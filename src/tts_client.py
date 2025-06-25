"""
OpenAI TTS API クライアント

Phase 3: プロダクション品質対応版
- プリセット機能
- 詳細音声制御（instructions）
- キャッシュシステム統合
- 長文処理（4096文字制限対応）
- パフォーマンス最適化
"""

import asyncio
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Literal, Dict, Any, List, Union

from openai import AsyncOpenAI
import logging

# 内部モジュール
from config import get_config, TTSPreset
from cache import get_cache, TTSCacheKey
from utils import split_long_text, merge_audio_files, normalize_text_for_speech, estimate_speech_duration

logger = logging.getLogger(__name__)

# 型定義
VoiceType = Literal["alloy", "echo", "fable", "onyx", "nova", "shimmer", "coral"]
ResponseFormat = Literal["mp3", "opus", "aac", "flac", "wav", "pcm"]
OutputMode = Literal["file", "play", "both"]


class TTSClient:
    """OpenAI TTS APIクライアント - Phase 3プロダクション版"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        TTSクライアントを初期化
        
        Args:
            api_key: OpenAI APIキー。Noneの場合は環境変数から取得
        """
        # 設定管理の取得
        self.config = get_config()
        
        # APIキーの設定
        self.api_key = api_key or self.config.openai_api_key
        if not self.api_key:
            raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY environment variable.")
        
        self.client = AsyncOpenAI(api_key=self.api_key)
        self.temp_dir = self.config.get_temp_dir()
        
        # キャッシュシステムの初期化
        self.cache = get_cache(
            max_size=self.config.cache_config.max_size,
            ttl_hours=self.config.cache_config.ttl_hours,
            cache_dir=self.temp_dir / "cache"
        ) if self.config.cache_config.enabled else None
        
        logger.info(f"TTS Client initialized with cache={'enabled' if self.cache else 'disabled'}")
    
    async def generate_speech(
        self,
        text: str,
        voice: Optional[VoiceType] = None,
        speed: Optional[float] = None,
        response_format: Optional[ResponseFormat] = None,
        output_mode: Optional[OutputMode] = None,
        instructions: Optional[str] = None,
        preset: Optional[str] = None,
        enable_cache: bool = True
    ) -> Union[str, List[str]]:
        """
        テキストを音声ファイルに変換（Phase 3: 全機能対応版）
        
        Args:
            text: 音声に変換するテキスト
            voice: 使用する音声
            speed: 再生速度（0.25-4.0）
            response_format: 出力形式
            output_mode: 出力モード
            instructions: 音声特徴指示
            preset: プリセット名
            enable_cache: キャッシュ使用の有効/無効
            
        Returns:
            Union[str, List[str]]: 生成された音声ファイルのパス（単一または複数）
            
        Raises:
            ValueError: パラメータが不正な場合
            Exception: OpenAI API呼び出しでエラーが発生した場合
        """
        # パラメータのバリデーションと正規化
        validated_params = self.config.validate_tts_parameters(
            text=text,
            voice=voice,
            speed=speed,
            response_format=response_format,
            output_mode=output_mode,
            instructions=instructions,
            preset=preset
        )
        
        # テキストの前処理
        processed_text = normalize_text_for_speech(validated_params["text"])
        
        # 長文チェックと分割
        if len(processed_text) > self.config.server_config.max_text_length:
            logger.info(f"Long text detected ({len(processed_text)} chars), splitting...")
            return await self._generate_long_speech(processed_text, validated_params, enable_cache)
        
        # 単一ファイル生成
        return await self._generate_single_speech(processed_text, validated_params, enable_cache)

    async def generate_speech_stream(
        self,
        text: str,
        voice: Optional[VoiceType] = None,
        speed: Optional[float] = None,
        response_format: Optional[ResponseFormat] = None,
        instructions: Optional[str] = None,
        preset: Optional[str] = None,
    ):
        """Create a streaming speech response for immediate playback."""
        validated_params = self.config.validate_tts_parameters(
            text=text,
            voice=voice,
            speed=speed,
            response_format=response_format,
            output_mode="play",
            instructions=instructions,
            preset=preset,
        )

        # Streaming playback works best with uncompressed audio.
        # If the requested format is MP3 (the default), switch to WAV
        # to avoid playback issues such as white noise.
        if validated_params["response_format"] == "mp3":
            validated_params["response_format"] = "wav"

        processed_text = normalize_text_for_speech(validated_params["text"])

        api_params = {
            "model": "tts-1",
            "voice": validated_params["voice"],
            "input": processed_text,
            "response_format": validated_params["response_format"],
            "speed": validated_params["speed"],
        }

        # Try the modern streaming interface first.  This returns an async
        # context manager yielding the stream.
        try:
            if hasattr(self.client.audio.speech, "with_streaming_response"):
                return self.client.audio.speech.with_streaming_response.create(
                    **api_params
                )
        except Exception:
            pass

        # Older releases use ``stream=True`` for streaming responses.
        try:
            return await self.client.audio.speech.create(
                **api_params,
                stream=True,
            )
        except TypeError:
            # ``stream`` not supported – fall back to a non-streaming request.
            resp = await self.client.audio.speech.create(**api_params)
            from io import BytesIO

            return BytesIO(resp.content)
    
    async def _generate_single_speech(
        self,
        text: str,
        params: Dict[str, Any],
        enable_cache: bool
    ) -> str:
        """
        単一音声ファイルの生成
        
        Args:
            text: 音声テキスト
            params: バリデーション済みパラメータ
            enable_cache: キャッシュ使用フラグ
            
        Returns:
            str: 生成された音声ファイルのパス
        """
        # キャッシュキーの生成
        cache_key = None
        if self.cache and enable_cache:
            cache_key = TTSCacheKey(
                text=text,
                voice=params["voice"],
                speed=params["speed"],
                response_format=params["response_format"],
                instructions=params.get("instructions")
            )
            
            # キャッシュからの取得を試行
            cached_path = self.cache.get(cache_key)
            if cached_path:
                logger.info(f"Cache hit for speech generation")
                return cached_path
        
        try:
            # OpenAI TTS API呼び出し準備
            api_params = {
                "model": "tts-1",
                "voice": params["voice"],
                "input": text,
                "response_format": params["response_format"],
                "speed": params["speed"]
            }
            
            # instructions対応（注意: OpenAI TTS APIは直接的なinstructionsパラメータをサポートしていない）
            # 実際の実装では、instructionsはテキストの前処理やプロンプトエンジニアリングで対応
            if params.get("instructions"):
                logger.debug(f"Instructions provided: {params['instructions']}")
                # 将来的な拡張ポイント
            
            logger.info(f"Generating speech: {len(text)} chars, voice={params['voice']}, speed={params['speed']}")
            
            # OpenAI TTS API呼び出し
            response = await self.client.audio.speech.create(**api_params)
            
            # 一意なファイル名を生成
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            file_extension = params["response_format"]
            file_path = self.temp_dir / f"tts_{timestamp}.{file_extension}"
            
            # ファイルに保存
            file_path.write_bytes(response.content)
            
            # キャッシュに保存
            if self.cache and enable_cache and cache_key:
                self.cache.put(cache_key, str(file_path))
            
            logger.info(f"Speech generated: {file_path}")
            return str(file_path)
            
        except Exception as e:
            # OpenAI API関連のエラーを適切に処理
            if "api key" in str(e).lower():
                raise Exception("OpenAI APIキーが無効です。設定を確認してください。") from e
            elif "quota" in str(e).lower():
                raise Exception("OpenAI APIの利用制限に達しました。課金設定を確認してください。") from e
            elif "rate limit" in str(e).lower():
                raise Exception("OpenAI APIのレート制限に達しました。しばらく待ってから再試行してください。") from e
            else:
                raise Exception(f"音声生成中にエラーが発生しました: {str(e)}") from e
    
    async def _generate_long_speech(
        self,
        text: str,
        params: Dict[str, Any],
        enable_cache: bool
    ) -> List[str]:
        """
        長文音声ファイルの生成（分割処理）
        
        Args:
            text: 長文テキスト
            params: バリデーション済みパラメータ
            enable_cache: キャッシュ使用フラグ
            
        Returns:
            List[str]: 生成された音声ファイルのパスリスト
        """
        # テキストを分割
        text_chunks = split_long_text(text, self.config.server_config.long_text_split_size)
        logger.info(f"Text split into {len(text_chunks)} chunks for processing")
        
        # 分割されたテキストを並行処理
        file_paths = []
        
        # 並行処理での生成（APIレート制限を考慮して適度な並行数）
        semaphore = asyncio.Semaphore(3)  # 最大3並行
        
        async def generate_chunk(chunk_text: str, chunk_index: int) -> str:
            async with semaphore:
                try:
                    logger.debug(f"Processing chunk {chunk_index + 1}/{len(text_chunks)}")
                    return await self._generate_single_speech(chunk_text, params, enable_cache)
                except Exception as e:
                    logger.error(f"Failed to generate chunk {chunk_index + 1}: {e}")
                    raise
        
        # 全チャンクを並行処理
        tasks = [
            generate_chunk(chunk, i)
            for i, chunk in enumerate(text_chunks)
        ]
        
        try:
            file_paths = await asyncio.gather(*tasks)
            logger.info(f"Successfully generated {len(file_paths)} audio chunks")
            return file_paths
            
        except Exception as e:
            # 一部でも失敗した場合は生成済みファイルをクリーンアップ
            for path in file_paths:
                try:
                    Path(path).unlink(missing_ok=True)
                except Exception:
                    pass
            raise Exception(f"長文音声生成中にエラーが発生しました: {str(e)}") from e
    
    def merge_long_speech_files(
        self,
        file_paths: List[str],
        output_format: str = "mp3"
    ) -> str:
        """
        分割された音声ファイルを結合
        
        Args:
            file_paths: 結合する音声ファイルのパスリスト
            output_format: 出力形式
            
        Returns:
            str: 結合された音声ファイルのパス
        """
        if len(file_paths) <= 1:
            return file_paths[0] if file_paths else ""
        
        try:
            merged_path = merge_audio_files(file_paths, output_format, self.temp_dir)
            logger.info(f"Audio files merged: {merged_path}")
            return merged_path
        except Exception as e:
            logger.error(f"Failed to merge audio files: {e}")
            # 結合に失敗した場合は最初のファイルを返す
            return file_paths[0]
    
    async def get_voice_preview(
        self,
        voice: VoiceType,
        sample_text: str = "これはサンプル音声です。Hello, this is a sample voice."
    ) -> str:
        """
        音声のプレビューサンプルを生成
        
        Args:
            voice: プレビューする音声
            sample_text: サンプルテキスト
            
        Returns:
            str: プレビュー音声ファイルのパス
        """
        logger.info(f"Generating voice preview for: {voice}")
        
        # プレビュー用の固定パラメータ
        params = {
            "voice": voice,
            "speed": 1.0,
            "response_format": "mp3",
            "output_mode": "file"
        }
        
        validated_params = self.config.validate_tts_parameters(
            text=sample_text,
            **params
        )
        
        return await self._generate_single_speech(sample_text, validated_params, enable_cache=True)
    
    def get_supported_voices(self) -> Dict[str, str]:
        """
        サポートされている音声一覧と説明を取得
        
        Returns:
            Dict[str, str]: 音声名と説明のマッピング
        """
        return {
            "alloy": "中性的で汎用性の高い音声",
            "echo": "男性的で深みのある音声", 
            "fable": "女性的で温かみのある音声",
            "onyx": "深く落ち着いた男性音声",
            "nova": "若々しく活発な女性音声",
            "shimmer": "柔らかく優雅な女性音声",
            "coral": "明るく親しみやすい女性音声"
        }
    
    def get_supported_formats(self) -> List[str]:
        """
        サポートされている出力形式一覧を取得
        
        Returns:
            List[str]: サポートされている出力形式のリスト
        """
        return ["mp3", "opus", "aac", "flac", "wav", "pcm"]
    
    def get_preset_info(self) -> Dict[str, Dict[str, Any]]:
        """
        利用可能なプリセット情報を取得
        
        Returns:
            Dict[str, Dict[str, Any]]: プリセット名と詳細情報のマッピング
        """
        presets = self.config.list_presets()
        return {
            name: {
                "description": preset.description,
                "voice": preset.voice,
                "speed": preset.speed,
                "response_format": preset.response_format,
                "instructions": preset.instructions
            }
            for name, preset in presets.items()
        }
    
    def get_cache_stats(self) -> Optional[Dict[str, Any]]:
        """
        キャッシュ統計情報を取得
        
        Returns:
            Optional[Dict[str, Any]]: キャッシュ統計、キャッシュが無効な場合はNone
        """
        if self.cache:
            return self.cache.get_stats()
        return None
    
    def clear_cache(self) -> None:
        """キャッシュをクリア"""
        if self.cache:
            self.cache.clear()
            logger.info("Cache cleared")
    
    def estimate_generation_time(
        self,
        text: str,
        speed: float = 1.0
    ) -> Dict[str, float]:
        """
        音声生成と再生時間を推定
        
        Args:
            text: 音声テキスト
            speed: 再生速度
            
        Returns:
            Dict[str, float]: 推定時間情報
        """
        speech_duration = estimate_speech_duration(text, speed)
        
        # 生成時間の推定（経験的な値）
        generation_time = len(text) * 0.01  # 1文字あたり約0.01秒
        
        return {
            "speech_duration_seconds": speech_duration,
            "estimated_generation_seconds": generation_time,
            "text_length": len(text),
            "is_long_text": len(text) > self.config.server_config.max_text_length
        }
    
    def cleanup_old_files(self, max_age_hours: int = None):
        """
        古い一時ファイルを削除
        
        Args:
            max_age_hours: 削除対象となるファイルの経過時間（時間）
        """
        max_age_hours = max_age_hours or self.config.server_config.temp_dir_cleanup_hours
        
        try:
            import time
            current_time = time.time()
            max_age_seconds = max_age_hours * 3600
            
            cleaned_count = 0
            for file_path in self.temp_dir.glob("tts_*"):
                if file_path.is_file():
                    file_age = current_time - file_path.stat().st_mtime
                    if file_age > max_age_seconds:
                        file_path.unlink()
                        cleaned_count += 1
            
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} old temporary files")
                
        except Exception as e:
            logger.warning(f"Failed to cleanup old files: {e}")

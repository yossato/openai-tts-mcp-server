"""
OpenAI TTS API クライアント

Phase 2: パラメータ選択機能対応版
- 音声パラメータ選択機能（voice, speed, response_format）
- 音声再生機能のサポート
- バリデーション強化
"""

import asyncio
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Literal, Dict, Any

from openai import AsyncOpenAI


# OpenAI TTS でサポートされている音声
SUPPORTED_VOICES = [
    "alloy", "echo", "fable", "onyx", "nova", "shimmer", "coral"
]

# 音声の特徴説明
VOICE_DESCRIPTIONS = {
    "alloy": "中性的で汎用性の高い音声",
    "echo": "男性的で深みのある音声", 
    "fable": "女性的で温かみのある音声",
    "onyx": "深く落ち着いた男性音声",
    "nova": "若々しく活発な女性音声",
    "shimmer": "柔らかく優雅な女性音声",
    "coral": "明るく親しみやすい女性音声"
}

# サポートされている出力形式
SUPPORTED_FORMATS = ["mp3", "opus", "aac", "flac", "wav", "pcm"]

# 出力モード
OutputMode = Literal["file", "play", "both"]
VoiceType = Literal["alloy", "echo", "fable", "onyx", "nova", "shimmer", "coral"]
ResponseFormat = Literal["mp3", "opus", "aac", "flac", "wav", "pcm"]


class TTSClient:
    """OpenAI TTS APIクライアント - Phase 2拡張版"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        TTSクライアントを初期化
        
        Args:
            api_key: OpenAI APIキー。Noneの場合は環境変数から取得
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY environment variable.")
        
        self.client = AsyncOpenAI(api_key=self.api_key)
        self.temp_dir = Path(tempfile.gettempdir()) / "openai_tts_mcp"
        self.temp_dir.mkdir(exist_ok=True)
    
    def validate_parameters(
        self, 
        text: str,
        voice: str = "alloy",
        speed: float = 1.0,
        response_format: str = "mp3"
    ) -> Dict[str, Any]:
        """
        パラメータのバリデーション
        
        Args:
            text: 音声に変換するテキスト
            voice: 使用する音声
            speed: 再生速度
            response_format: 出力形式
            
        Returns:
            Dict[str, Any]: バリデーション済みパラメータ
            
        Raises:
            ValueError: パラメータが不正な場合
        """
        # テキストの検証
        if not text or not text.strip():
            raise ValueError("テキストが空です。音声に変換するテキストを入力してください。")
        
        if len(text) > 4096:
            raise ValueError(f"テキストが長すぎます。最大4096文字ですが、{len(text)}文字入力されました。")
        
        # 音声の検証
        if voice not in SUPPORTED_VOICES:
            raise ValueError(f"サポートされていない音声です。使用可能な音声: {', '.join(SUPPORTED_VOICES)}")
        
        # 速度の検証
        if not isinstance(speed, (int, float)):
            raise ValueError("速度は数値で指定してください。")
        
        if not (0.25 <= speed <= 4.0):
            raise ValueError(f"速度は0.25～4.0の範囲で指定してください。入力値: {speed}")
        
        # 出力形式の検証
        if response_format not in SUPPORTED_FORMATS:
            raise ValueError(f"サポートされていない出力形式です。使用可能な形式: {', '.join(SUPPORTED_FORMATS)}")
        
        return {
            "text": text.strip(),
            "voice": voice,
            "speed": float(speed),
            "response_format": response_format
        }
    
    async def generate_speech(
        self,
        text: str,
        voice: VoiceType = "alloy",
        speed: float = 1.0,
        response_format: ResponseFormat = "mp3"
    ) -> str:
        """
        テキストを音声ファイルに変換（Phase 2: パラメータ対応版）
        
        Args:
            text: 音声に変換するテキスト
            voice: 使用する音声（デフォルト: "alloy"）
            speed: 再生速度（0.25-4.0、デフォルト: 1.0）
            response_format: 出力形式（デフォルト: "mp3"）
            
        Returns:
            str: 生成された音声ファイルのパス
            
        Raises:
            ValueError: パラメータが不正な場合
            Exception: OpenAI API呼び出しでエラーが発生した場合
        """
        # パラメータのバリデーション
        validated_params = self.validate_parameters(text, voice, speed, response_format)
        
        try:
            # OpenAI TTS API呼び出し（Phase 2: パラメータ対応）
            response = await self.client.audio.speech.create(
                model="tts-1",  # 高速モデル
                voice=validated_params["voice"],
                input=validated_params["text"],
                response_format=validated_params["response_format"],
                speed=validated_params["speed"]
            )
            
            # 一意なファイル名を生成
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            file_extension = validated_params["response_format"]
            file_path = self.temp_dir / f"tts_{timestamp}.{file_extension}"
            
            # ファイルに保存
            file_path.write_bytes(response.content)
            
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
    
    def get_supported_voices(self) -> Dict[str, str]:
        """
        サポートされている音声一覧と説明を取得
        
        Returns:
            Dict[str, str]: 音声名と説明のマッピング
        """
        return VOICE_DESCRIPTIONS.copy()
    
    def get_supported_formats(self) -> list[str]:
        """
        サポートされている出力形式一覧を取得
        
        Returns:
            list[str]: サポートされている出力形式のリスト
        """
        return SUPPORTED_FORMATS.copy()
    
    def cleanup_old_files(self, max_age_hours: int = 24):
        """
        古い一時ファイルを削除
        
        Args:
            max_age_hours: 削除対象となるファイルの経過時間（時間）
        """
        try:
            import time
            current_time = time.time()
            max_age_seconds = max_age_hours * 3600
            
            for file_path in self.temp_dir.glob("tts_*"):
                if file_path.is_file():
                    file_age = current_time - file_path.stat().st_mtime
                    if file_age > max_age_seconds:
                        file_path.unlink()
        except Exception:
            # クリーンアップのエラーは無視（重要ではない）
            pass

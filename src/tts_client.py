"""
OpenAI TTS API クライアント

Phase 1: 基本的な音声生成機能
"""

import asyncio
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from openai import AsyncOpenAI


class TTSClient:
    """OpenAI TTS APIクライアント"""
    
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
    
    async def generate_speech(self, text: str) -> str:
        """
        テキストを音声ファイルに変換（Phase 1: 固定パラメータ版）
        
        Args:
            text: 音声に変換するテキスト
            
        Returns:
            str: 生成された音声ファイルのパス
            
        Raises:
            ValueError: テキストが空または長すぎる場合
            Exception: OpenAI API呼び出しでエラーが発生した場合
        """
        # 入力検証
        if not text or not text.strip():
            raise ValueError("テキストが空です。音声に変換するテキストを入力してください。")
        
        if len(text) > 4096:
            raise ValueError(f"テキストが長すぎます。最大4096文字ですが、{len(text)}文字入力されました。")
        
        try:
            # Phase 1: 固定パラメータで音声生成
            response = await self.client.audio.speech.create(
                model="tts-1",  # 高速モデル
                voice="alloy",  # 固定
                input=text,
                response_format="mp3",  # 固定
                speed=1.0  # 固定
            )
            
            # 一意なファイル名を生成
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            file_path = self.temp_dir / f"tts_{timestamp}.mp3"
            
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
            
            for file_path in self.temp_dir.glob("tts_*.mp3"):
                if file_path.is_file():
                    file_age = current_time - file_path.stat().st_mtime
                    if file_age > max_age_seconds:
                        file_path.unlink()
        except Exception:
            # クリーンアップのエラーは無視（重要ではない）
            pass

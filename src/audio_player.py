"""
音声再生機能

Phase 2: 音声ファイルの再生機能
- プラットフォーム対応の音声再生
- 非同期再生サポート
- エラーハンドリング
"""

import asyncio
import logging
import platform
import subprocess
import sys
from pathlib import Path
from typing import Optional, Union

# セキュアなログ設定（標準エラー出力を使用）
logger = logging.getLogger(__name__)


class AudioPlayer:
    """
    プラットフォーム対応音声プレイヤー
    OpenAI の LocalAudioPlayer に類似した機能を提供
    """
    
    def __init__(self):
        """音声プレイヤーを初期化"""
        self.platform = platform.system().lower()
        logger.info(f"AudioPlayer initialized for platform: {self.platform}")
    
    async def play(self, file_path: Union[str, Path]) -> bool:
        """
        音声ファイルを再生
        
        Args:
            file_path: 再生する音声ファイルのパス
            
        Returns:
            bool: 再生成功時True、失敗時False
        """
        file_path = Path(file_path)
        
        # ファイル存在確認
        if not file_path.exists():
            logger.error(f"Audio file not found: {file_path}")
            return False
        
        try:
            logger.info(f"Playing audio file: {file_path}")
            
            if self.platform == "darwin":  # macOS
                return await self._play_macos(file_path)
            elif self.platform == "linux":  # Linux
                return await self._play_linux(file_path)
            elif self.platform == "windows":  # Windows
                return await self._play_windows(file_path)
            else:
                logger.error(f"Unsupported platform: {self.platform}")
                return False
                
        except Exception as e:
            logger.error(f"Error playing audio: {e}")
            return False
    
    async def _play_macos(self, file_path: Path) -> bool:
        """macOS での音声再生"""
        try:
            # afplay を使用（macOS標準）
            process = await asyncio.create_subprocess_exec(
                "afplay", str(file_path),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE
            )
            
            _, stderr = await process.communicate()
            
            if process.returncode == 0:
                logger.info("Audio playback completed successfully (afplay)")
                return True
            else:
                logger.error(f"afplay failed: {stderr.decode()}")
                return False
                
        except FileNotFoundError:
            logger.error("afplay not found on macOS")
            return False
        except Exception as e:
            logger.error(f"macOS audio playback error: {e}")
            return False
    
    async def _play_linux(self, file_path: Path) -> bool:
        """Linux での音声再生"""
        # Linux での再生コマンドを優先順位順に試行
        commands = [
            ["aplay", str(file_path)],           # ALSA
            ["paplay", str(file_path)],          # PulseAudio
            ["mpg123", str(file_path)],          # mpg123
            ["ffplay", "-nodisp", "-autoexit", str(file_path)]  # FFmpeg
        ]
        
        for cmd in commands:
            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE
                )
                
                _, stderr = await process.communicate()
                
                if process.returncode == 0:
                    logger.info(f"Audio playback completed successfully ({cmd[0]})")
                    return True
                else:
                    logger.warning(f"{cmd[0]} failed: {stderr.decode()}")
                    
            except FileNotFoundError:
                logger.debug(f"{cmd[0]} not found")
                continue
            except Exception as e:
                logger.warning(f"{cmd[0]} error: {e}")
                continue
        
        logger.error("No working audio player found on Linux")
        return False
    
    async def _play_windows(self, file_path: Path) -> bool:
        """Windows での音声再生"""
        try:
            # PowerShell を使用してWindows Media Player を呼び出し
            powershell_cmd = f"""
            Add-Type -AssemblyName presentationCore
            $mediaPlayer = New-Object system.windows.media.mediaplayer
            $mediaPlayer.open('{file_path}')
            $mediaPlayer.Play()
            Start-Sleep -Seconds 1
            while($mediaPlayer.naturalDuration.HasTimeSpan -eq $false) {{
                Start-Sleep -Milliseconds 100
            }}
            $duration = $mediaPlayer.naturalDuration.timeSpan.TotalSeconds
            Start-Sleep -Seconds $duration
            """
            
            process = await asyncio.create_subprocess_exec(
                "powershell", "-Command", powershell_cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE
            )
            
            _, stderr = await process.communicate()
            
            if process.returncode == 0:
                logger.info("Audio playback completed successfully (PowerShell)")
                return True
            else:
                logger.error(f"PowerShell audio playback failed: {stderr.decode()}")
                return False
                
        except Exception as e:
            logger.error(f"Windows audio playback error: {e}")
            return False
    
    def play_sync(self, file_path: Union[str, Path]) -> bool:
        """
        同期的な音声再生（後方互換性のため）
        
        Args:
            file_path: 再生する音声ファイルのパス
            
        Returns:
            bool: 再生成功時True、失敗時False
        """
        try:
            return asyncio.run(self.play(file_path))
        except Exception as e:
            logger.error(f"Sync audio playback error: {e}")
            return False
    
    @staticmethod
    def get_platform_info() -> dict:
        """
        プラットフォーム情報を取得
        
        Returns:
            dict: プラットフォーム情報
        """
        return {
            "platform": platform.system(),
            "platform_release": platform.release(),
            "platform_version": platform.version(),
            "python_version": sys.version
        }


# 簡単に使用できるグローバルインスタンス
_global_player = None

def get_audio_player() -> AudioPlayer:
    """グローバル音声プレイヤーインスタンスを取得"""
    global _global_player
    if _global_player is None:
        _global_player = AudioPlayer()
    return _global_player


async def play_audio(file_path: Union[str, Path]) -> bool:
    """
    音声ファイルを再生（便利関数）
    
    Args:
        file_path: 再生する音声ファイルのパス
        
    Returns:
        bool: 再生成功時True、失敗時False
    """
    player = get_audio_player()
    return await player.play(file_path)

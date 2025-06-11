"""
設定管理システム

Phase 3: プロダクション品質対応
- 環境変数と設定ファイルの統合管理
- プリセット機能のサポート
- デフォルト値の設定
- 設定バリデーション
"""

import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Any, Optional, Literal

# 型定義
VoiceType = Literal["alloy", "echo", "fable", "onyx", "nova", "shimmer", "coral"]
ResponseFormat = Literal["mp3", "opus", "aac", "flac", "wav", "pcm"]
OutputMode = Literal["file", "play", "both"]


@dataclass
class TTSPreset:
    """音声プリセット設定"""
    name: str
    description: str
    voice: VoiceType
    speed: float
    response_format: ResponseFormat
    instructions: Optional[str] = None


@dataclass
class TTSDefaults:
    """TTS デフォルト設定"""
    voice: VoiceType = "alloy"
    speed: float = 1.0
    response_format: ResponseFormat = "mp3"
    output_mode: OutputMode = "file"
    instructions: Optional[str] = None


@dataclass
class CacheConfig:
    """キャッシュ設定"""
    enabled: bool = True
    max_size: int = 100
    ttl_hours: int = 24


@dataclass
class ServerConfig:
    """サーバー設定"""
    name: str = "openai-tts"
    version: str = "0.3.0"
    temp_dir_cleanup_hours: int = 24
    max_text_length: int = 4096
    long_text_split_size: int = 4000


class ConfigManager:
    """設定管理クラス"""
    
    # 組み込みプリセット
    BUILTIN_PRESETS = {
        "cheerful_female": TTSPreset(
            name="cheerful_female",
            description="明るく親しみやすい女性音声",
            voice="coral",
            speed=1.1,
            response_format="mp3",
            instructions="明るく親しみやすい声で、少し速めに話してください"
        ),
        "calm_male": TTSPreset(
            name="calm_male",
            description="落ち着いた男性音声",
            voice="onyx", 
            speed=0.9,
            response_format="mp3",
            instructions="落ち着いてゆっくりと、安心感のある声で話してください"
        ),
        "professional": TTSPreset(
            name="professional",
            description="プロフェッショナルで権威のある音声",
            voice="echo",
            speed=1.0,
            response_format="flac",
            instructions="フォーマルで権威のある、ビジネス向けの声で話してください"
        ),
        "gentle_female": TTSPreset(
            name="gentle_female",
            description="優しく温かみのある女性音声",
            voice="shimmer",
            speed=0.95,
            response_format="mp3",
            instructions="優しく温かみのある、穏やかな声で話してください"
        ),
        "energetic": TTSPreset(
            name="energetic",
            description="活発でエネルギッシュな音声",
            voice="nova",
            speed=1.2,
            response_format="mp3",
            instructions="活発でエネルギッシュに、元気よく話してください"
        ),
        "storyteller": TTSPreset(
            name="storyteller",
            description="ストーリーテリングに適した音声",
            voice="fable",
            speed=1.0,
            response_format="wav",
            instructions="物語を語るように、表現力豊かに話してください"
        )
    }
    
    def __init__(self, config_file: Optional[Path] = None):
        """
        設定管理を初期化
        
        Args:
            config_file: 設定ファイルのパス（Noneの場合はデフォルト位置）
        """
        self.project_root = Path(__file__).parent.parent
        self.config_file = config_file or self.project_root / "config.json"
        
        # 設定の初期化
        self.defaults = TTSDefaults()
        self.cache_config = CacheConfig()
        self.server_config = ServerConfig()
        self.custom_presets: Dict[str, TTSPreset] = {}
        
        # 設定ファイルの読み込み
        self.load_config()
        
        # 環境変数から OpenAI API キーを取得
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        if not self.openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY environment variable is required. "
                "Please set it in your .env file or environment."
            )
    
    def load_config(self) -> None:
        """設定ファイルを読み込み"""
        if not self.config_file.exists():
            # 設定ファイルが存在しない場合はデフォルト設定で作成
            self.save_config()
            return
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # デフォルト設定の読み込み
            if "defaults" in config_data:
                defaults_data = config_data["defaults"]
                self.defaults = TTSDefaults(**defaults_data)
            
            # キャッシュ設定の読み込み
            if "cache" in config_data:
                cache_data = config_data["cache"]
                self.cache_config = CacheConfig(**cache_data)
            
            # サーバー設定の読み込み
            if "server" in config_data:
                server_data = config_data["server"]
                self.server_config = ServerConfig(**server_data)
            
            # カスタムプリセットの読み込み
            if "custom_presets" in config_data:
                presets_data = config_data["custom_presets"]
                self.custom_presets = {
                    name: TTSPreset(**preset_data)
                    for name, preset_data in presets_data.items()
                }
        
        except Exception as e:
            # 設定ファイルが破損している場合はデフォルト設定を使用
            print(f"Warning: Failed to load config file: {e}")
            print("Using default configuration")
    
    def save_config(self) -> None:
        """設定ファイルに保存"""
        config_data = {
            "defaults": asdict(self.defaults),
            "cache": asdict(self.cache_config),
            "server": asdict(self.server_config),
            "custom_presets": {
                name: asdict(preset)
                for name, preset in self.custom_presets.items()
            }
        }
        
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Warning: Failed to save config file: {e}")
    
    def get_preset(self, preset_name: str) -> Optional[TTSPreset]:
        """
        プリセットを取得
        
        Args:
            preset_name: プリセット名
            
        Returns:
            TTSPreset: プリセット設定、見つからない場合はNone
        """
        # 組み込みプリセットを優先
        if preset_name in self.BUILTIN_PRESETS:
            return self.BUILTIN_PRESETS[preset_name]
        
        # カスタムプリセット
        return self.custom_presets.get(preset_name)
    
    def list_presets(self) -> Dict[str, TTSPreset]:
        """
        利用可能なプリセット一覧を取得
        
        Returns:
            Dict[str, TTSPreset]: プリセット名と設定のマッピング
        """
        all_presets = self.BUILTIN_PRESETS.copy()
        all_presets.update(self.custom_presets)
        return all_presets
    
    def add_custom_preset(self, preset: TTSPreset) -> None:
        """
        カスタムプリセットを追加
        
        Args:
            preset: プリセット設定
        """
        # 組み込みプリセットと同名は禁止
        if preset.name in self.BUILTIN_PRESETS:
            raise ValueError(f"Cannot override builtin preset: {preset.name}")
        
        self.custom_presets[preset.name] = preset
        self.save_config()
    
    def remove_custom_preset(self, preset_name: str) -> bool:
        """
        カスタムプリセットを削除
        
        Args:
            preset_name: 削除するプリセット名
            
        Returns:
            bool: 削除成功の場合True
        """
        if preset_name in self.custom_presets:
            del self.custom_presets[preset_name]
            self.save_config()
            return True
        return False
    
    def validate_tts_parameters(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
        response_format: Optional[str] = None,
        output_mode: Optional[str] = None,
        instructions: Optional[str] = None,
        preset: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        TTSパラメータをバリデーションして正規化
        
        Args:
            text: 音声に変換するテキスト
            voice: 音声（Noneの場合はデフォルト使用）
            speed: 速度（Noneの場合はデフォルト使用）
            response_format: 出力形式（Noneの場合はデフォルト使用）
            output_mode: 出力モード（Noneの場合はデフォルト使用）
            instructions: 音声指示（Noneの場合はデフォルト使用）
            preset: プリセット名（指定された場合は他のパラメータより優先）
            
        Returns:
            Dict[str, Any]: バリデーション済みパラメータ
            
        Raises:
            ValueError: パラメータが不正な場合
        """
        # プリセットが指定された場合はプリセットから設定を取得
        if preset:
            preset_config = self.get_preset(preset)
            if not preset_config:
                available_presets = list(self.list_presets().keys())
                raise ValueError(
                    f"不明なプリセット: {preset}. "
                    f"利用可能なプリセット: {', '.join(available_presets)}"
                )
            
            # プリセットの値を使用（個別指定があれば上書き）
            voice = voice or preset_config.voice
            speed = speed or preset_config.speed
            response_format = response_format or preset_config.response_format
            instructions = instructions or preset_config.instructions
        
        # デフォルト値の適用
        voice = voice or self.defaults.voice
        speed = speed or self.defaults.speed
        response_format = response_format or self.defaults.response_format
        output_mode = output_mode or self.defaults.output_mode
        instructions = instructions or self.defaults.instructions
        
        # バリデーション
        if not text or not text.strip():
            raise ValueError("テキストが空です。音声に変換するテキストを入力してください。")
        
        if len(text) > self.server_config.max_text_length:
            raise ValueError(
                f"テキストが長すぎます。最大{self.server_config.max_text_length}文字ですが、"
                f"{len(text)}文字入力されました。"
            )
        
        # 音声の検証
        valid_voices = ["alloy", "echo", "fable", "onyx", "nova", "shimmer", "coral"]
        if voice not in valid_voices:
            raise ValueError(f"サポートされていない音声です。使用可能な音声: {', '.join(valid_voices)}")
        
        # 速度の検証
        if not isinstance(speed, (int, float)):
            raise ValueError("速度は数値で指定してください。")
        
        if not (0.25 <= speed <= 4.0):
            raise ValueError(f"速度は0.25～4.0の範囲で指定してください。入力値: {speed}")
        
        # 出力形式の検証
        valid_formats = ["mp3", "opus", "aac", "flac", "wav", "pcm"]
        if response_format not in valid_formats:
            raise ValueError(f"サポートされていない出力形式です。使用可能な形式: {', '.join(valid_formats)}")
        
        # 出力モードの検証
        valid_modes = ["file", "play", "both"]
        if output_mode not in valid_modes:
            raise ValueError(f"サポートされていない出力モードです。使用可能なモード: {', '.join(valid_modes)}")
        
        return {
            "text": text.strip(),
            "voice": voice,
            "speed": float(speed),
            "response_format": response_format,
            "output_mode": output_mode,
            "instructions": instructions,
            "preset": preset
        }
    
    def get_temp_dir(self) -> Path:
        """一時ディレクトリパスを取得"""
        temp_dir = Path.home() / ".cache" / "openai-tts-mcp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        return temp_dir


# グローバル設定インスタンス（シングルトン）
_config_instance: Optional[ConfigManager] = None


def get_config() -> ConfigManager:
    """設定マネージャーのインスタンスを取得（シングルトン）"""
    global _config_instance
    if _config_instance is None:
        _config_instance = ConfigManager()
    return _config_instance


def reload_config() -> ConfigManager:
    """設定を再読み込み"""
    global _config_instance
    _config_instance = ConfigManager()
    return _config_instance

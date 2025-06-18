#!/usr/bin/env python3
"""
OpenAI TTS MCP Server - Main Entry Point

Phase 3: プロダクション品質対応版
- キャッシュシステム統合
- プリセット機能
- 詳細音声制御（instructions）
- 長文処理（4096文字制限対応）
- 新ツール: get_voice_preview, get_cache_stats, manage_presets
- パフォーマンス最適化
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import List

# セキュアなログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# .envファイルのロード
try:
    from dotenv import load_dotenv
    
    project_root = Path(__file__).parent.parent
    env_path = project_root / ".env"
    load_dotenv(env_path)
    logger.info("Environment configuration loaded successfully")
    
except ImportError as e:
    logger.error(f"Failed to import dotenv: {e}")
    sys.exit(1)

# MCPライブラリのインポート
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    import mcp.types as types
    logger.info("MCP modules imported successfully")
    
except ImportError as e:
    logger.error(f"Failed to import MCP modules: {e}")
    sys.exit(1)

# 自作モジュール
try:
    from tts_client import TTSClient
    from audio_player import AudioPlayer
    from config import get_config, TTSPreset
    from cache import get_cache
    from utils import estimate_speech_duration
    logger.info("All custom modules imported successfully")
except ImportError as e:
    logger.error(f"Failed to import custom modules: {e}")
    sys.exit(1)

# MCPサーバーの初期化
app = Server(name="openai-tts", version="0.3.0")


@app.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """
    利用可能なツール一覧を返す
    Phase 3: 高度な機能対応版（6ツール提供）
    """
    logger.info("Listing available tools")
    return [
        types.Tool(
            name="generate_speech",
            description=(
                "テキストを音声ファイルに変換します。OpenAI TTSを使用して高品質な音声を生成し、"
                "指定された形式でファイル保存や音声再生を行います。"
                "長文（4096文字超）の自動分割、キャッシュによる高速化、プリセット機能をサポート。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "音声に変換するテキスト（最大4096文字、超過時は自動分割）",
                        "maxLength": 50000  # 長文対応
                    },
                    "voice": {
                        "type": "string",
                        "description": "使用する音声の種類",
                        "enum": ["alloy", "echo", "fable", "onyx", "nova", "shimmer", "coral"],
                        "default": "alloy"
                    },
                    "speed": {
                        "type": "number",
                        "description": "音声の再生速度（0.25-4.0）",
                        "minimum": 0.25,
                        "maximum": 4.0,
                        "default": 1.0
                    },
                    "response_format": {
                        "type": "string",
                        "description": "出力音声の形式",
                        "enum": ["mp3", "opus", "aac", "flac", "wav", "pcm"],
                        "default": "mp3"
                    },
                    "output_mode": {
                        "type": "string",
                        "description": "出力方法（file: ファイル保存のみ, play: 音声再生のみ, both: 両方）",
                        "enum": ["file", "play", "both"],
                        "default": "file"
                    },
                    "instructions": {
                        "type": "string",
                        "description": "音声の特徴指示（例: 'ゆっくりと優しく話してください'）"
                    },
                    "preset": {
                        "type": "string",
                        "description": "音声プリセット名（指定すると他のパラメータより優先）",
                        "enum": ["cheerful_female", "calm_male", "professional", "gentle_female", "energetic", "storyteller"]
                    },
                    "enable_cache": {
                        "type": "boolean",
                        "description": "キャッシュ使用の有効/無効",
                        "default": True
                    },
                    "merge_long_audio": {
                        "type": "boolean",
                        "description": "長文分割時に音声ファイルを結合するか",
                        "default": False
                    }
                },
                "required": ["text"],
                "additionalProperties": False
            }
        ),
        types.Tool(
            name="list_voices",
            description=(
                "OpenAI TTSで利用可能な音声の一覧と特徴を取得します。"
                "各音声の特徴や適用場面、プリセット情報を確認できます。"
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "additionalProperties": False
            }
        ),
        types.Tool(
            name="get_voice_preview",
            description=(
                "指定した音声のプレビューサンプルを生成します。"
                "音声選択の参考にするためのサンプル音声を提供します。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "voice": {
                        "type": "string",
                        "description": "プレビューする音声",
                        "enum": ["alloy", "echo", "fable", "onyx", "nova", "shimmer", "coral"]
                    },
                    "sample_text": {
                        "type": "string",
                        "description": "プレビュー用テキスト（省略時はデフォルト使用）",
                        "default": "これはサンプル音声です。Hello, this is a sample voice."
                    }
                },
                "required": ["voice"],
                "additionalProperties": False
            }
        ),
        types.Tool(
            name="get_cache_stats",
            description=(
                "キャッシュシステムの統計情報を取得します。"
                "ヒット率、使用量、エントリー数などのパフォーマンス情報を表示します。"
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "additionalProperties": False
            }
        ),
        types.Tool(
            name="manage_presets",
            description=(
                "音声プリセットの管理を行います。"
                "プリセット一覧の取得、カスタムプリセットの追加・削除が可能です。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "実行するアクション",
                        "enum": ["list", "add", "remove"],
                        "default": "list"
                    },
                    "preset_name": {
                        "type": "string",
                        "description": "プリセット名（add/remove時に必要）"
                    },
                    "preset_config": {
                        "type": "object",
                        "description": "プリセット設定（add時に必要）",
                        "properties": {
                            "description": {"type": "string"},
                            "voice": {"type": "string", "enum": ["alloy", "echo", "fable", "onyx", "nova", "shimmer", "coral"]},
                            "speed": {"type": "number", "minimum": 0.25, "maximum": 4.0},
                            "response_format": {"type": "string", "enum": ["mp3", "opus", "aac", "flac", "wav", "pcm"]},
                            "instructions": {"type": "string"}
                        }
                    }
                },
                "required": ["action"],
                "additionalProperties": False
            }
        ),
        types.Tool(
            name="estimate_speech_info",
            description=(
                "テキストから音声の推定情報を計算します。"
                "生成時間、再生時間、文字数などの詳細情報を提供します。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "推定対象のテキスト"
                    },
                    "speed": {
                        "type": "number",
                        "description": "再生速度（0.25-4.0）",
                        "minimum": 0.25,
                        "maximum": 4.0,
                        "default": 1.0
                    }
                },
                "required": ["text"],
                "additionalProperties": False
            }
        )
    ]


@app.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
    """
    ツールの実行を処理
    Phase 3: 6ツール対応版
    """
    logger.info(f"Tool called: {name} with arguments: {arguments}")
    
    if name == "generate_speech":
        return await handle_generate_speech(arguments)
    elif name == "list_voices":
        return await handle_list_voices(arguments)
    elif name == "get_voice_preview":
        return await handle_get_voice_preview(arguments)
    elif name == "get_cache_stats":
        return await handle_get_cache_stats(arguments)
    elif name == "manage_presets":
        return await handle_manage_presets(arguments)
    elif name == "estimate_speech_info":
        return await handle_estimate_speech_info(arguments)
    else:
        raise ValueError(f"Unknown tool: {name}")


async def handle_generate_speech(arguments: dict | None) -> list[types.TextContent]:
    """
    generate_speechツールの処理（Phase 3: 全機能対応版）
    """
    if not arguments:
        raise ValueError("引数が指定されていません")
    
    # パラメータの取得
    text = arguments.get("text")
    voice = arguments.get("voice")
    speed = arguments.get("speed")
    response_format = arguments.get("response_format")
    output_mode = arguments.get("output_mode")
    instructions = arguments.get("instructions")
    preset = arguments.get("preset")
    enable_cache = arguments.get("enable_cache", True)
    merge_long_audio = arguments.get("merge_long_audio", False)
    
    if not text:
        raise ValueError("textパラメータが指定されていません")
    
    try:
        logger.info(f"Generating speech - text: {len(text)} chars, preset: {preset}")
        tts_client = TTSClient()

        play_requested = output_mode in ["play", "both"]

        stream_resp = None
        if play_requested:
            stream_resp = await tts_client.generate_speech_stream(
                text=text,
                voice=voice,
                speed=speed,
                response_format=response_format,
                instructions=instructions,
                preset=preset,
            )
            audio_player = AudioPlayer()
            await audio_player.play(stream_resp)

        result = []
        if output_mode in ["file", "both"]:
            result = await tts_client.generate_speech(
                text=text,
                voice=voice,
                speed=speed,
                response_format=response_format,
                output_mode="file",
                instructions=instructions,
                preset=preset,
                enable_cache=enable_cache,
            )
        
        if result:
            if isinstance(result, list):
                file_paths = result
                if merge_long_audio and len(file_paths) > 1:
                    try:
                        merged_path = tts_client.merge_long_speech_files(
                            file_paths,
                            response_format or "mp3",
                        )
                        file_paths = [merged_path]
                        logger.info("Long audio files merged successfully")
                    except Exception as e:
                        logger.warning(f"Failed to merge audio files: {e}")
                main_file_path = file_paths[0]
                is_long_text = True
            else:
                file_paths = [result]
                main_file_path = result
                is_long_text = False
        else:
            file_paths = []
            main_file_path = "<streaming playback>"
            is_long_text = False

        played = play_requested
        
        # 古いファイルのクリーンアップ
        tts_client.cleanup_old_files()
        
        # 推定情報の取得
        estimation = tts_client.estimate_generation_time(text, speed or 1.0)
        
        # キャッシュ統計の取得
        cache_stats = tts_client.get_cache_stats()
        
        # 成功レスポンス
        result_data = {
            "success": True,
            "file_path": main_file_path,
            "file_count": len(file_paths),
            "is_long_text": is_long_text,
            "merged": merge_long_audio and is_long_text,
            "message": f"音声ファイルを生成しました: {len(file_paths)} ファイル",
            "parameters": {
                "text_length": len(text),
                "voice": voice,
                "speed": speed,
                "response_format": response_format,
                "output_mode": output_mode,
                "instructions": instructions,
                "preset": preset,
                "enable_cache": enable_cache
            },
            "playback_status": {
                "attempted": output_mode in ["play", "both"],
                "successful": played if output_mode in ["play", "both"] else None
            },
            "estimation": estimation,
            "cache_stats": cache_stats
        }
        
        logger.info(f"Speech generated successfully: {len(file_paths)} files")
        
        return [
            types.TextContent(
                type="text",
                text=json.dumps(result_data, ensure_ascii=False, indent=2)
            )
        ]
        
    except Exception as e:
        # エラーレスポンス
        error_result = {
            "success": False,
            "error": str(e),
            "message": "音声生成中にエラーが発生しました",
            "parameters": {
                "text_length": len(text) if text else 0,
                "voice": voice,
                "speed": speed,
                "response_format": response_format,
                "output_mode": output_mode,
                "preset": preset
            }
        }
        
        logger.error(f"Error generating speech: {e}", exc_info=True)
        
        return [
            types.TextContent(
                type="text", 
                text=json.dumps(error_result, ensure_ascii=False, indent=2)
            )
        ]


async def handle_list_voices(arguments: dict | None) -> list[types.TextContent]:
    """
    list_voicesツールの処理（Phase 3: プリセット対応版）
    """
    try:
        logger.info("Listing available voices and presets")
        tts_client = TTSClient()
        
        # 音声一覧と説明を取得
        voices = tts_client.get_supported_voices()
        formats = tts_client.get_supported_formats()
        presets = tts_client.get_preset_info()
        
        result = {
            "success": True,
            "voices": voices,
            "presets": presets,
            "supported_formats": formats,
            "speed_range": {
                "minimum": 0.25,
                "maximum": 4.0,
                "default": 1.0
            },
            "output_modes": [
                {
                    "mode": "file",
                    "description": "ファイルとして保存のみ"
                },
                {
                    "mode": "play", 
                    "description": "音声再生のみ（ファイルは一時的）"
                },
                {
                    "mode": "both",
                    "description": "ファイル保存と音声再生の両方"
                }
            ],
            "new_features": {
                "cache_system": "同一リクエストの高速化",
                "long_text_support": "4096文字超の自動分割処理",
                "presets": "事前定義された音声設定",
                "instructions": "詳細な音声特徴指示"
            },
            "usage_examples": [
                {
                    "description": "基本的な音声生成",
                    "parameters": {"text": "こんにちは"}
                },
                {
                    "description": "プリセット使用",
                    "parameters": {"text": "こんにちは", "preset": "cheerful_female"}
                },
                {
                    "description": "詳細指示付き",
                    "parameters": {"text": "こんにちは", "voice": "nova", "instructions": "元気よく話してください"}
                },
                {
                    "description": "長文処理（自動分割）",
                    "parameters": {"text": "長いテキスト...", "merge_long_audio": True}
                }
            ]
        }
        
        logger.info("Voice and preset list generated successfully")
        
        return [
            types.TextContent(
                type="text",
                text=json.dumps(result, ensure_ascii=False, indent=2)
            )
        ]
        
    except Exception as e:
        # エラーレスポンス
        error_result = {
            "success": False,
            "error": str(e),
            "message": "音声一覧の取得中にエラーが発生しました"
        }
        
        logger.error(f"Error listing voices: {e}", exc_info=True)
        
        return [
            types.TextContent(
                type="text",
                text=json.dumps(error_result, ensure_ascii=False, indent=2)
            )
        ]


async def handle_get_voice_preview(arguments: dict | None) -> list[types.TextContent]:
    """
    get_voice_previewツールの処理
    """
    if not arguments:
        raise ValueError("引数が指定されていません")
    
    voice = arguments.get("voice")
    sample_text = arguments.get("sample_text")
    
    if not voice:
        raise ValueError("voiceパラメータが指定されていません")
    
    try:
        logger.info(f"Generating voice preview for: {voice}")
        tts_client = TTSClient()
        
        # プレビュー音声生成
        file_path = await tts_client.get_voice_preview(voice, sample_text)
        
        # 音声再生
        audio_player = AudioPlayer()
        played = await audio_player.play(file_path)
        
        result = {
            "success": True,
            "voice": voice,
            "preview_file": file_path,
            "sample_text": sample_text or "これはサンプル音声です。Hello, this is a sample voice.",
            "played": played,
            "message": f"{voice}音声のプレビューを生成しました"
        }
        
        logger.info(f"Voice preview generated: {voice}")
        
        return [
            types.TextContent(
                type="text",
                text=json.dumps(result, ensure_ascii=False, indent=2)
            )
        ]
        
    except Exception as e:
        error_result = {
            "success": False,
            "error": str(e),
            "message": "音声プレビューの生成中にエラーが発生しました",
            "voice": voice
        }
        
        logger.error(f"Error generating voice preview: {e}", exc_info=True)
        
        return [
            types.TextContent(
                type="text",
                text=json.dumps(error_result, ensure_ascii=False, indent=2)
            )
        ]


async def handle_get_cache_stats(arguments: dict | None) -> list[types.TextContent]:
    """
    get_cache_statsツールの処理
    """
    try:
        logger.info("Getting cache statistics")
        config = get_config()
        
        if not config.cache_config.enabled:
            result = {
                "success": True,
                "cache_enabled": False,
                "message": "キャッシュシステムは無効になっています"
            }
        else:
            cache = get_cache()
            stats = cache.get_stats()
            
            result = {
                "success": True,
                "cache_enabled": True,
                "stats": stats,
                "message": "キャッシュ統計情報を取得しました"
            }
        
        logger.info("Cache statistics retrieved successfully")
        
        return [
            types.TextContent(
                type="text",
                text=json.dumps(result, ensure_ascii=False, indent=2)
            )
        ]
        
    except Exception as e:
        error_result = {
            "success": False,
            "error": str(e),
            "message": "キャッシュ統計の取得中にエラーが発生しました"
        }
        
        logger.error(f"Error getting cache stats: {e}", exc_info=True)
        
        return [
            types.TextContent(
                type="text",
                text=json.dumps(error_result, ensure_ascii=False, indent=2)
            )
        ]


async def handle_manage_presets(arguments: dict | None) -> list[types.TextContent]:
    """
    manage_presetsツールの処理
    """
    if not arguments:
        raise ValueError("引数が指定されていません")
    
    action = arguments.get("action", "list")
    preset_name = arguments.get("preset_name")
    preset_config = arguments.get("preset_config")
    
    try:
        logger.info(f"Managing presets: action={action}")
        config = get_config()
        
        if action == "list":
            presets = config.list_presets()
            result = {
                "success": True,
                "action": "list",
                "presets": {
                    name: {
                        "description": preset.description,
                        "voice": preset.voice,
                        "speed": preset.speed,
                        "response_format": preset.response_format,
                        "instructions": preset.instructions
                    }
                    for name, preset in presets.items()
                },
                "message": f"{len(presets)}個のプリセットが利用可能です"
            }
        
        elif action == "add":
            if not preset_name or not preset_config:
                raise ValueError("add操作にはpreset_nameとpreset_configが必要です")
            
            # プリセット作成
            preset = TTSPreset(
                name=preset_name,
                description=preset_config.get("description", "カスタムプリセット"),
                voice=preset_config["voice"],
                speed=preset_config["speed"],
                response_format=preset_config["response_format"],
                instructions=preset_config.get("instructions")
            )
            
            config.add_custom_preset(preset)
            
            result = {
                "success": True,
                "action": "add",
                "preset_name": preset_name,
                "message": f"プリセット '{preset_name}' を追加しました"
            }
        
        elif action == "remove":
            if not preset_name:
                raise ValueError("remove操作にはpreset_nameが必要です")
            
            removed = config.remove_custom_preset(preset_name)
            
            result = {
                "success": True,
                "action": "remove",
                "preset_name": preset_name,
                "removed": removed,
                "message": f"プリセット '{preset_name}' を削除しました" if removed else f"プリセット '{preset_name}' は見つかりませんでした"
            }
        
        else:
            raise ValueError(f"不明なアクション: {action}")
        
        logger.info(f"Preset management completed: {action}")
        
        return [
            types.TextContent(
                type="text",
                text=json.dumps(result, ensure_ascii=False, indent=2)
            )
        ]
        
    except Exception as e:
        error_result = {
            "success": False,
            "error": str(e),
            "message": "プリセット管理中にエラーが発生しました",
            "action": action
        }
        
        logger.error(f"Error managing presets: {e}", exc_info=True)
        
        return [
            types.TextContent(
                type="text",
                text=json.dumps(error_result, ensure_ascii=False, indent=2)
            )
        ]


async def handle_estimate_speech_info(arguments: dict | None) -> list[types.TextContent]:
    """
    estimate_speech_infoツールの処理
    """
    if not arguments:
        raise ValueError("引数が指定されていません")
    
    text = arguments.get("text")
    speed = arguments.get("speed", 1.0)
    
    if not text:
        raise ValueError("textパラメータが指定されていません")
    
    try:
        logger.info(f"Estimating speech info for text: {len(text)} chars")
        tts_client = TTSClient()
        
        # 推定情報の計算
        estimation = tts_client.estimate_generation_time(text, speed)
        
        # 長文分割情報
        from utils import split_long_text
        if estimation["is_long_text"]:
            chunks = split_long_text(text)
            chunk_info = {
                "total_chunks": len(chunks),
                "chunk_lengths": [len(chunk) for chunk in chunks],
                "average_chunk_length": sum(len(chunk) for chunk in chunks) / len(chunks)
            }
        else:
            chunk_info = {
                "total_chunks": 1,
                "chunk_lengths": [len(text)],
                "average_chunk_length": len(text)
            }
        
        result = {
            "success": True,
            "text_analysis": {
                "character_count": len(text),
                "word_count": len(text.split()),
                "is_long_text": estimation["is_long_text"],
                "requires_splitting": estimation["is_long_text"]
            },
            "time_estimation": {
                "speech_duration_seconds": estimation["speech_duration_seconds"],
                "speech_duration_formatted": f"{estimation['speech_duration_seconds']:.1f}秒",
                "estimated_generation_seconds": estimation["estimated_generation_seconds"],
                "generation_time_formatted": f"{estimation['estimated_generation_seconds']:.1f}秒"
            },
            "splitting_info": chunk_info,
            "parameters": {
                "speed": speed
            },
            "message": "音声情報の推定を完了しました"
        }
        
        logger.info("Speech estimation completed successfully")
        
        return [
            types.TextContent(
                type="text",
                text=json.dumps(result, ensure_ascii=False, indent=2)
            )
        ]
        
    except Exception as e:
        error_result = {
            "success": False,
            "error": str(e),
            "message": "音声情報の推定中にエラーが発生しました"
        }
        
        logger.error(f"Error estimating speech info: {e}", exc_info=True)
        
        return [
            types.TextContent(
                type="text",
                text=json.dumps(error_result, ensure_ascii=False, indent=2)
            )
        ]


async def main():
    """メイン実行関数"""
    logger.info("OpenAI TTS MCP Server (Phase 3) starting...")
    
    # 設定の初期化と検証
    try:
        config = get_config()
        logger.info(f"Configuration loaded: cache={'enabled' if config.cache_config.enabled else 'disabled'}")
        logger.info(f"Available presets: {len(config.list_presets())}")
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        sys.exit(1)
    
    # 環境変数の確認
    import os
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY environment variable is not set")
        sys.exit(1)
    
    logger.info("OpenAI API key configured")
    
    try:
        logger.info("Starting MCP server...")
        
        # Server クラスの create_initialization_options メソッドを使用
        initialization_options = app.create_initialization_options()
        logger.info("Initialization options created successfully")
        
        async with stdio_server() as (read_stream, write_stream):
            logger.info("Server streams established")
            await app.run(
                read_stream, 
                write_stream, 
                initialization_options
            )
            
    except Exception as e:
        logger.error(f"Failed to start server: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    """スクリプト実行時のエントリーポイント"""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)

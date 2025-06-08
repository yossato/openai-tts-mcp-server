#!/usr/bin/env python3
"""
OpenAI TTS MCP Server - Main Entry Point

Phase 2: 基本機能完成版
- 音声パラメータ選択機能（voice, speed, response_format）
- 音声再生機能（ファイル保存＋自動再生）
- list_voices補助ツール
- パラメータバリデーション強化
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

# セキュアなログ設定
# 標準エラー出力を使用してMCPクライアントからの漏洩を防ぐ
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr  # 標準エラー出力を使用（MCPプロトコルは標準入出力を使用）
)
logger = logging.getLogger(__name__)

# .envファイルのロード
try:
    from dotenv import load_dotenv
    
    # プロジェクトルートの.envファイルを読み込み
    project_root = Path(__file__).parent.parent
    env_path = project_root / ".env"
    load_dotenv(env_path)
    logger.info("Environment configuration loaded successfully")
    logger.debug(f"Environment file location: {env_path}")  # 機密情報はdebugレベル
    
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
    logger.info("TTS client and audio player imported successfully")
except ImportError as e:
    logger.error(f"Failed to import custom modules: {e}")
    sys.exit(1)

# MCPサーバーの初期化
app = Server(name="openai-tts", version="0.2.0")


@app.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """
    利用可能なツール一覧を返す
    Phase 2: generate_speech拡張 + list_voices追加
    """
    logger.info("Listing available tools")
    return [
        types.Tool(
            name="generate_speech",
            description=(
                "テキストを音声ファイルに変換します。OpenAI TTSを使用して高品質な音声を生成し、"
                "指定された形式でファイル保存や音声再生を行います。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "音声に変換するテキスト（最大4096文字）",
                        "maxLength": 4096
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
                "各音声の特徴や適用場面を確認できます。"
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "additionalProperties": False
            }
        )
    ]


@app.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
    """
    ツールの実行を処理
    Phase 2: 拡張されたgenerate_speech + 新しいlist_voices
    """
    logger.info(f"Tool called: {name} with arguments: {arguments}")
    
    if name == "generate_speech":
        return await handle_generate_speech(arguments)
    elif name == "list_voices":
        return await handle_list_voices(arguments)
    else:
        raise ValueError(f"Unknown tool: {name}")


async def handle_generate_speech(arguments: dict | None) -> list[types.TextContent]:
    """
    generate_speechツールの処理
    """
    if not arguments:
        raise ValueError("引数が指定されていません")
    
    # パラメータの取得（デフォルト値付き）
    text = arguments.get("text")
    voice = arguments.get("voice", "alloy")
    speed = arguments.get("speed", 1.0)
    response_format = arguments.get("response_format", "mp3")
    output_mode = arguments.get("output_mode", "file")
    
    if not text:
        raise ValueError("textパラメータが指定されていません")
    
    try:
        # TTSクライアントで音声生成
        logger.info(f"Generating speech - text: {text[:50]}..., voice: {voice}, speed: {speed}, format: {response_format}, mode: {output_mode}")
        tts_client = TTSClient()
        file_path = await tts_client.generate_speech(
            text=text,
            voice=voice,
            speed=speed,
            response_format=response_format
        )
        
        # 音声再生処理
        played = False
        if output_mode in ["play", "both"]:
            audio_player = AudioPlayer()
            played = await audio_player.play(file_path)
            if played:
                logger.info("Audio playback completed successfully")
            else:
                logger.warning("Audio playback failed")
        
        # output_mode: "play" の場合、再生後にファイルを削除
        if output_mode == "play":
            try:
                Path(file_path).unlink()  # ファイル削除
                logger.info(f"Temporary file deleted: {Path(file_path).name}")
                # レスポンス用にファイルパスを更新
                file_path = f"<temporary file - deleted after playback: {Path(file_path).name}>"
            except Exception as e:
                logger.warning(f"Failed to delete temporary file: {e}")
        
        # 古いファイルのクリーンアップ
        tts_client.cleanup_old_files()
        
        # 成功レスポンス
        result = {
            "success": True,
            "file_path": file_path,
            "message": f"音声ファイルを生成しました: {Path(file_path).name}",
            "parameters": {
                "text_length": len(text),
                "voice": voice,
                "speed": speed,
                "response_format": response_format,
                "output_mode": output_mode
            },
            "playback_status": {
                "attempted": output_mode in ["play", "both"],
                "successful": played if output_mode in ["play", "both"] else None
            }
        }
        
        logger.info(f"Speech generated successfully: {file_path}")
        
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
            "message": "音声生成中にエラーが発生しました",
            "parameters": {
                "text_length": len(text) if text else 0,
                "voice": voice,
                "speed": speed,
                "response_format": response_format,
                "output_mode": output_mode
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
    list_voicesツールの処理
    """
    try:
        logger.info("Listing available voices")
        tts_client = TTSClient()
        
        # 音声一覧と説明を取得
        voices = tts_client.get_supported_voices()
        formats = tts_client.get_supported_formats()
        
        result = {
            "success": True,
            "voices": voices,
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
            "usage_examples": [
                {
                    "description": "基本的な音声生成",
                    "parameters": {"text": "こんにちは"}
                },
                {
                    "description": "音声と速度を指定",
                    "parameters": {"text": "こんにちは", "voice": "nova", "speed": 1.2}
                },
                {
                    "description": "生成と同時に再生",
                    "parameters": {"text": "こんにちは", "output_mode": "both"}
                }
            ]
        }
        
        logger.info("Voice list generated successfully")
        
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


async def main():
    """メイン実行関数"""
    logger.info("OpenAI TTS MCP Server (Phase 2) starting...")
    
    # 環境変数の確認
    import os
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY environment variable is not set")
        sys.exit(1)
    
    logger.info("OpenAI API key configured")
    logger.debug(f"API key length: {len(api_key)}")  # 機密情報はdebugレベル
    
    try:
        logger.info("Starting MCP server...")
        
        # Server クラスの create_initialization_options メソッドを使用
        logger.info("Creating initialization options using server method...")
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

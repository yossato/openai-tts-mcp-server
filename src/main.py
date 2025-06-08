#!/usr/bin/env python3
"""
OpenAI TTS MCP Server - Main Entry Point

Phase 1: MVP実装 - 正常に動作する実装
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

# ログ設定を最初に行う
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# .envファイルのロード
try:
    from dotenv import load_dotenv
    
    # プロジェクトルートの.envファイルを読み込み
    project_root = Path(__file__).parent.parent
    env_path = project_root / ".env"
    load_dotenv(env_path)
    logger.info(f"Loaded environment from: {env_path}")
    
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
    logger.info("TTS client imported successfully")
except ImportError as e:
    logger.error(f"Failed to import TTS client: {e}")
    sys.exit(1)

# MCPサーバーの初期化
app = Server(name="openai-tts", version="0.1.0")


@app.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """利用可能なツール一覧を返す"""
    logger.info("Listing available tools")
    return [
        types.Tool(
            name="generate_speech",
            description="テキストを音声ファイルに変換します。OpenAI TTSを使用して高品質な音声を生成し、MP3ファイルとして保存します。",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "音声に変換するテキスト（最大4096文字）",
                        "maxLength": 4096
                    }
                },
                "required": ["text"],
                "additionalProperties": False
            }
        )
    ]


@app.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
    """ツールの実行を処理"""
    logger.info(f"Tool called: {name} with arguments: {arguments}")
    
    if name != "generate_speech":
        raise ValueError(f"Unknown tool: {name}")
    
    if not arguments:
        raise ValueError("引数が指定されていません")
    
    text = arguments.get("text")
    if not text:
        raise ValueError("textパラメータが指定されていません")
    
    try:
        # TTSクライアントで音声生成
        logger.info(f"Generating speech for text: {text[:50]}...")
        tts_client = TTSClient()
        file_path = await tts_client.generate_speech(text)
        
        # 古いファイルのクリーンアップ
        tts_client.cleanup_old_files()
        
        # 成功レスポンス
        result = {
            "success": True,
            "file_path": file_path,
            "message": f"音声ファイルを生成しました: {Path(file_path).name}",
            "text_length": len(text)
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
            "message": "音声生成中にエラーが発生しました"
        }
        
        logger.error(f"Error generating speech: {e}", exc_info=True)
        
        return [
            types.TextContent(
                type="text", 
                text=json.dumps(error_result, ensure_ascii=False, indent=2)
            )
        ]


async def main():
    """メイン実行関数"""
    logger.info("OpenAI TTS MCP Server (Phase 1) starting...")
    
    # 環境変数の確認
    import os
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY environment variable is not set")
        sys.exit(1)
    
    logger.info(f"OPENAI_API_KEY loaded (length: {len(api_key)})")
    
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

# Phase 1 動作確認手順

## 前提条件
- OpenAI APIキーが.envファイルに設定済み
- 仮想環境に必要なパッケージがインストール済み
- Claude Desktopの設定ファイルにMCPサーバーが追加済み

## 1. 依存関係のインストール

```bash
cd /Users/yoshiaki/Projects/openai-tts-mcp-server
source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Claude Desktop設定

`~/Library/Application Support/Claude/claude_desktop_config.json` に以下を追加：

```json
{
  "mcpServers": {
    "openai-tts": {
      "command": "/Users/yoshiaki/Projects/openai-tts-mcp-server/.venv/bin/python",
      "args": ["/Users/yoshiaki/Projects/openai-tts-mcp-server/src/main.py"],
      "cwd": "/Users/yoshiaki/Projects/openai-tts-mcp-server"
    }
  }
}
```

## 3. Claude Desktop再起動

設定ファイルを編集した後、Claude Desktopを完全に終了して再起動してください。

## 4. Phase 1 動作テスト

Claude Desktopで以下のテストを実行：

### テスト 1: 基本的な音声生成
```
音声を生成してください: "こんにちは、世界！"
```

**期待される結果:**
- 音声ファイルが生成される
- ファイルパスが返される
- 成功メッセージが表示される

### テスト 2: 日本語長文
```
以下のテキストを音声にしてください: "今日は良い天気ですね。OpenAI TTSを使った音声生成のテストを行っています。"
```

### テスト 3: 英語テキスト
```
英語で音声を生成してください: "Hello, this is a test of OpenAI TTS integration."
```

### テスト 4: エラーハンドリング
```
空のテキストで音声を生成してください: ""
```

**期待される結果:** 適切なエラーメッセージが表示される

## 5. 生成されたファイルの確認

音声ファイルは `/tmp/openai_tts_mcp/` ディレクトリに保存されます。
Finderで確認するか、以下のコマンドで確認できます：

```bash
ls -la /tmp/openai_tts_mcp/
```

## 6. トラブルシューティング

### MCPサーバーが認識されない場合
1. Claude Desktopを完全に終了して再起動
2. 設定ファイルのパスを確認
3. Python仮想環境のパスを確認

### APIエラーが発生する場合
1. .envファイルのOPENAI_API_KEYを確認
2. OpenAI APIの利用可能状況を確認
3. 課金設定を確認

### ファイルが生成されない場合
1. /tmpディレクトリの書き込み権限を確認
2. ディスク容量を確認

## Phase 1 成功基準

以下が全て達成されればPhase 1完了：

- [x] MCPクライアント（Claude Desktop）から接続可能
- [x] テキストを渡すと音声ファイルが生成される
- [x] 生成されたファイルパスが返却される  
- [x] エラー時に適切なエラーメッセージが表示される
- [x] 日本語・英語両方のテキストで動作する

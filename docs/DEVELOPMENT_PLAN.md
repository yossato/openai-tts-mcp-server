# OpenAI TTS MCP Server

OpenAI TTS APIを活用した音声生成MCPサーバーの開発プロジェクト

## プロジェクト概要

MCPサーバーとして動作し、クライアントからのテキスト入力に対してOpenAI TTS APIを使用して高品質な音声を生成・再生する機能を提供します。リアルタイム性と高品質を両立した音声合成ソリューションです。

## 開発環境

### 必要な環境
- macOS
- Python 3.8+
- venv環境推奨

### セットアップ

```bash
# システム依存関係のインストール
brew install portaudio

# Python依存関係のインストール
pip install openai
pip install sounddevice
```

### 環境変数設定

プロジェクトルートに `.env` ファイルを作成：
```
OPENAI_API_KEY=your_openai_api_key_here
```

## 段階的開発計画

### Phase 1: MVP (Minimum Viable Product)

**目標**: 動作する最小限のMCPサーバー

**実装機能**:
- 基本的なMCPサーバー構造
- 単一ツール `generate_speech`
- 固定パラメータでのOpenAI TTS呼び出し
- ファイル出力のみ

**固定設定**:
- voice: "alloy"
- response_format: "mp3"
- speed: 1.0
- output_mode: "file"

**成功条件**:
- MCPクライアントから接続可能
- テキストを渡すと音声ファイルが生成される
- 生成されたファイルパスが返却される
- エラー時に適切なエラーメッセージ

### Phase 2: 基本機能完成

**目標**: 実用的な機能セット

**実装機能**:
- 音声パラメータの選択機能
- 音声再生機能の追加
- 補助ツール `list_voices` の実装
- 基本的なバリデーション

**パラメータ拡張**:
```
generate_speech:
- text: string (必須)
- voice: "alloy"|"echo"|"fable"|"onyx"|"nova"|"shimmer"|"coral" (オプション)
- speed: number (0.25-4.0、オプション)
- output_mode: "file"|"play"|"both" (オプション)

list_voices:
- パラメータなし
- 利用可能な音声リストと特徴説明を返却
```

**成功条件**:
- 複数の音声から選択可能
- ファイル出力と再生の両方が動作
- `list_voices`ツールが機能
- 不正パラメータ時の適切な処理

### Phase 3: 高度な機能

**目標**: プロダクション品質

**実装機能**:
- キャッシュ機能（LRUキャッシュシステム）
- プリセット機能
- 詳細な音声制御（instructions）
- パフォーマンス最適化
- 設定管理の拡張

**最終パラメータ**:
```
generate_speech:
- text: string (必須)
- voice: string (OpenAI TTS対応音声)
- speed: number (0.25-4.0)
- instructions: string (音声の特徴指示)
- preset: "cheerful_female"|"calm_male"|"professional"
- response_format: "mp3"|"wav"|"opus"
- output_mode: "file"|"play"|"both"

get_voice_preview:
- voice: string (必須)
- サンプル音声を返却
```

**成功条件**:
- 同一リクエストの2回目が高速化（キャッシュ効果）
- プリセット指定で期待される音声特徴
- 長文処理（1000文字以上）が適切に処理
- 設定ファイルでデフォルト値変更可能

## 技術的制約と対応

### OpenAI TTS API制限

**文字数制限**: 1リクエスト4096文字

**対応策**:
- 4096文字を超える場合は自動分割
- 文章の区切り（句点、改行）で分割
- 分割された音声ファイルの結合または連続再生

**実装方針**:
```python
def split_text(text: str, max_length: int = 4000) -> List[str]:
    # 文章の自然な区切りで分割
    # 4000文字を目安に、句点や改行で分割
    pass

async def generate_long_speech(text: str, **params) -> List[str]:
    # 長文を分割して複数のAPIコールで処理
    # 結果をファイルリストまたは結合ファイルとして返却
    pass
```

## アーキテクチャ設計

### コアコンポーネント

1. **MCP Server基本構造**: ツール定義とリクエスト処理
2. **OpenAI API統合**: 非同期クライアント管理とエラーハンドリング
3. **一時ファイル管理**: TTLベースの自動削除システム
4. **音声再生システム**: LocalAudioPlayer統合
5. **キャッシュシステム**: ハッシュベースのLRUキャッシュ
6. **設定管理**: 環境変数と設定ファイルの統合管理

### エラーハンドリング戦略

**API関連エラー**:
- 認証エラー → 設定ガイダンス
- レート制限 → リトライ機能
- 課金制限 → 適切なエラーメッセージ

**ローカル処理エラー**:
- 音声再生デバイス不可 → ファイルモードにフォールバック
- ディスク容量不足 → ストリーミングモードを推奨

## 開発ガイドライン

### ファイル構成
```
openai-tts-mcp-server/
├── README.md
├── docs/                     # ドキュメント類 (このファイルを含む)
├── .env                      # 環境変数（gitignore対象）
├── .gitignore
├── requirements.txt          # Python依存関係
├── src/
│   ├── __init__.py
│   ├── main.py              # MCPサーバーエントリーポイント
│   ├── tts_client.py        # OpenAI TTS API クライアント
│   ├── audio_player.py      # 音声再生機能
│   ├── cache.py             # キャッシュシステム
│   ├── config.py            # 設定管理
│   └── utils.py             # ユーティリティ関数
└── tests/
    ├── __init__.py
    ├── test_tts_client.py
    ├── test_audio_player.py
    └── test_integration.py
```

### 実装の優先順位

1. **Phase 1**: 基本的なMCP構造とOpenAI API統合
2. **Phase 2**: パラメータ拡張と音声再生機能
3. **Phase 3**: 最適化機能（キャッシュ、プリセット等）

### テスト戦略

各Phase完了時に以下をテスト：

**Phase 1**:
- MCPクライアント接続テスト
- 基本的な音声生成テスト
- エラーハンドリングテスト

**Phase 2**:
- 全パラメータでの動作テスト
- 音声再生機能テスト
- バリデーション機能テスト

**Phase 3**:
- キャッシュ効果測定
- 長文処理テスト
- パフォーマンステスト

## 使用例

### Phase 1 (MVP)
```json
{
  "tool": "generate_speech",
  "parameters": {
    "text": "こんにちは、世界！"
  }
}
```

### Phase 2 (基本機能)
```json
{
  "tool": "generate_speech",
  "parameters": {
    "text": "こんにちは、世界！",
    "voice": "nova",
    "speed": 1.2,
    "output_mode": "both"
  }
}
```

### Phase 3 (高度な機能)
```json
{
  "tool": "generate_speech",
  "parameters": {
    "text": "重要な発表があります。",
    "preset": "professional",
    "instructions": "フォーマルで権威のある声で話してください"
  }
}
```

## 今後の拡張可能性

- 多言語対応の強化
- 音声効果（エコー、リバーブ等）の追加
- バッチ処理機能
- Webhook連携
- 音声ファイルの永続化ストレージ連携

---

**開発開始日**: 2025年6月8日  
**最終更新**: 2025年6月8日

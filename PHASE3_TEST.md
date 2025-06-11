# 🧪 Phase 3 テスト手順書

OpenAI TTS MCP Server Phase 3（プロダクション品質版）の包括的テスト手順

## 📋 テスト環境準備

### 必要な環境
```bash
# 依存関係のインストール
pip install -r requirements.txt

# オプション: 音声ファイル結合機能
pip install pydub

# macOSの場合
brew install ffmpeg
```

### 環境変数設定
```bash
# .envファイルに設定
OPENAI_API_KEY=your_openai_api_key_here
```

### MCPクライアント接続
```bash
# サーバー起動
python src/main.py

# 別ターミナルでデバッグクライアント（オプション）
python debug_server.py
```

## 🎯 Phase 3 新機能テスト

### 1. キャッシュシステムテスト

#### 1.1 キャッシュ統計確認
```json
{
  "tool": "get_cache_stats",
  "parameters": {}
}
```
**期待結果**: キャッシュが有効で、初期状態の統計情報表示

#### 1.2 同一リクエストのキャッシュ効果テスト
```json
{
  "tool": "generate_speech",
  "parameters": {
    "text": "キャッシュテスト用のテキストです。",
    "voice": "alloy",
    "enable_cache": true
  }
}
```
**1回目実行**: 通常の生成時間  
**2回目実行**: 高速化（キャッシュヒット）を確認

#### 1.3 キャッシュ統計の変化確認
```json
{
  "tool": "get_cache_stats",
  "parameters": {}
}
```
**期待結果**: ヒット数やエントリー数の増加

### 2. プリセット機能テスト

#### 2.1 プリセット一覧確認
```json
{
  "tool": "manage_presets",
  "parameters": {
    "action": "list"
  }
}
```
**期待結果**: 6個の組み込みプリセット表示

#### 2.2 プリセット使用テスト
```json
{
  "tool": "generate_speech",
  "parameters": {
    "text": "これはプロフェッショナルなプリセットのテストです。",
    "preset": "professional",
    "output_mode": "both"
  }
}
```
**期待結果**: echo音声、FLAC形式での生成・再生

#### 2.3 カスタムプリセット追加
```json
{
  "tool": "manage_presets",
  "parameters": {
    "action": "add",
    "preset_name": "test_custom",
    "preset_config": {
      "description": "テスト用カスタムプリセット",
      "voice": "coral",
      "speed": 1.3,
      "response_format": "wav",
      "instructions": "テスト用の指示"
    }
  }
}
```
**期待結果**: カスタムプリセット追加成功

#### 2.4 カスタムプリセット使用
```json
{
  "tool": "generate_speech",
  "parameters": {
    "text": "カスタムプリセットのテストです。",
    "preset": "test_custom"
  }
}
```
**期待結果**: coral音声、1.3倍速、WAV形式で生成

#### 2.5 カスタムプリセット削除
```json
{
  "tool": "manage_presets",
  "parameters": {
    "action": "remove",
    "preset_name": "test_custom"
  }
}
```
**期待結果**: カスタムプリセット削除成功

### 3. 長文処理テスト

#### 3.1 音声情報推定
```json
{
  "tool": "estimate_speech_info",
  "parameters": {
    "text": "これは非常に長いテキストです。文字数が4096文字を超える場合、システムは自動的にテキストを適切な区切りで分割し、複数の音声ファイルを生成します。この機能により、長い文書や記事なども音声化することが可能になります。各分割されたテキストは個別に処理され、最終的には連続再生や結合ファイルとして提供されます。",
    "speed": 1.0
  }
}
```
**期待結果**: テキスト解析と推定時間表示

#### 3.2 長文音声生成（分割ファイル）
```json
{
  "tool": "generate_speech",
  "parameters": {
    "text": "長文テストの開始です。これは4096文字の制限を超えるテキストの処理をテストするためのものです。システムは自動的にテキストを自然な区切りで分割し、複数の音声ファイルを生成します。この分割処理により、非常に長い文書や記事も適切に音声化することができます。分割された各部分は個別に処理され、最終的には連続再生や単一ファイルへの結合が可能です。この機能により、ユーザーは文字数制限を気にすることなく、長いコンテンツを音声化できます。各チャンクは文章の自然な区切り（句読点、段落等）で分割されるため、聞きやすい音声が生成されます。さらに、キャッシュシステムにより、同一テキストの再処理は高速化されます。プリセット機能と組み合わせることで、一貫した音声特徴での長文処理も可能です。このように、Phase 3では実用的な長文処理機能が実装されています。",
    "voice": "nova",
    "merge_long_audio": false,
    "output_mode": "file"
  }
}
```
**期待結果**: 複数ファイルの生成

#### 3.3 長文音声生成（結合ファイル）
```json
{
  "tool": "generate_speech",
  "parameters": {
    "text": "長文結合テストです。このテキストは複数のチャンクに分割されますが、merge_long_audio オプションにより、最終的には単一の音声ファイルに結合されます。この機能により、長い文書でも途切れることなく連続した音声として再生できます。結合処理にはpydubライブラリが使用され、高品質な音声結合が実現されます。",
    "voice": "shimmer",
    "merge_long_audio": true,
    "output_mode": "both"
  }
}
```
**期待結果**: 結合された単一ファイルの生成・再生

### 4. 音声プレビュー機能テスト

#### 4.1 各音声のプレビュー
```json
{
  "tool": "get_voice_preview",
  "parameters": {
    "voice": "coral"
  }
}
```
**期待結果**: coral音声のサンプル生成・再生

#### 4.2 カスタムサンプルテキスト
```json
{
  "tool": "get_voice_preview",
  "parameters": {
    "voice": "onyx",
    "sample_text": "これはカスタムサンプルテキストです。音声の特徴を確認してください。"
  }
}
```
**期待結果**: onyx音声でカスタムテキストの再生

### 5. 詳細音声制御テスト

#### 5.1 instructions機能
```json
{
  "tool": "generate_speech",
  "parameters": {
    "text": "重要なお知らせがあります。",
    "voice": "echo",
    "instructions": "権威があり、フォーマルな口調で話してください",
    "output_mode": "both"
  }
}
```
**期待結果**: 指示に従った音声特徴での生成

#### 5.2 プリセットとinstructionsの組み合わせ
```json
{
  "tool": "generate_speech",
  "parameters": {
    "text": "こんにちは、皆さん！",
    "preset": "energetic",
    "instructions": "さらに元気よく、笑顔が伝わるように話してください",
    "output_mode": "play"
  }
}
```
**期待結果**: プリセット＋追加指示による音声生成

### 6. 高度な機能統合テスト

#### 6.1 全パラメータ指定テスト
```json
{
  "tool": "generate_speech",
  "parameters": {
    "text": "これは全機能を統合したテストです。キャッシュ、音声設定、詳細制御、すべてが組み合わされています。",
    "voice": "fable",
    "speed": 1.1,
    "response_format": "flac",
    "output_mode": "both",
    "instructions": "温かみがあり、ストーリーテラーのように表現豊かに話してください",
    "enable_cache": true
  }
}
```
**期待結果**: 全パラメータでの正常動作

#### 6.2 リスト機能の更新確認
```json
{
  "tool": "list_voices",
  "parameters": {}
}
```
**期待結果**: Phase 3の新機能情報を含む詳細な一覧表示

## 🔧 エラーハンドリングテスト

### 7.1 不正プリセット指定
```json
{
  "tool": "generate_speech",
  "parameters": {
    "text": "テスト",
    "preset": "invalid_preset"
  }
}
```
**期待結果**: 適切なエラーメッセージと利用可能プリセット一覧

### 7.2 組み込みプリセット上書き試行
```json
{
  "tool": "manage_presets",
  "parameters": {
    "action": "add",
    "preset_name": "professional",
    "preset_config": {
      "description": "上書きテスト",
      "voice": "alloy",
      "speed": 1.0,
      "response_format": "mp3"
    }
  }
}
```
**期待結果**: 組み込みプリセット保護のエラーメッセージ

### 7.3 存在しないプリセット削除
```json
{
  "tool": "manage_presets",
  "parameters": {
    "action": "remove",
    "preset_name": "nonexistent_preset"
  }
}
```
**期待結果**: プリセットが見つからない旨のメッセージ

## 📊 パフォーマンステスト

### 8.1 キャッシュ効果測定
同一パラメータで複数回実行し、2回目以降の高速化を確認

### 8.2 長文処理時間測定
異なる長さのテキストで処理時間を比較

### 8.3 並行処理性能
複数の長文チャンクの並行処理時間を測定

## ✅ 成功基準

### Phase 3成功条件:
- [ ] 全ツール（6個）が正常動作
- [ ] キャッシュシステムでの高速化確認
- [ ] プリセット機能の完全動作
- [ ] 長文の自動分割・処理成功
- [ ] 音声ファイル結合機能動作
- [ ] エラーハンドリングの適切性
- [ ] 設定ファイルの永続化動作
- [ ] 新機能と既存機能の互換性

### 品質指標:
- **キャッシュヒット率**: 2回目以降80%以上
- **長文処理**: 10,000文字以上の処理成功
- **エラー処理**: 不正入力での適切なエラーメッセージ
- **音声品質**: 全プリセットでの明確な音声特徴差

## 📝 テスト実行ログ

### テスト実行日: ___________
### 実行者: ___________

| テスト項目 | 結果 | 備考 |
|-----------|------|------|
| キャッシュ統計確認 | ⬜ | |
| キャッシュ効果測定 | ⬜ | |
| プリセット一覧表示 | ⬜ | |
| プリセット使用 | ⬜ | |
| カスタムプリセット管理 | ⬜ | |
| 長文情報推定 | ⬜ | |
| 長文分割処理 | ⬜ | |
| 長文結合処理 | ⬜ | |
| 音声プレビュー | ⬜ | |
| instructions機能 | ⬜ | |
| 統合機能テスト | ⬜ | |
| エラーハンドリング | ⬜ | |

### 総合評価: ⬜ 成功 / ⬜ 部分成功 / ⬜ 失敗

---

**Phase 3実装完了条件**: 上記テストの90%以上成功

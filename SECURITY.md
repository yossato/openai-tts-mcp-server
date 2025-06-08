# 🔒 セキュリティ対策ガイド

## 📋 概要

Phase 2実装において、MCPサーバーのログ出力に関するセキュリティリスクが特定され、適切な対策を実施しました。

## 🚨 特定されたリスク

### 問題1: ログ出力先の脆弱性
**リスク**: MCPプロトコルは標準入出力を使用するため、標準出力に送られるログがクライアントに漏洩する可能性

**影響**: 
- 機密情報（ファイルパス、APIキー長等）がMCPクライアントから読み取り可能
- セキュリティ情報の間接的な漏洩

### 問題2: 機密情報の詳細ログ出力
**リスク**: `.env`ファイルパスやAPIキー長などの情報を INFO レベルで出力

**影響**:
- 攻撃者にとって有用な情報の提供
- システム構成の推測を容易にする

## ✅ 実施した対策

### 1. ログ出力先の変更

**修正前（危険）**:
```python
logging.basicConfig(level=logging.INFO)  # 標準出力（危険）
```

**修正後（安全）**:
```python
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr  # 標準エラー出力（安全）
)
```

**効果**: MCPプロトコルが使用する標準入出力とは分離され、クライアントからの漏洩を防止

### 2. ログ内容のセキュア化

**修正前（危険）**:
```python
logger.info(f"Loaded environment from: {env_path}")
logger.info(f"OPENAI_API_KEY loaded (length: {len(api_key)})")
```

**修正後（安全）**:
```python
logger.info("Environment configuration loaded successfully")
logger.info("OpenAI API key configured")

# 機密情報はDEBUGレベル（本番では出力されない）
logger.debug(f"Environment file location: {env_path}")
logger.debug(f"API key length: {len(api_key)}")
```

**効果**: 
- 一般ユーザーには汎用的な成功メッセージのみ表示
- 開発者は DEBUG レベルで詳細情報を確認可能

### 3. 開発者向けデバッグ機能

**新規追加**: `debug_server.py`
```python
# 開発時のみ使用するデバッグモード
python debug_server.py  # 詳細ログ+ファイル出力
```

**機能**:
- 詳細ログの`debug.log`ファイル出力
- 開発者専用の診断情報表示
- 本番環境とは完全に分離

### 4. ログファイルのセキュリティ

**`.gitignore`に追加**:
```
debug.log
*.log
```

**効果**: 機密情報を含む可能性のあるログファイルをバージョン管理から除外

## 🎯 運用ガイドライン

### 本番環境での使用

```bash
# 通常起動（INFOレベル、標準エラー出力）
python src/main.py
```

**ログレベル**: INFO以上のみ出力
**出力先**: 標準エラー（MCPクライアントから分離）
**機密情報**: 出力されない

### 開発・デバッグ時

```bash
# デバッグモード起動（DEBUGレベル、ファイル出力）
python debug_server.py
```

**ログレベル**: DEBUG以上すべて出力
**出力先**: ファイル（`debug.log`）+ 標準エラー
**機密情報**: ファイル内でのみ確認可能

### ログレベルの制御

**環境変数での制御**（将来的な拡張）:
```bash
# 本番環境
export LOG_LEVEL=WARNING

# 開発環境  
export LOG_LEVEL=DEBUG
```

## 🔍 セキュリティチェックリスト

- [x] **ログ出力先**: 標準エラー出力に変更済み
- [x] **機密情報**: DEBUGレベルに移動済み
- [x] **開発者ツール**: 分離されたデバッグモード提供
- [x] **ファイルセキュリティ**: ログファイルを`.gitignore`に追加
- [x] **ドキュメント**: セキュリティ対策の文書化

## 📈 今後の改善案

1. **ログローテーション**: 長期運用時のログファイル管理
2. **ログ暗号化**: 機密情報を含むログの暗号化
3. **監査ログ**: セキュリティイベントの専用ログ
4. **アクセス制御**: ログファイルの権限設定自動化

---

**セキュリティ対策実施日**: 2025年6月8日  
**対策レベル**: Phase 2対応完了

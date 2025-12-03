# ログ機能追加ドキュメント

## 変更内容

デバッグのため、実行プロセスを全てカレントディレクトリの `result.txt` に出力するように仕様変更しました。

## 追加されたファイル

### 1. `logger.py`
- 標準出力とファイルの両方にログを出力する `DualLogger` クラスを実装
- タイムスタンプ付きでログを記録
- INFO、DEBUG、WARNING、ERROR の各ログレベルをサポート
- グローバルロガーインスタンスによる一元管理

## 変更されたファイル

### 2. `wasabi_downloader.py`
- `logger` モジュールをインポート
- `main()` 関数の開始時にロガーを初期化（`logger.init_logger(mode='w')`）
- 全ての `print()` 文を `logger.log()` 呼び出しに置き換え
- 詳細なデバッグログを追加（コマンド、引数、設定パス、バケット名など）
- `finally` ブロックでロガーを確実にクローズ

### 3. `s3_handler.py`
- `logger` モジュールをインポート
- 各関数に詳細なデバッグログを追加：
  - `get_s3_client()`: S3クライアント作成プロセス、MFA認証、SSL設定
  - `get_object_info()`: オブジェクト情報の取得
  - `list_objects_in_prefix()`: オブジェクトリスト、ページ数、合計サイズ
  - `list_object_versions_at_timestamp()`: バージョン情報、処理エントリ数
  - `download_file()`: ダウンロードの開始と完了
  - `download_objects()`: バッチダウンロードの統計（成功数、エラー数）

### 4. `config_loader.py`
- `logger` モジュールをインポート
- `load_config()` 関数に詳細なデバッグログを追加：
  - CSVファイルの読み込み
  - 設定の検証
  - MFA/SSL設定の確認

## 使用方法

通常通りコマンドを実行すると、自動的に `result.txt` にログが記録されます：

```bash
python wasabi_downloader.py list_files --source path/to/folder
```

実行後、カレントディレクトリに `result.txt` が作成され、以下の情報が記録されます：
- タイムスタンプ付きの全ての実行ログ
- DEBUG情報（詳細な処理内容）
- INFO情報（通常の進行状況）
- WARNING情報（警告）
- ERROR情報（エラー）

## ログファイルの形式

```
================================================================================
Wasabi Downloader Execution Log
Started at: 2025-12-03 15:10:09
================================================================================

[2025-12-03 15:10:09.123] INFO: Starting command: list_files
[2025-12-03 15:10:09.124] DEBUG: Arguments: {'command': 'list_files', 'source': 'path/to/folder'}
[2025-12-03 15:10:09.125] INFO: Loading configuration from: c:\gemini\BC1\config.csv
...
================================================================================
Execution ended at: 2025-12-03 15:10:15
================================================================================
```

## メリット

1. **デバッグの容易化**: 全ての実行プロセスが時系列で記録される
2. **トラブルシューティング**: エラー発生時の詳細な情報を確認可能
3. **監査証跡**: 実行履歴の記録
4. **パフォーマンス分析**: タイムスタンプから処理時間を計算可能

## PyInstallerでのコンパイル

ログ機能を含めてコンパイルする場合、`logger.py` も自動的に含まれます：

```bash
pyinstaller --onefile --name wasabi_downloader wasabi_downloader.py
```

コンパイル後も同様に、実行時に `result.txt` が自動生成されます。

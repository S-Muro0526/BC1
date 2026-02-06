# Wasabi Hot Cloud Storage ファイルダウンロードツール

## 1. 概要

本ツールは、Wasabi Hot Cloud Storage (Wasabi) からファイルをダウンロードするためのPython製コマンドラインツールです。

主な機能として、単一ファイルのダウンロード、ディレクトリ単位の一括ダウンロード、そして指定した過去の時点でのファイルバージョンの一括取得を提供します。設定は外部の`config.env`ファイルから読み込まれ、オプションでMFA（多要素認証）にも対応しています。

## 2. 必要なライブラリ

本ツールを実行するには、以下のPythonライブラリが必要です。

- `boto3`: AWS SDK for Python (WasabiはS3互換APIを提供)
- `tqdm`: ダウンロードの進捗状況をプログレスバーで表示するために使用

以下のコマンドで、必要なライブラリをすべてインストールできます。

```bash
pip install -r requirements.txt
```

## 3. セットアップ

ツールの実行前に、`config.env`ファイルに必要な情報を設定する必要があります。

```env
aws_access_key_id=YOUR_ACCESS_KEY
aws_secret_access_key=YOUR_SECRET_KEY
endpoint_url=https://s3.wasabisys.com
bucket_name=YOUR_BUCKET_NAME
mfa_serial_number=YOUR_MFA_SERIAL_NUMBER_ARN (optional)
ssl_verify_path= (optional)
sts_endpoint_url=https://sts.wasabisys.com
```

| key | 説明 |
| :--- | :--- |
| `aws_access_key_id` | Wasabiアカウントのアクセスキーを入力します。 |
| `aws_secret_access_key` | Wasabiアカウントのシークレットアクセスキーを入力します。 |
| `endpoint_url` | WasabiのS3互換APIエンドポイントURLです。通常はこのままで問題ありません。 |
| `bucket_name` | ダウンロード対象のファイルが格納されているバケット名を入力します。 |
| `mfa_serial_number` | **【任意】** MFA認証を行う場合、IAMユーザーに紐づくMFAデバイスのARNを入力します。不要な場合は空欄のままにしてください。 |
| `ssl_verify_path` | **【任意】** プロキシ環境下などで、カスタムSSL証明書（`.pem`ファイルなど）のパスを指定します。 |

### 3.1. MFA認証について

`config.env` ファイルで `mfa_serial_number` に有効なARNを設定している場合、他のコマンド（`download_file`, `list_files` など）を実行する前に、`mfa` コマンドを実行して認証を行う必要があります。

認証を行うと一時的なセッションが保存され、そのセッションが有効な間（通常数時間）は他のコマンドをMFA入力なしで実行できます。セッションが期限切れになった場合や、まだ認証を行っていない状態で他のコマンドを実行すると、エラーが表示されます。

詳細な手順については、「4.1. MFA認証の実行 (`mfa`)」を参照してください。

### 3.2. プロキシ環境とSSL証明書

企業内プロキシなどを経由して通信を行う際、SSLインスペクション（通信の復号・再暗号化）が行われることがあります。
このような環境では、`SSL validation failed` というエラーが発生する場合があります。

この問題を解決するには、プロキシが使用するカスタムSSL証明書（通常は`.pem`形式）のフルパスを`config.env`の`ssl_verify_path`に設定してください。

**設定例:**
```env
ssl_verify_path=C:\certs\my-proxy-ca.pem
```

## 4. 使用方法

コマンドプロンプトやターミナルから`wasabi_downloader.py`を実行します。

### 4.1. MFA認証の実行 (`mfa`)

MFAが設定されている場合、最初にこのコマンドを実行してセッションを確立します。

**コマンド例:**
```bash
python wasabi_downloader.py mfa
```

実行すると `Enter MFA Token:` と表示されるので、認証アプリの6桁のコードを入力してください。認証に成功すると `.mfa_session.json` ファイルが作成され、以降のコマンドが利用可能になります。

### 4.2. 単一ファイルのダウンロード (`download_file`)

Wasabi上の特定のファイル1つをダウンロードします。

**コマンド例:**
```bash
python wasabi_downloader.py download_file --source "path/to/remote/file.txt" --destination "C:\local\path\to\save\file.txt"
```

**引数:**
- `--source`: **[必須]** ダウンロード対象のWasabi上のオブジェクトキー（ファイルパス）。
- `--destination`: **[任意]** ローカル環境での保存先ファイルパス。指定しない場合、実行ディレクトリ配下に`Download`フォルダが作成され, その中に保存されます。

### 4.3. ディレクトリの一括ダウンロード (`download_dir`)

Wasabi上の特定のディレクトリ（プレフィックス）配下のすべてのファイルを一括でダウンロードします。

**コマンド例:**
```bash
# 特定のディレクトリをダウンロード
python wasabi_downloader.py download_dir --source "path/to/remote_dir/"

# バケット全体をダウンロード
python wasabi_downloader.py download_dir
```

**引数:**
- `--source`: **[任意]** ダウンロード対象のディレクトリパス。指定しない場合はバケット全体が対象となります。
- `--destination`: **[任意]** ローカル環境での保存先ディレクトリパス。指定しない場合、実行ディレクトリ配下に`Download`フォルダが作成され、その中に保存されます。

### 4.4. 特定時点のバージョン一括ダウンロード (`download_versioned`)

指定された日付の時点で存在していた、各ファイルの最新バージョンをすべてダウンロードします。(※対象バケットでバージョニングが有効になっている必要があります)

**コマンド例:**
```bash
# 2024年1月1日時点の状態でバケット全体をダウンロード
python wasabi_downloader.py download_versioned --timestamp "20240101"

# 特定のディレクトリを対象
python wasabi_downloader.py download_versioned --timestamp "20240101" --source "path/to/remote_dir/"
```

**引数:**
- `--timestamp`: **[必須]** 取得したい過去の時点を示す日付。フォーマットは`YYYYMMDD`。
- `--source`: **[任意]** ダウンロード対象のディレクトリパス。指定しない場合はバケット全体が対象となります。
- `--destination`: **[任意]** ローカル保存先ディレクトリパス。指定しない場合、実行ディレクトリ配下に`Download`フォルダが作成され、その中に保存されます。

### 4.5. ファイルの再帰的リスト表示 (`list_files`)

Wasabi上の特定のディレクトリ（プレフィックス）配下、またはバケット全体のすべてのファイルキーを再帰的にリスト表示します。

**コマンド例:**
```bash
# 特定のディレクトリのファイルをリスト表示
python wasabi_downloader.py list_files --source "path/to/remote_dir/"

# バケット全体のファイルをリスト表示
python wasabi_downloader.py list_files
```

**引数:**
- `--source`: **[任意]** リスト表示対象のディレクトリパス。指定しない場合はバケット全体が対象となります。

## 5. デバッグログ機能

### 5.1. 概要

全ての実行プロセスは、自動的にカレントディレクトリの `result.txt` ファイルに記録されます。
このログファイルには、実行時のタイムスタンプ付きで詳細な情報が保存されるため、トラブルシューティングやデバッグに役立ちます。

### 5.2. ログの内容

`result.txt` には以下の情報が記録されます：

- **実行開始・終了時刻**: プログラムの開始と終了のタイムスタンプ
- **タイムスタンプ付きログ**: 各処理のタイムスタンプ（ミリ秒まで）
- **ログレベル**:
  - `INFO`: 一般的な情報（コマンド開始、接続成功など）
  - `DEBUG`: 詳細なデバッグ情報（設定読み込み、S3クライアント作成、オブジェクト処理など）
  - `WARNING`: 警告（ファイルダウンロード失敗など）
  - `ERROR`: エラー情報（認証失敗、設定エラーなど）

### 5.3. ログファイルの例

```
================================================================================
Wasabi Downloader Execution Log
Started at: 2025-12-03 15:22:46
================================================================================

[2025-12-03 15:22:47.001] INFO: Starting command: list_files
[2025-12-03 15:22:47.002] DEBUG: Arguments: {'command': 'list_files', 'source': ''}
[2025-12-03 15:22:47.002] INFO: Loading configuration from: C:\gemini\BC1\config.env
[2025-12-03 15:22:47.002] DEBUG: Loading configuration from: C:\gemini\BC1\config.env
[2025-12-03 15:22:47.047] DEBUG: ENV file loaded successfully, 7 entries found
[2025-12-03 15:22:47.047] DEBUG: Configuration loaded successfully
[2025-12-03 15:22:47.047] Connecting to Wasabi...
[2025-12-03 15:22:47.047] DEBUG: Creating S3 client session
[2025-12-03 15:22:49.307] DEBUG: S3 client created for endpoint: https://s3.wasabisys.com
[2025-12-03 15:22:49.307] Connection successful.
...

================================================================================
Execution ended at: 2025-12-03 15:22:57
================================================================================
```

### 5.4. ログファイルの活用

- **トラブルシューティング**: エラー発生時に詳細な情報を確認できます
- **パフォーマンス分析**: タイムスタンプから各処理の所要時間を計算できます
- **監査証跡**: 実行履歴を記録として保存できます

**注意**: `result.txt` は毎回の実行時に上書きされます。ログを保持したい場合は、実行後に別の場所にコピーしてください。


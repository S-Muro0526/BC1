# Wasabi Downloader Blueprint
システム全体の設計と連携動作に関する技術資料

## 📋 目次
1. [システム概要](#システム概要)
2. [アーキテクチャ図](#アーキテクチャ図)
3. [コンポーネント詳細](#コンポーネント詳細)
4. [データフロー](#データフロー)
5. [認証とセッション管理](#認証とセッション管理)
6. [エラーハンドリング戦略](#エラーハンドリング戦略)
7. [セキュリティ設計](#セキュリティ設計)

---

## システム概要

**Wasabi Downloader** は、Wasabi Hot Cloud Storage（S3互換ストレージ）からファイルやディレクトリを効率的にダウンロードするためのPython製CLIツールです。

### 主要機能
- ✅ **単一ファイルダウンロード**: 特定のオブジェクトを指定してダウンロード
- ✅ **ディレクトリ一括ダウンロード**: プレフィックス配下の全ファイルを再帰的にダウンロード
- ✅ **バージョン管理対応**: 過去の特定時点でのファイル状態を一括復元
- ✅ **MFA認証サポート**: 多要素認証によるセキュアなアクセス
- ✅ **プロキシ対応**: カスタムSSL証明書を使用したプロキシ環境での動作
- ✅ **デバッグログ**: 全処理をタイムスタンプ付きで記録

### 技術スタック
- **言語**: Python 3.x
- **主要ライブラリ**: 
  - `boto3`: AWS SDK for Python（S3/STS操作）
  - `tqdm`: プログレスバー表示
- **認証プロトコル**: AWS STS (Security Token Service)
- **ストレージAPI**: S3互換API

---

## アーキテクチャ図

```mermaid
graph TB
    subgraph "ユーザーインターフェース層"
        CLI[wasabi_downloader.py<br/>CLIエントリーポイント]
    end

    subgraph "ビジネスロジック層"
        S3H[s3_handler.py<br/>S3操作ハンドラー]
        CONFIG[config_loader.py<br/>設定管理]
    end

    subgraph "インフラストラクチャ層"
        LOGGER[logger.py<br/>ログシステム]
        BOTO3[boto3ライブラリ]
    end

    subgraph "外部サービス"
        WASABI_S3[Wasabi S3 API<br/>s3.wasabisys.com]
        WASABI_STS[Wasabi STS API<br/>sts.wasabisys.com]
    end

    subgraph "永続化層"
        ENV[config.env<br/>設定ファイル]
        SESSION[.mfa_session.json<br/>MFAセッション]
        LOG[result.txt<br/>実行ログ]
    end

    CLI -->|設定読み込み| CONFIG
    CLI -->|S3操作依頼| S3H
    CLI -->|ログ出力| LOGGER
    
    CONFIG -->|ファイル読み取り| ENV
    CONFIG -->|ログ出力| LOGGER
    
    S3H -->|boto3クライアント使用| BOTO3
    S3H -->|セッション保存/読み込み| SESSION
    S3H -->|ログ出力| LOGGER
    
    BOTO3 -->|S3 API呼び出し| WASABI_S3
    BOTO3 -->|STS認証| WASABI_STS
    
    LOGGER -->|書き込み| LOG

    style CLI fill:#e1f5ff
    style S3H fill:#fff4e1
    style CONFIG fill:#fff4e1
    style LOGGER fill:#e8f5e9
    style WASABI_S3 fill:#ffe1e1
    style WASABI_STS fill:#ffe1e1
```

---

## コンポーネント詳細

### 1️⃣ wasabi_downloader.py
**役割**: CLIのエントリーポイントとコマンドルーティング

#### 主要機能
- コマンドライン引数のパース（`argparse`）
- サブコマンド実装:
  - `mfa`: MFA認証実行
  - `download_file`: 単一ファイルダウンロード
  - `download_dir`: ディレクトリ一括ダウンロード
  - `download_versioned`: タイムスタンプ指定バージョンダウンロード
  - `list_files`: ファイル一覧表示
- プログレスバー管理（tqdm）
- ロガーのライフサイクル管理（初期化→使用→クローズ）

#### 重要な処理フロー
```python
1. ロガー初期化 (logger.init_logger())
2. コマンド引数解析
3. 設定ファイル読み込み (config_loader.load_config())
4. MFAセッション検証（必要な場合）
5. S3クライアント取得 (s3_handler.get_s3_client())
6. コマンド実行
7. ロガークローズ (logger.close_logger())
```

#### 依存関係
```python
import config_loader  # 設定管理
import s3_handler     # S3操作
import logger         # ログシステム
```

---

### 2️⃣ s3_handler.py
**役割**: Wasabi S3/STSとの全ての通信を担当

#### 主要関数

| 関数名 | 機能 | 戻り値 |
|--------|------|--------|
| `get_mfa_session_token()` | STSでMFAトークン検証し、一時認証情報取得 | Dict[Credentials] |
| `save_session()` | 一時認証情報をJSONファイルに保存 | None |
| `load_session()` | 保存された認証情報を読み込み | Optional[Dict] |
| `is_session_valid()` | セッションの有効期限チェック | bool |
| `get_s3_client()` | S3クライアントインスタンス作成 | boto3.client |
| `get_object_info()` | 単一オブジェクトのメタデータ取得 | Dict[Key, Size, LastModified] |
| `list_objects_in_prefix()` | プレフィックス配下の全オブジェクトリスト | List[Objects], total_size |
| `list_object_versions_at_timestamp()` | 指定時刻の有効バージョンリスト | List[Versions], total_size |
| `download_file()` | 単一ファイルダウンロード | None |
| `download_objects()` | 複数オブジェクトバッチダウンロード | None |

#### 認証フロー（MFA有効時）
```mermaid
sequenceDiagram
    participant User
    participant CLI as wasabi_downloader
    participant S3H as s3_handler
    participant STS as Wasabi STS
    participant File as .mfa_session.json

    User->>CLI: python wasabi_downloader.py mfa
    CLI->>User: Enter MFA Token:
    User->>CLI: 123456
    CLI->>S3H: get_mfa_session_token(config, "123456")
    S3H->>STS: get_session_token(SerialNumber, TokenCode)
    STS-->>S3H: Credentials (AccessKey, SecretKey, SessionToken, Expiration)
    S3H->>File: save_session(credentials)
    S3H-->>CLI: Success
    CLI->>User: MFA authentication successful
```

#### バージョン管理の仕組み
`list_object_versions_at_timestamp()`は以下のロジックで動作:
1. `list_object_versions` APIで全バージョンとDeleteMarkerを取得
2. 各オブジェクトキーごとに、指定タイムスタンプ以前の最新バージョンを特定
3. DeleteMarkerでない有効なバージョンのみをリストアップ

---

### 3️⃣ config_loader.py
**役割**: 環境設定ファイルの読み込みと検証

#### 処理ステップ
```python
1. config.envファイルをオープン
2. key=value形式でパース（コメント行と空行はスキップ）
3. 必須キーの存在確認:
   - aws_access_key_id
   - aws_secret_access_key
   - endpoint_url
   - bucket_name
   - sts_endpoint_url
4. オプションキーの処理:
   - mfa_serial_number: 空の場合はNoneに変換
   - ssl_verify_path: 空の場合はNoneに変換
5. Dict形式で設定を返却
```

#### バリデーション
- 必須キー不足時: `ValueError`をスロー
- ファイル不在時: `FileNotFoundError`をスロー

---

### 4️⃣ logger.py
**役割**: デュアル出力（コンソール + ファイル）ロギングシステム

#### 設計の特徴
- **シングルトンパターン**: グローバル`_global_logger`で全モジュールから同一インスタンスを使用
- **タイムスタンプ精度**: ミリ秒まで記録（`%Y-%m-%d %H:%M:%S.%f`）
- **ファイル自動フラッシュ**: 各ログ出力後に即座にディスク書き込み
- **コンテキストマネージャ対応**: `with`文で自動クローズ可能

#### ログレベル

| レベル | メソッド | 用途 |
|--------|----------|------|
| INFO | `log_info()` | 一般的な情報（コマンド開始、接続成功など） |
| DEBUG | `log_debug()` | 詳細なデバッグ情報（設定読み込み、API呼び出しなど） |
| WARNING | `log_warning()` | 警告（個別ファイルダウンロード失敗など） |
| ERROR | `log_error()` | エラー（認証失敗、設定エラーなど） |

#### ログファイル構造
```
================================================================================
Wasabi Downloader Execution Log
Started at: 2025-12-03 15:22:46
================================================================================

[2025-12-03 15:22:47.001] INFO: Starting command: list_files
[2025-12-03 15:22:47.002] DEBUG: Arguments: {'command': 'list_files', 'source': ''}
...
[2025-12-03 15:22:57.305] INFO: Total files found: 42

================================================================================
Execution ended at: 2025-12-03 15:22:57
================================================================================
```

---

## データフロー

### 📥 単一ファイルダウンロード (`download_file`)
```mermaid
sequenceDiagram
    participant User
    participant CLI
    participant ConfigLoader
    participant S3Handler
    participant Wasabi
    participant Logger

    User->>CLI: download_file --source "path/file.txt"
    CLI->>Logger: init_logger()
    CLI->>ConfigLoader: load_config("config.env")
    ConfigLoader->>Logger: log_debug("Loading config...")
    ConfigLoader-->>CLI: config dict
    CLI->>S3Handler: get_s3_client(config, session_data)
    S3Handler->>Logger: log_debug("Creating S3 client...")
    S3Handler-->>CLI: s3_client
    CLI->>S3Handler: get_object_info(s3_client, bucket, key)
    S3Handler->>Wasabi: head_object(Bucket, Key)
    Wasabi-->>S3Handler: {Size, LastModified}
    S3Handler->>Logger: log_debug("Object size: X bytes")
    S3Handler-->>CLI: object_info
    CLI->>S3Handler: download_file(s3_client, bucket, key, dest, callback)
    S3Handler->>Wasabi: download_file()
    Wasabi-->>S3Handler: ファイルデータ
    S3Handler->>Logger: log_debug("Successfully downloaded")
    S3Handler-->>CLI: Success
    CLI->>User: ✅ ダウンロード完了
    CLI->>Logger: close_logger()
```

---

### 📦 ディレクトリ一括ダウンロード (`download_dir`)
```mermaid
sequenceDiagram
    participant CLI
    participant S3Handler
    participant Wasabi

    CLI->>S3Handler: list_objects_in_prefix(client, bucket, prefix)
    S3Handler->>Wasabi: list_objects_v2(Bucket, Prefix) [ページネーション]
    Wasabi-->>S3Handler: Page 1 {Contents: [...]}
    Wasabi-->>S3Handler: Page 2 {Contents: [...]}
    Wasabi-->>S3Handler: ...
    S3Handler-->>CLI: [object_list], total_size
    
    CLI->>S3Handler: download_objects(client, bucket, dest_dir, prefix, object_list)
    loop 各オブジェクト
        S3Handler->>Wasabi: download_file(Bucket, Key, Filename)
        Wasabi-->>S3Handler: ファイルデータ
        S3Handler->>S3Handler: ローカルに保存
    end
    S3Handler-->>CLI: 完了統計（成功数/エラー数）
```

---

### ⏱️ バージョン指定ダウンロード (`download_versioned`)
```mermaid
flowchart TD
    A[ユーザー: timestamp指定] --> B[タイムスタンプをdatetime変換]
    B --> C[list_object_versions API呼び出し]
    C --> D[全バージョン + DeleteMarkerを取得]
    D --> E{各オブジェクトキーをループ}
    E --> F{LastModified <= timestamp?}
    F -->|Yes| G[最新のバージョンとして記録]
    F -->|No| E
    E --> H[全キーの処理完了]
    H --> I{DeleteMarkerか?}
    I -->|No| J[ダウンロード対象に追加]
    I -->|Yes| K[スキップ]
    J --> L[download_objects実行]
    K --> L
    L --> M[各バージョンをVersionId指定でダウンロード]
```

---

## 認証とセッション管理

### MFA認証フロー

#### 1. 初回認証（`mfa`コマンド）
```python
# ユーザー操作
$ python wasabi_downloader.py mfa
Enter MFA Token: 123456

# 内部処理
1. config.envからmfa_serial_numberを取得
2. STSにget_session_token()リクエスト
   - SerialNumber: arn:aws:iam::...:mfa/user
   - TokenCode: 123456
3. STS応答:
   {
     "AccessKeyId": "ASIA...",
     "SecretAccessKey": "...",
     "SessionToken": "...",
     "Expiration": "2026-01-22T17:14:45Z"
   }
4. .mfa_session.jsonに保存
```

#### 2. セッション再利用（他コマンド実行時）
```python
# 内部処理
1. .mfa_session.jsonが存在するかチェック
2. is_session_valid()で有効期限確認
   - Expiration > 現在時刻 + 1分 → 有効
   - それ以外 → エラー
3. 有効な場合、セッション情報をget_s3_client()に渡す
4. boto3がSessionTokenを使用してS3 API呼び出し
```

### セッション有効期限
- **デフォルト**: STSトークンは通常12時間有効
- **バッファ**: 有効期限の1分前に無効と判定（安全マージン）
- **期限切れ時**: `ValueError`をスローし、再度`mfa`コマンド実行を促す

---

## エラーハンドリング戦略

### エラー分類と対処

| エラータイプ | 発生源 | 処理 | ユーザーへの影響 |
|-------------|--------|------|------------------|
| **設定ファイルエラー** | config_loader.py | `FileNotFoundError`/`ValueError`スロー → CLI層でキャッチしてログ出力 | プログラム終了（exit 1） |
| **認証エラー** | s3_handler.py | `ClientError`スロー | プログラム終了（exit 1） |
| **MFAセッション期限切れ** | s3_handler.py | `ValueError`スロー | エラーメッセージ表示、`mfa`コマンド再実行を促す |
| **単一オブジェクトダウンロード失敗** | download_file | 例外スロー | プログラム終了 |
| **バッチダウンロード中の個別失敗** | download_objects | `WARNING`ログ出力、処理継続 | 他ファイルのダウンロードは継続 |
| **オブジェクト不在** | get_object_info | `FileNotFoundError`スロー | プログラム終了 |

### 例外ハンドリングパターン
```python
# wasabi_downloader.py
try:
    # メイン処理
    config = config_loader.load_config(config_path)
    s3_client = s3_handler.get_s3_client(config, session_data=session_data)
    # ...
except (FileNotFoundError, ValueError, ClientError) as e:
    logger.log_error(str(e))
    sys.exit(1)
except Exception as e:
    logger.log_error(f"An unexpected error occurred: {e}")
    sys.exit(1)
finally:
    logger.close_logger()  # 必ずログをクローズ
```

---

## セキュリティ設計

### 🔐 認証情報の保護

#### 原則
1. **ソースコードにハードコーディングしない**: 全て`config.env`から読み込み
2. **一時認証情報の使用**: MFA有効時はSTS一時トークンを使用
3. **セッションファイルの権限**: `.mfa_session.json`はローカルファイルシステムの権限で保護

#### config.envの管理
```bash
# .gitignoreに追加必須
config.env
.mfa_session.json
result.txt
```

### 🌐 プロキシ環境とSSL検証

#### 課題
企業内プロキシでSSLインスペクションが行われる環境では、Wasabiの証明書検証が失敗する。

#### 解決策
`ssl_verify_path`にカスタムCA証明書のパスを指定:
```env
ssl_verify_path=C:\certs\corporate-proxy-ca.pem
```

#### 実装
```python
# s3_handler.py
if config.get('ssl_verify_path'):
    logger.log_debug(f"Using custom SSL certificate: {config['ssl_verify_path']}")
    client_params['verify'] = config['ssl_verify_path']

s3_client = boto3.client('s3', **client_params)
```

boto3は`verify`パラメータに証明書パスを渡すことで、カスタムCA証明書を使用して検証を行う。

### 🛡️ MFA (多要素認証)

#### 有効化条件
`config.env`に以下を設定:
```env
mfa_serial_number=arn:aws:iam::123456789012:mfa/username
```

#### セキュリティメリット
- 認証情報が万一漏洩しても、MFAコードなしでは操作不可
- 一時トークンは有効期限付きのため、永続的な認証情報よりリスク低減
- 最小権限の原則に準拠（IAMポリシーでMFA必須条件を設定可能）

---

## 付録

### ディレクトリ構造
```
BC1-feature-separate-mfa-command/
├── wasabi_downloader.py    # エントリーポイント
├── s3_handler.py            # S3/STS操作
├── config_loader.py         # 設定管理
├── logger.py                # ロギングシステム
├── config.env               # 環境設定（要手動作成）
├── requirements.txt         # 依存ライブラリ
├── README.md                # ユーザー向けドキュメント
├── blueprint.md             # 本ドキュメント
├── Compailation.md          # PyInstallerビルド手順
├── LOG_FEATURE.md           # ログ機能詳細
├── .mfa_session.json        # MFAセッション（自動生成）
└── result.txt               # 実行ログ（自動生成）
```

### 依存関係グラフ
```mermaid
graph LR
    WD[wasabi_downloader.py]
    S3H[s3_handler.py]
    CFG[config_loader.py]
    LOG[logger.py]
    BOTO[boto3]
    
    WD --> S3H
    WD --> CFG
    WD --> LOG
    S3H --> LOG
    S3H --> BOTO
    CFG --> LOG
    
    style WD fill:#e1f5ff,stroke:#01579b,stroke-width:3px
    style S3H fill:#fff4e1,stroke:#e65100
    style CFG fill:#fff4e1,stroke:#e65100
    style LOG fill:#e8f5e9,stroke:#1b5e20
    style BOTO fill:#f3e5f5,stroke:#4a148c
```

### 主要な設計パターン

| パターン | 適用箇所 | 目的 |
|---------|---------|------|
| **Facade Pattern** | s3_handler.py | boto3の複雑なAPIを簡潔なインターフェースでラップ |
| **Singleton Pattern** | logger.py | グローバルロガーで全モジュールから同一インスタンスを使用 |
| **Strategy Pattern** | download_file/download_dir/download_versioned | コマンドごとに異なるダウンロード戦略を実装 |
| **Dependency Injection** | get_s3_client() | 設定やセッションデータを外部から注入 |

---

## 変更履歴

| 日付 | 変更内容 |
|------|---------|
| 2026-01-22 | 初版作成 - システム全体のブループリント記述 |

---

**Document Version**: 1.0  
**Last Updated**: 2026-01-22  
**Author**: Antigravity

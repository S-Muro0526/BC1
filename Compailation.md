# PyInstaller コンパイル手順

## 前提条件
- Python がインストールされていること
- `pip install pyinstaller`
- `pip install -r requirements.txt`

## コンパイルコマンド
以下のコマンドをターミナルで実行し、アプリケーションを単一の実行ファイルにコンパイルします：

```bash
pyinstaller --onefile --name wasabi_downloader wasabi_downloader.py
```

## コンパイル後のセットアップ
1. `dist` フォルダにある生成された実行ファイル (例: `dist/wasabi_downloader.exe`) を確認してください。
2. **重要**: `config.csv` ファイルを実行ファイルと同じディレクトリにコピーしてください。
   - アプリケーションは、実行ファイルと同じフォルダにある `config.csv` を参照するように設計されています。

## 使用方法
実行ファイルと `config.csv` があるディレクトリでターミナルを開き、以下を実行します：

```bash
.\wasabi_downloader.exe list_files
```
（またはツールがサポートするその他のコマンド）
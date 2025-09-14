# py-sbi-yahoo-auth

Yahooメールを利用したSBI証券の二段階認証処理の自動化スクリプト

## Features

* SBI証券のログインと二段階認証を自動化
* Yahooメールから認証コードを取得し、認証処理を自動実行
* Playwrightを使用したブラウザ操作
* ログ出力による処理の追跡

## Project Structure

* sbiauth.py: メインの認証処理クラス（SbiAuthenticator）
* README.md: 本ドキュメント
* error.html: エラー時のHTML出力（デバッグ用）

## How to Build and Run

1.  **Clone or Download:**
    *   Clone: git clone https://github.com/yourusername/py-sbi-yahoo-auth.git
    *   Or download ZIP from this repository.
2.  **Run:**
    *  必要なライブラリをインストール: pip install playwright
    *  環境変数またはコード内でSBI証券およびYahooメールの認証情報を設定
    *  以下のサンプルコードを参考に実行

```python
#coding: utf-8
from sbiauth import SbiAuthenticator
import logging
import os
import re
 
# ログの設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s [%(filename)s:%(lineno)d]')
logger = logging.getLogger(__name__)
 
if __name__ == '__main__':
    try:
        authenticator = SbiAuthenticator(
            sbi_username="SBI_USERNAME", # SBIユーザ名
            sbi_password="SBI_PASSWORD", # SBIパスワード
            mail_username="MAIL_USERNAME", # Yahooメールユーザ名
            mail_password="MAIL_PASSWORD", # Yahooメールパスワード
            headless=False  # ヘッドレス設定（Trueで非表示、Falseで表示）
        )
 
        playwright, browser, sbi_page = authenticator.authenticate()
 
        好きな処理関数(sbi_page)
 
        authenticator.close()
 
    except ValueError as e:
        logger.error(f"認証エラー: {e}")
        raise
    except Exception as e:
        logger.error(f"予期しないエラー: {e}")
        raise
```

## License

MIT License

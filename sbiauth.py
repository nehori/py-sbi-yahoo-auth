# coding: utf-8
from playwright.sync_api import sync_playwright
import time
import logging
import re
import os

# ログの設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s [%(filename)s:%(lineno)d]')
logger = logging.getLogger(__name__)

class SbiAuthenticator:
    def __init__(
        self,
        sbi_username=None,
        sbi_password=None,
        mail_username=None,
        mail_password=None,
        mail_url="https://login.yahoo.co.jp/config/login?.done=https%3A%2F%2Fmail.yahoo.co.jp%2Fu%2Fpc%2Ff%2F",
        headless=False
    ):
        """
        SBI証券のログイン・認証処理を行うクラス
        """
        self.sbi_username = sbi_username or os.environ.get("SBI_USERNAME")
        self.sbi_password = sbi_password or os.environ.get("SBI_PASSWORD")
        self.mail_username = mail_username or os.environ.get("MAIL_USERNAME")
        self.mail_password = mail_password or os.environ.get("MAIL_PASSWORD")
        self.mail_url = mail_url
        self.headless = headless
        self.browser = None
        self.sbi_page = None
        self.context = None
        self.playwright = None

        if not self.sbi_username or not self.sbi_password:
            logger.error("SBI_USERNAME and SBI_PASSWORD must be provided via arguments or environment variables")
            raise ValueError("Missing SBI_USERNAME or SBI_PASSWORD")
        if not self.mail_username or not self.mail_password:
            logger.error("MAIL_USERNAME and MAIL_PASSWORD must be provided via arguments or environment variables")
            raise ValueError("Missing MAIL_USERNAME or MAIL_PASSWORD")

        logger.info("SbiAuthenticator initialized with provided credentials")

    def login_to_sbi(self, context):
        """
        SBI証券にログインする
        """
        page = context.new_page()
        page.goto("https://www.sbisec.co.jp/ETGate/")
        page.fill('input[name="user_id"]', self.sbi_username)
        page.fill('input[name="user_password"]', self.sbi_password)
        page.click('input[name="ACT_login"]')
        return page

    def click_to_emailbottom(self, page):
        """
        'Eメールを送信する' ボタンをクリックする
        """
        time.sleep(3)
        page.click('button[name="ACT_deviceotpcall"]')
        logger.info("Clicked 'Eメールを送信する' button")

    def authenticate_sbi(self, page):
        """
        SBI証券の認証キーを取得する
        """
        time.sleep(3)
        auth_code = page.text_content('div#code-display') or "認証コードが見つかりませんでした"
        logger.info(f"Authentication code: {auth_code}")
        return auth_code

    def wait_for_inbox(self, page, timeout=100000):
        """受信箱が表示されるまで待機する"""
        try:
            page.wait_for_function(
                """
                (text) => {
                    const elements = document.querySelectorAll('span, div, a, h1');
                    return Array.from(elements).some(el => el.innerText.includes(text));
                }
                """,
                arg="受信箱",
                timeout=timeout
            )
            logger.info("「受信箱」が表示されました")
            return True
        except TimeoutError:
            logger.warning(f"タイムアウト: 「受信箱」が{timeout/1000}秒以内に表示されませんでした")
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "error_inbox.html"), "w", encoding="utf-8") as f:
                f.write(page.content())
            page.screenshot(path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "error_inbox.png"))
            return False

    def mail_operation(self, context):
        """
        Yahoo!メールを起動し、ログインを完了させる
        戻り値: (page, new_tab)
        """
        page = context.new_page()
        page.goto(self.mail_url)
        time.sleep(2)

        new_tab = context.new_page()
        new_tab.goto(self.mail_url)
        time.sleep(2)

        # セッション保持により受信箱が既に表示されているか確認（タイムアウトしても続行）
        try:
            if self.wait_for_inbox(new_tab, timeout=10000):
                logger.info("セッション保持によりログイン不要、メーラー起動処理 完了")
                return page, new_tab
            else:
                logger.warning("受信箱の初期チェックでタイムアウト、ログイン処理に進みます")
        except Exception as e:
            logger.warning(f"受信箱の初期チェックでエラー: {type(e).__name__}: {e}、ログイン処理に進みます")

        # ログイン処理
        new_tab.fill('input[name="handle"]', self.mail_username)
        new_tab.click('button[data-cl_cl_index="2"]')
        logger.info("ユーザ名入力処理 完了")
        time.sleep(2)

        new_tab.fill('input[name="password"]', self.mail_password)
        new_tab.click('button.riff-Clickable__root:text("ログイン")')
        logger.info("パスワード入力処理 完了")
        time.sleep(2)

        # SMS認証設定画面が表示された場合、「あとで設定する」をクリック
        later_button = new_tab.query_selector('a:text("あとで設定する")')
        if later_button:
            logger.info("SMS認証設定画面を検出、あとで設定するをクリック")
            later_button.click()
            time.sleep(2)

        # 受信箱が表示されるまで待機
        if not self.wait_for_inbox(new_tab, timeout=100000):
            logger.error("メーラー起動処理 失敗")
            return None, None

        logger.info("メーラー起動処理 完了")
        return page, new_tab

    def process_email(self, new_tab, auth_id):
        """
        メールを受信し、認証URLを処理する
        """
        time.sleep(5)  # 待機時間を保持
        
        # 「受信箱」をクリックしてメール一覧を更新
        new_tab.click('span:has-text("受信箱")')
        logger.info("受信箱をクリックしました")
        time.sleep(2)  # 待機時間を保持

        logger.info("メーラー起動処理 完了")
        time.sleep(2)  # 待機時間を保持

        email_rows = new_tab.query_selector_all('tr[data-cy="mailListItem"]')
        target_email = next((row for row in email_rows if row.query_selector('span[data-cy="mailListFromOrTo"]').get_attribute('title') == 'info@sbisec.co.jp'), None)

        if not target_email:
            logger.error("SBI証券からのメールが見つかりませんでした")
            with open("error.html", "w", encoding="utf-8") as f:
                f.write(new_tab.content())
            new_tab.close()
            return False

        logger.info("SBI証券からの最新のメール選択")
        target_email.click()
        time.sleep(2)

        preview_area = new_tab.query_selector('div[data-cy="mailPreviewArea"]')
        if not preview_area:
            logger.error("メールプレビューエリアが見つかりませんでした")
            with open("error.html", "w", encoding="utf-8") as f:
                f.write(new_tab.content())
            new_tab.close()
            return False

        iframe = preview_area.query_selector('iframe[data-cy="htmlMail"]')
        if not iframe:
            logger.error("iframeが見つかりませんでした")
            with open("error.html", "w", encoding="utf-8") as f:
                f.write(new_tab.content())
            new_tab.close()
            return False

        frame = iframe.content_frame()
        if not frame:
            logger.error("iframeのコンテンツにアクセスできませんでした")
            with open("error.html", "w", encoding="utf-8") as f:
                f.write(new_tab.content())
            new_tab.close()
            return False

        frame.wait_for_load_state('load', timeout=10000)

        link_element = frame.query_selector('a[href*="deviceAuthentication/input"]')
        if link_element:
            auth_url = link_element.get_attribute('href').replace('&amp;', '&')
        else:
            content = frame.text_content('body') or "本文が見つかりませんでした"
            url_match = re.search(r'https://m\.sbisec\.co\.jp/deviceAuthentication/input\?[^ \n]+', content)
            if not url_match:
                logger.error("Authentication URL not found in email")
                with open("error.html", "w", encoding="utf-8") as f:
                    f.write(new_tab.content())
                new_tab.close()
                return False
            auth_url = url_match.group(0)

        logger.info(f"Authentication URL: {auth_url}")

        new_tab.goto(auth_url)
        time.sleep(2)

        new_tab.click('div.btn_area a')
        time.sleep(2)

        new_tab.fill('input#verifyCode', auth_id)
        logger.info(f"Entered authentication code: {auth_id}")
        new_tab.click('button#verification')
        logger.info("Clicked '認証する' button")
        time.sleep(5)

        new_tab.close()
        return True

    def click_to_certification(self, page):
        """
        SBI証券ログイン側のブラウザで認証を進める
        """
        page.check('input#device-checkbox')
        logger.info("Checked 'device-checkbox'")
        page.click('button#device-auth-otp')
        logger.info("Clicked 'デバイスを登録する' button")
        time.sleep(3)

    def authenticate(self):
        """
        SBI証券にログインし、認証を完了してブラウザとページを返す
        戻り値: (playwright, browser, sbi_page)
        """
        # スクリプトのディレクトリとuser_dataパスを設定
        user_data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_data")
        logger.info(f"user_data directory: {user_data_dir}")
        os.makedirs(user_data_dir, exist_ok=True)

        self.playwright = sync_playwright().start()
        # 非匿名モードでChromiumを起動
        self.browser = self.playwright.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,  # lib/user_dataに保存
            headless=self.headless,
            args=["--disable-blink-features=AutomationControlled"],  # ボット検知回避
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
            viewport={"width": 1500, "height": 1000},
            locale="ja-JP",
            timezone_id="Asia/Tokyo"
        )
        self.context = self.browser
        self.context.set_default_timeout(180000)

        # 1. 最初にYahoo!メールを起動してログイン
        logger.info("Starting Yahoo! Mail login")
        mail_page, mail_tab = self.mail_operation(self.context)

        if not mail_tab:
            logger.error("Email processing failed, aborting authentication")
            mail_page.close()
            self.close()
            return None, None, None

        # 2. SBI証券にログインして認証キーを取得
        self.sbi_page = self.login_to_sbi(self.context)
        
        # 重要なお知らせ画面のチェック
        notice_selector = 'div#titleSec.seeds-my-x-6.seeds-text-main h1:has-text("重要なお知らせ")'
        try:
            self.sbi_page.wait_for_selector(notice_selector, timeout=5000)
            logger.info("重要なお知らせ画面を検出、認証キー取得処理をスキップ")
        except Exception as e:
            logger.info(f"重要なお知らせ画面は検出されず、通常の認証処理を続行: {type(e).__name__}: {e}")
            try:
                self.click_to_emailbottom(self.sbi_page)
                auth_id = self.authenticate_sbi(self.sbi_page)
                success = self.process_email(mail_tab, auth_id)
                if not success:
                    logger.error("Email processing failed, aborting authentication")
                    mail_page.close()
                    self.close()
                    return None, None, None
                self.click_to_certification(self.sbi_page)
            except Exception as e:
                logger.error(f"認証処理でエラー: {type(e).__name__}: {e}")
                mail_page.close()
                self.close()
                return None, None, None

        # リダイレクトを待機
        redirect_url = "https://site1.sbisec.co.jp/ETGate/WPLEThmR001Control/DefaultPID/DefaultAID/DSWPLEThmR001Control"
        logger.info("Waiting for redirect after authentication")
        try:
            self.sbi_page.wait_for_url(redirect_url, timeout=20000)
            logger.info(f"Current page URL after redirect: {self.sbi_page.url}")
        except Exception as e:
            logger.warning(f"Redirect wait failed: {e}. Proceeding with current URL: {self.sbi_page.url}")

        # メールのページを閉じる
        mail_page.close()

        return self.playwright, self.browser, self.sbi_page

    def close(self):
        """
        ブラウザとPlaywrightを閉じる
        """
        if self.browser:
            self.browser.close()
            self.browser = None
            self.sbi_page = None
            self.context = None
            logger.info("Browser closed")
        if self.playwright:
            self.playwright.stop()
            self.playwright = None
            logger.info("Playwright stopped")

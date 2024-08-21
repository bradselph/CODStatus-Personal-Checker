import sys
import json
import time
import asyncio
import aiohttp
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QTextEdit, QLineEdit, QLabel, QHBoxLayout, QListWidget, QMessageBox, QTabWidget, QFileDialog, QProgressBar
from PyQt5.QtCore import QThread, pyqtSignal, Qt
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

# Constants
CONFIG_FILE_NAME = "config.json"
ACCOUNTS_FILE_NAME = "accounts.json"
LOGIN_CREDENTIALS_FILE_NAME = "login_credentials.json"
EZ_CAPTCHA_API_URL = "https://api.ez-captcha.com/createTask"
EZ_CAPTCHA_RESULT_URL = "https://api.ez-captcha.com/getTaskResult"
EZ_CAPTCHA_BALANCE_URL = "https://api.ez-captcha.com/getBalance"
ACCOUNT_CHECK_URL = "https://support.activision.com/api/bans/v2/appeal?locale=en"
PROFILE_URL = "https://support.activision.com/api/profile"
LOGIN_URL = "https://s.activision.com/do_login?new_SiteId=activision"
SUPPORT_URL = "https://support.activision.com"
MAX_RETRIES = 12
RETRY_INTERVAL = 10
MAX_CONCURRENT_CHECKS = 25
EZ_CAPTCHA_APP_ID = 84291
LOGIN_SITE_KEY = "6LfjPWwbAAAAAKhf5D1Ag5nIS-QO2M4rX52LcnDt"
LOGIN_TIMEOUT = 120
CAPTCHA_TIMEOUT = 120

class Config:
    def __init__(self):
        self.ez_captcha_key = ""
        self.site_key = ""
        self.page_url = ""
        self.debug_mode = False

class Account:
    def __init__(self, email, username, uno_id, sso_cookie):
        self.email = email
        self.username = username
        self.uno_id = uno_id
        self.sso_cookie = sso_cookie

class LoginCredentials:
    def __init__(self, email, password):
        self.email = email
        self.password = password

config = Config()
accounts = []
login_credentials = []

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CODStatus Personal Checker")
        self.setGeometry(100, 100, 800, 600)

        main_layout = QHBoxLayout()
        left_layout = QVBoxLayout()
        right_layout = QVBoxLayout()

        self.account_list = QListWidget()
        self.account_list.itemClicked.connect(self.display_account_details)
        left_layout.addWidget(QLabel("Accounts:"))
        left_layout.addWidget(self.account_list)

        self.check_accounts_button = QPushButton("Check Account Status")
        self.check_accounts_button.clicked.connect(self.check_accounts)
        left_layout.addWidget(self.check_accounts_button)

        self.validate_cookies_button = QPushButton("Validate SSO Cookies")
        self.validate_cookies_button.clicked.connect(self.validate_accounts)
        left_layout.addWidget(self.validate_cookies_button)

        self.check_balance_button = QPushButton("Check Captcha Balance")
        self.check_balance_button.clicked.connect(self.check_captcha_balance)
        left_layout.addWidget(self.check_balance_button)

        self.login_button = QPushButton("Login and Update SSO Cookies")
        self.login_button.clicked.connect(self.login_and_update_sso)
        left_layout.addWidget(self.login_button)

        self.account_details = QTextEdit()
        self.account_details.setReadOnly(True)
        right_layout.addWidget(QLabel("Account Details:"))
        right_layout.addWidget(self.account_details)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        right_layout.addWidget(QLabel("Log:"))
        right_layout.addWidget(self.log_text)

        main_layout.addLayout(left_layout, 1)
        main_layout.addLayout(right_layout, 2)

        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        self.captcha_solver = CaptchaSolver()
        self.captcha_solver.captcha_solved.connect(self.on_captcha_solved)

        self.load_config()
        self.load_accounts()
        self.load_login_credentials()
        self.update_account_list()

    def load_config(self):
        try:
            with open(CONFIG_FILE_NAME, 'r') as f:
                config_data = json.load(f)
                config.ez_captcha_key = config_data.get('ez_captcha_key', '')
                config.site_key = config_data.get('site_key', '')
                config.page_url = config_data.get('page_url', '')
                config.debug_mode = config_data.get('debug_mode', False)
            self.log("Config loaded successfully")
        except FileNotFoundError:
            self.log(f"Config file {CONFIG_FILE_NAME} not found. Using default values.")
        except json.JSONDecodeError:
            self.log(f"Error parsing {CONFIG_FILE_NAME}. Using default values.")

    def load_accounts(self):
        try:
            with open(ACCOUNTS_FILE_NAME, 'r') as f:
                accounts_data = json.load(f)
                for acc in accounts_data:
                    accounts.append(Account(acc['email'], acc['username'], acc['uno_id'], acc['sso_cookie']))
            self.log(f"Loaded {len(accounts)} accounts")
        except FileNotFoundError:
            self.log(f"Accounts file {ACCOUNTS_FILE_NAME} not found.")
        except json.JSONDecodeError:
            self.log(f"Error parsing {ACCOUNTS_FILE_NAME}.")

    def load_login_credentials(self):
        try:
            with open(LOGIN_CREDENTIALS_FILE_NAME, 'r') as f:
                cred_data = json.load(f)
                for cred in cred_data:
                    login_credentials.append(LoginCredentials(cred['email'], cred['password']))
            self.log(f"Loaded {len(login_credentials)} login credentials")
        except FileNotFoundError:
            self.log(f"Login credentials file {LOGIN_CREDENTIALS_FILE_NAME} not found.")
        except json.JSONDecodeError:
            self.log(f"Error parsing {LOGIN_CREDENTIALS_FILE_NAME}.")

    def update_account_list(self):
        self.account_list.clear()
        for account in accounts:
            self.account_list.addItem(account.email)

    def display_account_details(self, item):
        email = item.text()
        account = next((acc for acc in accounts if acc.email == email), None)
        if account:
            details = f"Email: {account.email}\n"
            details += f"Username: {account.username}\n"
            details += f"UNO ID: {account.uno_id}\n"
            details += f"SSO Cookie: {account.sso_cookie[:30]}..." if account.sso_cookie else "SSO Cookie: Not available"
            self.account_details.setText(details)

    def log(self, message):
        self.log_text.append(message)

    async def check_accounts(self):
        self.log("Checking accounts...")
        for account in accounts:
            status = await self.check_account(account)
            self.log(f"{account.email}: {status}")
        self.log("Account checking completed.")

    async def check_account(self, account):
        async with aiohttp.ClientSession() as session:
            captcha_response = await self.captcha_solver.solve_captcha()
            if not captcha_response:
                return "Failed to solve captcha"

            headers = {
                "Cookie": f"ACT_SSO_COOKIE={account.sso_cookie}",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
            }
            params = {"g-cc": captcha_response}

            try:
                async with session.get(ACCOUNT_CHECK_URL, headers=headers, params=params) as response:
                    if response.status != 200:
                        return f"Error: HTTP {response.status}"
                    data = await response.json()
                    if data.get("error"):
                        return f"API error: {data['error']}"
                    if not data.get("bans"):
                        return "Account not banned"
                    ban = data["bans"][0]
                    if ban["enforcement"] == "PERMANENT":
                        return "Permanently banned"
                    elif ban["enforcement"] == "UNDER_REVIEW":
                        return "Shadowbanned"
                    else:
                        return "Unknown ban status"
            except Exception as e:
                return f"Error: {str(e)}"

    async def validate_accounts(self):
        self.log("Validating SSO cookies...")
        for account in accounts:
            is_valid = await self.validate_sso_cookie(account.sso_cookie)
            status = "Valid" if is_valid else "Invalid"
            self.log(f"{account.email}: SSO Cookie is {status}")
            if not is_valid:
                account.sso_cookie = ""
        self.save_accounts()
        self.log("SSO cookie validation completed.")

    async def validate_sso_cookie(self, sso_cookie):
        async with aiohttp.ClientSession() as session:
            headers = {
                "Cookie": f"ACT_SSO_COOKIE={sso_cookie}",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
            }
            try:
                async with session.get(PROFILE_URL, headers=headers) as response:
                    return response.status == 200 and len(await response.text()) > 0
            except Exception:
                return False

    async def check_captcha_balance(self):
        self.log("Checking captcha balance...")
        balance = await self.get_ez_captcha_balance()
        if balance:
            self.log(f"EZ-Captcha balance: {balance}")
        else:
            self.log("Failed to retrieve EZ-Captcha balance")

    async def get_ez_captcha_balance(self):
        async with aiohttp.ClientSession() as session:
            payload = {"clientKey": config.ez_captcha_key}
            try:
                async with session.post(EZ_CAPTCHA_BALANCE_URL, json=payload) as response:
                    if response.status != 200:
                        return None
                    data = await response.json()
                    if data.get("errorId", 0) != 0:
                        return None
                    return f"{data.get('balance', 0):.2f}"
            except Exception:
                return None

    def login_and_update_sso(self):
        self.log("Starting login process...")
        self.login_thread = LoginThread(login_credentials, accounts)
        self.login_thread.log_message.connect(self.log)
        self.login_thread.finished.connect(self.on_login_finished)
        self.login_thread.start()

    def on_login_finished(self):
        self.log("Login process completed.")
        self.save_accounts()
        self.update_account_list()

    def save_accounts(self):
        accounts_data = [
            {
                "email": account.email,
                "username": account.username,
                "uno_id": account.uno_id,
                "sso_cookie": account.sso_cookie
            }
            for account in accounts
        ]
        with open(ACCOUNTS_FILE_NAME, 'w') as f:
            json.dump(accounts_data, f, indent=2)
        self.log("Accounts saved successfully.")

    def on_captcha_solved(self, solution):
        self.log("Captcha solved successfully.")

class CaptchaSolver(QThread):
    captcha_solved = pyqtSignal(str)

    async def solve_captcha(self):
        async with aiohttp.ClientSession() as session:
            create_task_payload = {
                "clientKey": config.ez_captcha_key,
                "task": {
                    "type": "ReCaptchaV2TaskProxyless",
                    "websiteURL": config.page_url,
                    "websiteKey": config.site_key,
                    "isInvisible": False
                }
            }
            try:
                async with session.post(EZ_CAPTCHA_API_URL, json=create_task_payload) as response:
                    if response.status != 200:
                        return None
                    create_task_result = await response.json()
                    if create_task_result.get("errorId") != 0:
                        return None
                    task_id = create_task_result.get("taskId")

                get_result_payload = {
                    "clientKey": config.ez_captcha_key,
                    "taskId": task_id
                }
                start_time = time.time()
                while time.time() - start_time < CAPTCHA_TIMEOUT:
                    async with session.post(EZ_CAPTCHA_RESULT_URL, json=get_result_payload) as response:
                        if response.status != 200:
                            return None
                        result = await response.json()
                        if result.get("status") == "ready":
                            solution = result.get("solution", {}).get("gRecaptchaResponse")
                            self.captcha_solved.emit(solution)
                            return solution
                        elif result.get("status") == "processing":
                            await asyncio.sleep(5)
                        else:
                            return None
                return None
            except Exception:
                return None

class LoginThread(QThread):
    log_message = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, login_credentials, accounts):
        super().__init__()
        self.login_credentials = login_credentials
        self.accounts = accounts

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.login_process())
        loop.close()

    async def login_process(self):
        for cred in self.login_credentials:
            self.log_message.emit(f"Logging in for account: {cred.email}")
            success, account_info = await self.login_and_get_cookie(cred)
            if success:
                self.update_account(account_info)
                self.log_message.emit(f"Successfully logged in and updated info for {cred.email}")
            else:
                self.log_message.emit(f"Failed to log in for {cred.email}")
        self.finished.emit()

    async def login_and_get_cookie(self, cred):
        driver = None
        try:
            options = uc.ChromeOptions()
            driver = uc.Chrome(options=options)

            driver.get(SUPPORT_URL)
            login_link = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, ".log-in-link"))
            )
            login_link.click()

            WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.ID, "username")))

            driver.find_element(By.ID, "username").send_keys(cred.email)
            driver.find_element(By.ID, "password").send_keys(cred.password)

            captcha_solver = CaptchaSolver()
            captcha_response = await captcha_solver.solve_captcha()
            if not captcha_response:
                return False, None

            driver.execute_script(f"""
                document.getElementById('g-recaptcha-response').innerHTML = '{captcha_response}';
                grecaptcha.getResponse = function() {{ return '{captcha_response}'; }};
            """)

            login_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.ID, "login-button"))
            )
            login_button.click()

            try:
                WebDriverWait(driver, LOGIN_TIMEOUT).until(EC.url_contains("support.activision.com"))
            except TimeoutException:
                return False, None

            all_cookies = driver.get_cookies()
            sso_cookie = next((cookie for cookie in all_cookies if cookie["name"] == "ACT_SSO_COOKIE"), None)

            if not sso_cookie:
                return False, None

            driver.get(PROFILE_URL)
            profile_data = json.loads(driver.find_element(By.TAG_NAME, "body").text)

            username = profile_data.get('username')
            email = profile_data.get('email')
            uno_account = next((acc for acc in profile_data.get('accounts', []) if acc.get('provider') == 'uno'), None)
            uno_id = uno_account.get('username') if uno_account else None

            return True, {
                "email": email,
                "username": username,
                "uno_id": uno_id,
                "sso_cookie": sso_cookie["value"]
            }

        except Exception as e:
            self.log_message.emit(f"An error occurred during login: {str(e)}")
        return False, None
        finally:
        if driver:
                driver.quit()15---


        async def login_and_get_cookie(self, cred):
    driver = None
    try:
        options = uc.ChromeOptions()
        driver = uc.Chrome(options=options)

        driver.get(SUPPORT_URL)
        login_link = WebDriverWait(driver, 10).until(
            EC.element_t-  e_clickable((By.CSS_SELECTOR, ".log-in-link"))
        )
        login_link.click()

        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.ID, "username")))

        driver.find_element(By.ID, "username").send_keys(cred.email)
        driver.find_element(By.ID, "password").send_keys(cred.password)

        captcha_solver = CaptchaSolver()
        captcha_response = await captcha_solver.solve_captcha()
        if not captcha_response:
            return False, None

        driver.execute_script(f"""
            document.getElementById('g-recaptcha-response').innerHTML = '{captcha_response}';
            grecaptcha.getResponse = function() {{ return '{captcha_response}'; }};
        """)

        login_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "login-button"))
        )
        login_button.click()

        try:
            WebDriverWait(driver, LOGIN_TIMEOUT).until(EC.url_contains("support.activision.com"))
        except TimeoutException:
            return False, None

        all_cookies = driver.get_cookies()
        sso_cookie = next((cookie for cookie in all_cookies if cookie["name"] == "ACT_SSO_COOKIE"), None)

        if not sso_cookie:
            return False, None

        driver.get(PROFILE_URL)
        profile_data = json.loads(driver.find_element(By.TAG_NAME, "body").text)

        username = profile_data.get('username')
        email = profile_data.get('email')
        uno_account = next((acc for acc in profile_data.get('accounts', []) if acc.get('provider') == 'uno'), None)
        uno_id = uno_account.get('username') if uno_account else None

        return True, {
            "email": email,
            "username": username,
            "uno_id": uno_id,
            "sso_cookie": sso_cookie["value"]
        }

    except Exception as e:
        self.log_message.emit(f"An error occurred during login: {str(e)}")
        return False, None
    finally:
        if driver:
            driver.quit()

def update_account(self, account_info):
    existing_account = next((acc for acc in self.accounts if acc.email == account_info["email"]), None)
    if existing_account:
        existing_account.username = account_info["username"]
        existing_account.uno_id = account_info["uno_id"]
        existing_account.sso_cookie = account_info["sso_cookie"]
    else:
        new_account = Account(
            account_info["email"],
            account_info["username"],
            account_info["uno_id"],
            account_info["sso_cookie"]
        )
        self.accounts.append(new_account)

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
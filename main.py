"""
CODStatus Personal Checker - Call of Duty Account Status Management Application

CRITICAL ISSUES SUMMARY (see detailed TODOs throughout the file):
==================================================================
1. BROKEN ACCOUNT CREATION - Account constructor called with wrong parameter order in 3 locations
   (lines 279, 475, 1100). This CORRUPTS all account data. See TODOs at those lines.

2. DATA LOSS ON RESTART - Linked account IDs (PSN, XBL, Steam, Battle), ban info, and can_appeal
   are fetched but NEVER saved to JSON (save_accounts line 707). See TODO at line 708.

3. BROKEN CANCELLATION - Progress dialogs have no cancel button (setCancelButton(None) at line 620)
   but code tries to connect to canceled signal and check wasCanceled(). See TODOs at lines 510, 570, 614, 690.

4. SIGNAL/SLOT TYPE MISMATCH - accounts_updated signal emits a list but save_accounts takes no params,
   causing TypeError at runtime. See TODO at line 503.

5. INCOMPLETE FEATURE - Cookie expiration info only shown for BANNED accounts due to early return.
   Non-banned accounts never see cookie expiry. See TODO at line 824.

6. API KEY TYPO - solve_login_captcha uses "appid" instead of "appId", inconsistent with
   solve_status_check_captcha. May cause API failures. See TODO at line 1112.

7. WRONG BUILD SYSTEM - GitHub workflow tries to build with Go instead of Python. Will always fail.
   See .github/workflows/GoBuild.yml TODOs.

8. MISSING DEPENDENCIES FILE - No requirements.txt file exists for this Python project, making
   installation and CI/CD impossible.
"""
import os
import base64
import json
import sys
import time
from datetime import datetime, timezone
import iso8601
import requests
import undetected_chromedriver as uc
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QInputDialog, QAction, QDialog, QFormLayout, QLineEdit, QDialogButtonBox,
    QApplication, QMainWindow, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QTextEdit,
    QLabel, QListWidget, QMessageBox, QProgressDialog, QFileDialog, QGroupBox, QDockWidget, QGridLayout
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# Constants
# TODO: Dead code - These commented-out path definitions are never used and are redefined at lines 28-29.
# WHY: These lines serve no purpose and create confusion about which constants are actually used.
# FIX: Remove these commented lines entirely to clean up the codebase.
#CHROME = os.path.join(os.path.dirname(sys.executable), "chrome", "chrome.exe")
#DRIVER = os.path.join(os.path.dirname(sys.executable), "chromedriver", "chromedriver.exe")
icon_path = os.path.abspath('icon.ico')
CONFIG_FILE_NAME = "config.json"
ACCOUNTS_FILE_NAME = "accounts.json"
EZ_CAPTCHA_APP_ID = 84291
CHROME = "chrome/chrome.exe"
DRIVER = "chromedriver/chromedriver.exe"
LOGIN_CREDENTIALS_FILE_NAME = "login_credentials.json"
EZ_CAPTCHA_API_URL = "https://api.ez-captcha.com/createTask"
EZ_CAPTCHA_RESULT_URL = "https://api.ez-captcha.com/getTaskResult"
EZ_CAPTCHA_BALANCE_URL = "https://api.ez-captcha.com/getBalance"
ACCOUNT_CHECK_URL = "https://support.activision.com/api/bans/v2/appeal?locale=en"
PROFILE_URL = "https://support.activision.com/api/profile"
LOGIN_URL = "https://s.activision.com/do_login?new_SiteId=activision"
SUPPORT_URL = "https://support.activision.com"
LOGIN_SITE_KEY = "6LfjPWwbAAAAAKhf5D1Ag5nIS-QO2M4rX52LcnDt"
STATUS_SITE_KEY = "6LdB2NUpAAAAANcdcy9YcjBOBD4rY-TIHOeolkkk"
LOGIN_TIMEOUT = 120
CAPTCHA_TIMEOUT = 120

class Config:
    def __init__(self, ez_captcha_key="", login_site_key=LOGIN_SITE_KEY, status_site_key=STATUS_SITE_KEY,
                 login_url=LOGIN_URL, page_url=SUPPORT_URL, extra_options_mode=False):
        self.ez_captcha_key = ez_captcha_key
        self.login_site_key = login_site_key
        self.status_site_key = status_site_key
        self.login_url = login_url
        self.page_url = page_url
        self.extra_options_mode = extra_options_mode

class Account:
    # TODO: Missing attribute initialization - cookie_error and can_appeal are not initialized
    # WHY: These attributes are set conditionally at runtime (cookie_error at line 744, can_appeal at line 730)
    # but never initialized in __init__, causing potential AttributeError or requiring hasattr checks everywhere
    # FIX: Add self.cookie_error = None and self.can_appeal = False to __init__ method
    def __init__(self, email, username, uno_id, sso_cookie, password="", platform="", last_status=""):
        self.email = email
        self.username = username
        self.uno_id = uno_id
        self.sso_cookie = sso_cookie
        self.password = password
        self.platform = platform
        self.last_status = last_status
        self.last_check_time = None
        self.account_age = "Unknown"
        self.psn_id = None
        self.xbl_id = None
        self.steam_id = None
        self.battle_id = None
        self.bans = []
        # TODO: Linked account IDs (psn_id, xbl_id, steam_id, battle_id) are fetched at lines 738-741
        # but are NEVER saved to accounts.json in save_accounts (lines 644-660).
        # WHY: This means linked account data is lost every time the application restarts.
        # FIX: Add psn_id, xbl_id, steam_id, battle_id to the accounts_data dictionary in save_accounts method
        # and load them back in load_accounts method (lines 662-685).

    # TODO: Redundant method - add_status does exactly the same thing as update_status
    # WHY: Both methods set last_status and last_check_time identically. Having two methods is confusing.
    # FIX: Remove add_status and use update_status everywhere, or clarify the distinction if there should be one.
    def add_status(self, status):
        timestamp = datetime.now().isoformat()
        self.last_status = status
        self.last_check_time = timestamp

    def update_status(self, status):
        self.last_status = status
        self.last_check_time = datetime.now().isoformat()

class LoginCredentials:
    def __init__(self, email, password):
        self.email = email
        self.password = password

class AddAccountDialog(QDialog):
    def __init__(self):
        super ().__init__()
        self.setWindowTitle("Add New Account")
        self.setModal(True)
        layout = QFormLayout(self)
        self.email_input = QLineEdit(self)
        self.email_input.setPlaceholderText("Enter email(required only if sso_cookie is not provided)")
        self.password_input = QLineEdit(self)
        self.password_input.setPlaceholderText("Enter password(required only if email is provided)")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.username_input = QLineEdit(self)
        self.username_input.setPlaceholderText("Enter username(optional)")
        self.sso_cookie_input = QLineEdit(self)
        self.sso_cookie_input.setPlaceholderText("Enter SSO Cookie(required if password is not provided)")
        layout.addRow("Email: *", self.email_input)
        layout.addRow("Password: *", self.password_input)
        layout.addRow("Username:", self.username_input)
        layout.addRow("SSO Cookie: *", self.sso_cookie_input)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        helper_text = QLabel("* Required fields")
        helper_text.setStyleSheet("color: gray; font-size: 10px;")
        layout.addRow(helper_text)

    def get_account_info(self):
        return {
            "email":      self.email_input.text(),
            "password":   self.password_input.text(),
            "username":   self.username_input.text(),
            "sso_cookie": self.sso_cookie_input.text(),
        }

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CODStatus Personal Checker")
        self.setGeometry(100, 100, 1000, 600)
        self.setWindowIcon (QIcon (icon_path))
        
        central_widget = QWidget()
        main_layout = QHBoxLayout(central_widget)
        
        left_layout = QVBoxLayout ()
        self.account_list = QListWidget()
        self.account_list.itemClicked.connect(self.display_account_details)
        left_layout.addWidget(QLabel("Accounts:"))
        left_layout.addWidget(self.account_list)
        
        right_layout = QVBoxLayout()
        
        self.account_details = QTextEdit ()
        self.account_details.setReadOnly (True)
        right_layout.addWidget (QLabel ("Account Details:"))
        right_layout.addWidget (self.account_details)
        
        button_grid = QGridLayout()
        
        single_ops_group = QGroupBox("Single Account Operations")
        single_ops_layout = QGridLayout(single_ops_group)
        add_account_btn = QPushButton("Add Account")
        edit_account_btn = QPushButton("Edit Selected Account")
        delete_account_btn = QPushButton("Delete Selected Account")
        check_account_btn = QPushButton("Check Selected Account")
        single_ops_layout.addWidget(add_account_btn, 1, 0, 1, 2)
        single_ops_layout.addWidget(edit_account_btn, 2, 0)
        single_ops_layout.addWidget(delete_account_btn, 2, 1)
        single_ops_layout.addWidget(check_account_btn, 0, 0, 1, 2)
        
        bulk_ops_group = QGroupBox("Bulk Account Operations")
        bulk_ops_layout = QGridLayout(bulk_ops_group)
        check_all_btn = QPushButton("Check All Accounts")
        validate_cookies_btn = QPushButton("Validate SSO Cookies")
        login_update_btn = QPushButton("Login and Update SSO Cookies")
        bulk_ops_layout.addWidget(check_all_btn, 0, 0, 1, 2)
        bulk_ops_layout.addWidget(validate_cookies_btn, 1, 0, 1, 2)
        bulk_ops_layout.addWidget(login_update_btn, 2, 0, 1, 2)

        utility_group = QGroupBox("Utility Functions")
        utility_layout = QGridLayout(utility_group)
        check_balance_btn = QPushButton("Check Captcha Balance")
        refresh_accounts_btn = QPushButton("Refresh Accounts")
        utility_layout.addWidget(check_balance_btn, 0, 0)
        utility_layout.addWidget(refresh_accounts_btn, 1, 0)
        
        # Arrange groups in the main grid
        button_grid.addWidget(single_ops_group, 0, 0, 1, 2)  # Span across two columns
        button_grid.addWidget(bulk_ops_group, 1, 0)
        button_grid.addWidget(utility_group, 1, 1)

        right_layout.addLayout(button_grid)
        main_layout.addLayout (left_layout, 1)
        main_layout.addLayout (right_layout, 2)
        self.setCentralWidget (central_widget)
        self.create_log_window ()
        self.setup_menu()
        
        add_account_btn.clicked.connect(self.add_account)
        edit_account_btn.clicked.connect(self.edit_selected_account)
        delete_account_btn.clicked.connect(self.delete_selected_account)
        check_account_btn.clicked.connect(self.check_selected_account)
        check_all_btn.clicked.connect(self.run_check_accounts)
        validate_cookies_btn.clicked.connect(self.validate_sso_cookies)
        login_update_btn.clicked.connect(self.login_and_update_sso)
        check_balance_btn.clicked.connect(self.run_check_captcha_balance)
        refresh_accounts_btn.clicked.connect(self.refresh_accounts)
        
        self.load_config ()
        if not self.check_api_key ():
            self.get_api_key ()
        self.load_accounts ()
        self.load_login_credentials ()
        self.update_account_list ()
    
    def setup_menu ( self ):
        menubar = self.menuBar ()
        file_menu = menubar.addMenu ("File")
        settings_menu = menubar.addMenu ("Settings")
        self.toggle_log_action = QAction("Show Log Window", self, checkable=True)
        self.toggle_log_action.setChecked(False)
        load_credentials_action = QAction ("Load Credentials from File", self)
        save_log_action = QAction ("Save Log", self)
        extra_options_mode = QAction ("Extra Options Mode", self, checkable = True)
        change_api_key_action = QAction ("Change API Key", self)
        change_api_key_action.triggered.connect (self.get_api_key)
        self.toggle_log_action.triggered.connect (self.toggle_log_window)
        load_credentials_action.triggered.connect (self.load_credentials_from_file)
        save_log_action.triggered.connect (self.save_log)
        extra_options_mode.triggered.connect (self.toggle_extra_options_mode)
        file_menu.addAction (load_credentials_action)
        file_menu.addAction(save_log_action)
        settings_menu.addAction (self.toggle_log_action)
        settings_menu.addAction(change_api_key_action)
        settings_menu.addAction(extra_options_mode)
        extra_options_mode.setChecked(config.extra_options_mode)
    
    def toggle_log_window(self, state):
        if state:
            self.log_dock.show()
            self.toggle_log_action.setText("Hide Log Window")
        else:
            self.log_dock.hide()
            self.toggle_log_action.setText("Show Log Window")

    def create_log_window(self):
        self.log_dock = QDockWidget("Log", self)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_dock.setWidget(self.log_text)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.log_dock)
        self.log_dock.hide()

    def add_account(self):
        dialog = AddAccountDialog ()
        if dialog.exec_():
            account_info = dialog.get_account_info()
            existing_account = next((acc for acc in accounts if acc.email == account_info ["email"]), None)
            if existing_account:
                reply = QMessageBox.question(
                    self,
                    "Account Exists",
                    f"An account with email {account_info ['email']} already exists. Do you want to update it?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No)
                if reply == QMessageBox.Yes:
                    existing_account.username = account_info ["username"]
                    existing_account.sso_cookie = account_info ["sso_cookie"]
                    self.log(f"Updated existing account: {account_info ['email']}")
                else:
                    self.log(f"Account not added: {account_info ['email']}(already exists)")
                    return
            else:
                # TODO: CRITICAL BUG - Account constructor parameters are in WRONG ORDER
                # WHY: Account.__init__ signature is (email, username, uno_id, sso_cookie, password, platform, last_status)
                # but this call passes sso_cookie as uno_id, password as sso_cookie, and empty string as password.
                # This will cause all account data to be corrupted and authentication to fail.
                # FIX: Change to Account(account_info["email"], account_info["username"], "", account_info["sso_cookie"], account_info["password"], "", "")
                # or better yet: Account(email, username, uno_id="", sso_cookie=sso_cookie, password=password, platform="", last_status="")
                new_account = Account(
                    account_info ["email"],
                    account_info ["username"],
                    account_info ["sso_cookie"],
                    account_info ["password"],
                    "")
                accounts.append(new_account)
                self.log(f"Added new account: {account_info ['email']}")

            existing_cred = next((cred for cred in login_credentials if cred.email == account_info ["email"]), None)
            if existing_cred:
                existing_cred.password = account_info ["password"]
            else:
                login_credentials.append(LoginCredentials(account_info ["email"], account_info ["password"]))
            
            self.update_account_list()
            self.save_accounts()
            self.save_login_credentials()
    
    def save_login_credentials(self):
        cred_data = [{"email": cred.email, "password": cred.password} for cred in login_credentials]
        with open(LOGIN_CREDENTIALS_FILE_NAME, "w") as f:
            json.dump(cred_data, f, indent=2)
        self.log("Login credentials saved successfully.")

    def load_config(self):
        try:
            with open(CONFIG_FILE_NAME, "r") as f:
                config_data = json.load(f)
                config.ez_captcha_key = config_data.get("ez_captcha_key", "")
                config.login_site_key = config_data.get("login_site_key", LOGIN_SITE_KEY)
                config.status_site_key = config_data.get("status_site_key", STATUS_SITE_KEY)
                config.login_url = config_data.get("login_url", LOGIN_URL)
                config.page_url = config_data.get("page_url", SUPPORT_URL)
                config.extra_options_mode = config_data.get("extra_options_mode", False)
            self.log("Config loaded successfully")
        except FileNotFoundError:
            self.log(f"Config file {CONFIG_FILE_NAME} not found. Using default values.")
        except json.JSONDecodeError:
            self.log(f"Error parsing {CONFIG_FILE_NAME}. Using default values.")

    def save_config(self):
        config_data = {
            "ez_captcha_key":  config.ez_captcha_key,
            "login_site_key":  config.login_site_key,
            "status_site_key": config.status_site_key,
            "login_url": config.login_url,
            "page_url": config.page_url,
            "extra_options_mode": config.extra_options_mode,
        }
        with open(CONFIG_FILE_NAME, "w") as f:
            json.dump(config_data, f, indent = 2)
        self.log("Config saved successfully")
    
    def edit_selected_account(self):
        selected_item = self.account_list.currentItem()
        if selected_item:
            email = selected_item.text()
            account = next((acc for acc in accounts if acc.email == email), None)
            if account:
                dialog = AddAccountDialog()
                dialog.email_input.setText(account.email)
                dialog.email_input.setReadOnly(True)
                dialog.password_input.setText(account.password)
                dialog.username_input.setText(account.username)
                dialog.sso_cookie_input.setText(account.sso_cookie)
                if dialog.exec_():
                    account_info = dialog.get_account_info()
                    account.password = account_info["password"]
                    account.username = account_info["username"]
                    account.sso_cookie = account_info["sso_cookie"]
                    self.save_accounts()
                    self.update_account_list()
                    self.log(f"Account updated: {account.email}")
            else:
                self.log("Selected account not found.")
        else:
            self.log("No account selected.")
    
    def save_log(self):
        file_name, _ = QFileDialog.getSaveFileName(
            self, "Save Log", "", "Text Files(*.txt);;All Files(*)"
        )
        if file_name:
            with open(file_name, "w") as f:
                f.write(self.log_text.toPlainText())
            self.log(f"Log saved to {file_name}")

    def refresh_accounts(self):
        self.load_accounts()
        self.load_login_credentials()
        self.update_account_list()
        self.log("Accounts refreshed")

    def toggle_extra_options_mode(self, state):
        config.extra_options_mode = state
        self.save_config()
        self.log(f"Extra Options Mode {'enabled' if state else 'disabled'}")

    # TODO: Dead code - set_busy method is defined but NEVER called anywhere in the application
    # WHY: This method was likely intended to show a busy cursor and disable UI during long operations,
    # but progress dialogs are used instead (e.g., lines 466, 482, 526, 623).
    # FIX: Either remove this method if it's truly unused, or integrate it into long-running operations
    # by calling self.set_busy(True) before operations and self.set_busy(False) after completion.
    def set_busy(self, busy):
        QApplication.setOverrideCursor(Qt.WaitCursor if busy else Qt.ArrowCursor)
        self.setEnabled(not busy)

    def log(self, message):
        timestamp = time.strftime("%Y-%m-%d %H:%M")
        log_message = f"[{timestamp}] {message}"
        self.log_text.append(log_message)
        print(log_message)
    
    def check_api_key(self):
        self.log(f"EZ-Captcha API Key Set: {bool(config.ez_captcha_key)}")
        return bool(config.ez_captcha_key)
    
    def get_api_key(self):
        api_key, ok = QInputDialog.getText(
            self, "API Key", "Enter your EZ-Captcha API Key:"
        )
        if ok and api_key:
            config.ez_captcha_key = api_key
            self.save_config()
            self.log("API Key updated successfully")
        elif not ok:
            self.log("API Key input cancelled")
        else:
            self.log("No API Key entered")

    def get_ez_captcha_balance(self):
        payload = {"clientKey": config.ez_captcha_key}
        try:
            response = requests.post(EZ_CAPTCHA_BALANCE_URL, json=payload)
            response.raise_for_status()
            data = response.json()
            if data.get("errorId", 0) != 0:
                self.log(f"API error: {data.get('errorDescription', 'Unknown error')}")
                return None
            return f"{data.get('balance', 0):.2f}"
        except requests.RequestException as e:
            self.log(f"HTTP error checking balance: {str(e)}")
            return None
        except Exception as e:
            self.log(f"Error checking balance: {str(e)}")
            return None
    
    def run_check_captcha_balance(self):
        self.log("Checking captcha balance...")
        balance = self.get_ez_captcha_balance()
        if balance:
            message = f"EZ-Captcha balance: {balance}"
            self.log(message)
            QMessageBox.information(self, "Captcha Balance", message)
        else:
            self.log("Failed to retrieve EZ-Captcha balance")
            QMessageBox.warning(self, "Captcha Balance", "Failed to retrieve balance")
    
    def load_login_credentials(self):
        login_credentials.clear()
        try:
            with open(LOGIN_CREDENTIALS_FILE_NAME, "r") as f:
                cred_data = json.load(f)
                for cred in cred_data:
                    login_credentials.append(
                        LoginCredentials(cred["email"], cred["password"])
                    )
            self.log(f"Loaded {len(login_credentials)} login credentials")
        except FileNotFoundError:
            self.log(f"Login credentials file {LOGIN_CREDENTIALS_FILE_NAME} not found.")
        except json.JSONDecodeError:
            self.log(f"Error parsing {LOGIN_CREDENTIALS_FILE_NAME}.")
    
    def load_credentials_from_file(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Load Credentials", "", "JSON Files (*.json);;All Files (*)")
        if file_name:
            try:
                with open(file_name, 'r') as f:
                    cred_data = json.load(f)
                accounts_updated = 0
                accounts_added = 0
                for cred in cred_data:
                    email = cred.get('email')
                    password = cred.get('password')
                    if email and password:
                        existing_account = next((acc for acc in accounts if acc.email == email), None)
                        if existing_account:
                            existing_account.password = password
                            accounts_updated += 1
                        else:
                            # TODO: CRITICAL BUG - Account constructor parameters are in WRONG ORDER
                            # WHY: Account.__init__ signature is (email, username, uno_id, sso_cookie, password, platform, last_status)
                            # but this call passes empty strings for username, uno_id, sso_cookie, and then password as platform parameter.
                            # This will corrupt account data and prevent authentication from working.
                            # FIX: Change to Account(email, "", "", "", password, "", "") with password in the correct 5th position.
                            new_account = Account(email, "", "", "", password)
                            accounts.append(new_account)
                            accounts_added += 1
                        existing_cred = next((cred for cred in login_credentials if cred.email == email), None)
                        if existing_cred:
                            existing_cred.password = password
                        else:
                            login_credentials.append(LoginCredentials(email, password))
                self.save_accounts()
                self.save_login_credentials()
                self.update_account_list()
                self.log(f"Loaded credentials from file: {accounts_updated} updated, {accounts_added} added")
                QMessageBox.information(self, "Credentials Loaded", f"Updated {accounts_updated} accounts\nAdded {accounts_added} new accounts")
            except json.JSONDecodeError:
                self.log("Error: The selected file is not a valid JSON file.")
                QMessageBox.warning(self, "Error", "The selected file is not a valid JSON file.")
            except Exception as e:
                self.log(f"Error loading credentials: {str(e)}")
                QMessageBox.warning(self, "Error", f"An error occurred while loading credentials: {str(e)}")

    def run_check_accounts(self):
        self.log("Starting account status check...")
        self.progress_dialog = self.show_progress_dialog("Checking Accounts")
        self.progress_dialog.setMaximum(len(accounts))
        self.check_accounts_thread = CheckAccountsThread(accounts, config)
        self.check_accounts_thread.log_message.connect(self.log)
        self.check_accounts_thread.progress_updated.connect(self.update_progress)
        self.check_accounts_thread.finished.connect(self.on_check_accounts_finished)
        # TODO: CRITICAL BUG - Signal/slot parameter mismatch will cause TypeError at runtime
        # WHY: accounts_updated signal emits self.accounts (a list) at line 710, but save_accounts method
        # (line 644) takes NO parameters. PyQt will raise TypeError when trying to call save_accounts(list).
        # FIX: Either change signal emission to emit no parameters, or create a wrapper slot that ignores the parameter,
        # e.g., lambda _: self.save_accounts() or change save_accounts to accept an optional parameter.
        self.check_accounts_thread.accounts_updated.connect(self.save_accounts)
        self.check_accounts_thread.start()
        # TODO: Broken cancel functionality - progress dialog has no cancel button but we connect to canceled signal
        # WHY: At line 569, setCancelButton(None) removes the cancel button from progress dialogs, so the
        # canceled signal will NEVER be emitted, making this connection useless.
        # FIX: Either remove setCancelButton(None) and add a cancel button to progress dialogs, or remove
        # all .canceled.connect() calls and cancel logic from threads.
        self.progress_dialog.canceled.connect(self.check_accounts_thread.cancel)
        
    def check_selected_account(self):
        selected_item = self.account_list.currentItem()
        if selected_item:
            email = selected_item.text()
            account = next((acc for acc in accounts if acc.email == email), None)
            if account:
                self.progress_dialog = self.show_progress_dialog("Checking Account")
                self.check_accounts_thread = CheckAccountsThread([account], config)
                self.check_accounts_thread.log_message.connect(self.log)
                self.check_accounts_thread.progress_updated.connect(self.update_single_account_progress)
                self.check_accounts_thread.finished.connect(self.on_single_account_check_finished)
                self.check_accounts_thread.start()
            else:
                self.log("No account selected or account not found.")
        else:
            self.log("Please select an account to check.")
    
    def update_single_account_progress(self, value):
        if hasattr(self, "progress_dialog"):
            self.progress_dialog.setValue(value)
    
    def on_single_account_check_finished(self):
        if hasattr(self, "progress_dialog"):
            self.progress_dialog.close()
        self.log("Single account check completed.")
        self.update_account_list()
        self.save_accounts()

    def delete_selected_account(self):
        selected_item = self.account_list.currentItem()
        if selected_item:
            email = selected_item.text()
            reply = QMessageBox.question(self, 'Confirm Deletion',
                                          f"Are you sure you want to delete the account: {email}?",
                                          QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                account = next((acc for acc in accounts if acc.email == email), None)
                if account:
                    accounts.remove(account)
                    self.update_account_list()
                    self.save_accounts()
                    self.log(f"Account {email} deleted.")

    def update_account_list(self):
        self.account_list.clear()
        for account in accounts:
            self.account_list.addItem(account.email)

    def validate_sso_cookies(self):
        self.log("Starting SSO cookie validation...")
        self.progress_dialog = self.show_progress_dialog("Validating SSO Cookies")
        self.progress_dialog.setMaximum(len(accounts))
        for i, account in enumerate(accounts):
            # TODO: Broken cancel check - wasCanceled() will always return False
            # WHY: Progress dialog created at line 566 has setCancelButton(None) at line 569,
            # so there's no cancel button and wasCanceled() will never return True.
            # FIX: Either add a cancel button by changing/removing setCancelButton(None), or remove this check.
            if self.progress_dialog.wasCanceled():
                break
            self.progress_dialog.setValue(i)
            is_valid = self.validate_sso_cookie(account.sso_cookie)
            status = "Valid" if is_valid else "Invalid"
            self.log(f"{account.email}: SSO Cookie is {status}")
            if not is_valid:
                account.sso_cookie = ""
        self.progress_dialog.setValue(len(accounts))
        self.save_accounts()
        self.load_accounts()
        self.update_account_list()
        self.log("SSO cookie validation completed.")

    def validate_sso_cookie(self, sso_cookie):
        url = "https://support.activision.com/api/profile"
        headers = {"Cookie": f"ACT_SSO_COOKIE={sso_cookie}"}
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                content = response.text
                if content.strip():  # Check if the response body is not empty
                    return True
                else:
                    self.log(f"SSO cookie expired or invalid (empty response)")
                    return False
            elif response.status_code == 401:
                self.log(f"SSO cookie invalid (401 Unauthorized)")
                return False
            else:
                self.log(f"Unexpected status code: {response.status_code}")
                return False
        except requests.RequestException as e:
            self.log(f"Error during SSO cookie validation: {str(e)}")
            return False

    def show_progress_dialog(self, title):
        progress_dialog = QProgressDialog(self)
        progress_dialog.setWindowTitle(title)
        progress_dialog.setRange(0, 100)
        # TODO: Inconsistent cancel button configuration breaks cancel functionality throughout the app
        # WHY: setCancelButton(None) removes the cancel button, but multiple places in the code try to
        # connect to progress_dialog.canceled signal (lines 515, 665) and check wasCanceled() (line 574).
        # These will never work because there's no cancel button to trigger the canceled signal.
        # FIX: Either remove this line to enable cancel buttons, or remove all cancel-related code
        # (canceled.connect calls and wasCanceled checks) throughout the application.
        progress_dialog.setCancelButton(None)
        progress_dialog.setWindowModality(Qt.WindowModal)
        return progress_dialog

    def on_check_accounts_finished(self):
        if hasattr(self, "progress_dialog"):
            self.progress_dialog.close()
        self.log("Account checking completed.")
    
    def display_account_details(self, item):
        email = item.text()
        account = next((acc for acc in accounts if acc.email == email), None)
        if account:
            details = []
            details.append(f"Email: {account.email}")
            if account.username:
                details.append(f"Username: {account.username}")
            if account.uno_id:
                details.append(f"UNO ID: {account.uno_id}")
            if account.sso_cookie:
                details.append(f"SSO Cookie: {account.sso_cookie[:30]}...")
            if account.last_status:
                details.append(f"Last Status: {account.last_status}")
            if account.last_check_time:
                details.append(f"Last Checked: {account.last_check_time}")
            if account.account_age:
                details.append(f"Account Age: {account.account_age}")
            linked_accounts = []
            # TODO: Redundant hasattr checks - these attributes are always initialized in Account.__init__
            # WHY: psn_id, xbl_id, steam_id, and battle_id are initialized to None in Account.__init__ (lines 71-74),
            # so hasattr will always return True. These checks are unnecessary overhead.
            # FIX: Remove hasattr checks and just check truthiness: if account.psn_id: ...
            if hasattr(account, 'psn_id') and account.psn_id:
                linked_accounts.append(f"- psn: {account.psn_id}")
            if hasattr(account, 'xbl_id') and account.xbl_id:
                linked_accounts.append(f"- xbl: {account.xbl_id}")
            if hasattr(account, 'steam_id') and account.steam_id:
                linked_accounts.append(f"- steam: {account.steam_id}")
            if hasattr(account, 'battle_id') and account.battle_id:
                linked_accounts.append(f"- battle: {account.battle_id}")
            if linked_accounts:
                details.append("\nLinked Accounts:")
                details.extend(linked_accounts)
            if hasattr(account, 'bans') and account.bans:
                details.append("\nBan Information:")
                for ban in account.bans:
                    ban_info = f"- {ban.get('title', 'Unknown Game')}: {ban.get('enforcement', 'Unknown')}"
                    if 'bar' in ban:
                        ban_info += f" (Appeal Status: {ban['bar'].get('Status', 'Unknown')})"
                    details.append(ban_info)
            self.account_details.setText("\n".join(details))
        else:
            self.account_details.setText("No account selected or account not found.")
        # TODO: cookie_error is logged but never displayed in the UI details
        # WHY: cookie_error is set at line 744 when cookie decoding fails, but it's only logged here
        # and never added to the details list shown in the account_details text edit.
        # FIX: Add cookie error to the details list if it exists, e.g., details.append(f"Cookie Error: {account.cookie_error}")
        # Also, cookie_error attribute is not initialized in Account.__init__ (see TODO at line 57).
        if account and hasattr(account, 'cookie_error') and account.cookie_error:
            self.log(f"Cookie Error for {account.email}: {account.cookie_error}")

    def login_and_update_sso(self):
        self.log("Starting login process...")
        self.progress_dialog = self.show_progress_dialog("Logging In")
        self.progress_dialog.setMaximum(len(login_credentials))
        self.login_thread = LoginThread(login_credentials, accounts, config, self.save_accounts)
        self.login_thread.progress_updated.connect(self.update_progress)
        self.login_thread.log_message.connect(self.log)
        self.login_thread.finished.connect(self.on_login_finished)
        self.login_thread.start()
        # TODO: Broken cancel functionality - progress dialog has no cancel button (see TODO at line 614)
        # WHY: setCancelButton(None) in show_progress_dialog means canceled signal will never be emitted.
        # FIX: Remove this line or fix show_progress_dialog to include a cancel button.
        self.progress_dialog.canceled.connect(self.login_thread.cancel)

    def update_progress(self, value):
        if hasattr(self, "progress_dialog"):
            self.progress_dialog.setValue(value)
    
    def on_login_finished(self):
        self.log("Login process completed.")
        self.save_accounts()
        self.load_accounts()
        self.update_account_list()
        if hasattr(self, 'progress_dialog'):
            self.progress_dialog.close()

    def save_accounts(self):
        # TODO: Critical data loss - multiple account attributes are NOT saved to JSON
        # WHY: The following attributes are fetched/set during runtime but never persisted:
        # - psn_id, xbl_id, steam_id, battle_id (set at lines 738-741)
        # - bans list (set at line 731)
        # - can_appeal (set at line 730)
        # - password (stored in Account object but not saved here, causing loss on app restart)
        # This means all linked account IDs, ban information, and passwords are lost when the app closes.
        # FIX: Add these fields to the accounts_data dictionary: "psn_id": account.psn_id, "xbl_id": account.xbl_id,
        # "steam_id": account.steam_id, "battle_id": account.battle_id, "bans": account.bans,
        # "can_appeal": getattr(account, 'can_appeal', False), "password": account.password
        accounts_data = [
            {
                "email": account.email,
                "username": account.username,
                "uno_id": account.uno_id,
                "sso_cookie": account.sso_cookie,
                "platform": account.platform,
                "last_status": account.last_status,
                "last_check_time": account.last_check_time,
                "account_age": account.account_age
            }
            for account in accounts
        ]
        with open(ACCOUNTS_FILE_NAME, "w") as f:
            json.dump(accounts_data, f, indent=2)
        self.log("Accounts saved successfully.")

    def load_accounts(self):
        global accounts
        accounts.clear()
        try:
            with open(ACCOUNTS_FILE_NAME, "r") as f:
                accounts_data = json.load(f)
                for acc_data in accounts_data:
                    new_account = Account(
                        acc_data["email"],
                        acc_data["username"],
                        acc_data["uno_id"],
                        acc_data["sso_cookie"],
                        acc_data.get("password", ""),
                        acc_data.get("platform", ""),
                        acc_data.get("last_status", "")
                    )
                    new_account.last_check_time = acc_data.get("last_check_time")
                    new_account.account_age = acc_data.get("account_age", "Unknown")
                    # TODO: Missing attribute loading - psn_id, xbl_id, steam_id, battle_id, bans, can_appeal are never loaded
                    # WHY: These attributes are not saved in save_accounts (see TODO at line 708), so even if they were
                    # in the JSON, they wouldn't be loaded here. This creates incomplete account restoration on app restart.
                    # FIX: After fixing save_accounts to save these fields, add loading code here:
                    # new_account.psn_id = acc_data.get("psn_id")
                    # new_account.xbl_id = acc_data.get("xbl_id")
                    # new_account.steam_id = acc_data.get("steam_id")
                    # new_account.battle_id = acc_data.get("battle_id")
                    # new_account.bans = acc_data.get("bans", [])
                    # new_account.can_appeal = acc_data.get("can_appeal", False)
                    accounts.append(new_account)
            self.log(f"Loaded {len(accounts)} accounts")
        except FileNotFoundError:
            self.log(f"Accounts file {ACCOUNTS_FILE_NAME} not found.")
        except json.JSONDecodeError:
            self.log(f"Error parsing {ACCOUNTS_FILE_NAME}.")

class CheckAccountsThread(QThread):
    progress_updated = pyqtSignal(int)
    log_message = pyqtSignal(str)
    finished = pyqtSignal()
    # TODO: Unused signal parameter - accounts_updated emits a list that is never used by connected slots
    # WHY: This signal is emitted with self.accounts at line 710, but connected to save_accounts at line 508
    # which takes NO parameters, causing a TypeError. The list parameter serves no purpose.
    # FIX: Change to pyqtSignal() without parameters, and emit without arguments at line 710.
    accounts_updated = pyqtSignal(list)
    
    def __init__(self, accounts, config):
        super().__init__()
        self.accounts = accounts
        self.config = config
        self.is_cancelled = False

    def run(self):
        for i, account in enumerate(self.accounts):
            if self.is_cancelled:
                break
            self.progress_updated.emit(i * 100 // len(self.accounts))
            ban_status = self.check_account(account)
            account.add_status(ban_status)
            self.log_message.emit(f"{account.email}: {ban_status}")
            age_status = self.check_account_age(account)
            account.account_age = age_status
            self.log_message.emit(f"{account.email} Age: {age_status}")
            self.accounts_updated.emit(self.accounts)
            time.sleep(1)
        self.progress_updated.emit(100)
        self.finished.emit()

    def check_account(self, account):
        captcha_response = self.solve_status_check_captcha()
        if not captcha_response:
            return "Failed to solve status check captcha"
        headers = {
            "Cookie": f"ACT_SSO_COOKIE={account.sso_cookie}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3",
        }
        params = {"g-cc": captcha_response}
        try:
            response = requests.get(ACCOUNT_CHECK_URL, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            if data.get("error"):
                return f"API error: {data['error']}"
            # TODO: can_appeal attribute is set but NEVER saved or used elsewhere in the application
            # WHY: This attribute is set here but not persisted in save_accounts (line 707) and not displayed
            # in account details (display_account_details at line 628). It's completely unused.
            # FIX: Either save this attribute and display it in the UI, or remove this line if it's not needed.
            account.can_appeal = data.get('canAppeal', False)
            account.bans = data.get('bans', [])
            if not account.bans:
                # TODO: Critical bug - Cookie expiration info is ONLY shown for banned accounts
                # WHY: Early return here prevents cookie_status from being calculated and returned for non-banned accounts.
                # Users with clean accounts never see their cookie expiration time, making it hard to know when re-login is needed.
                # FIX: Move cookie decoding logic (lines 830-844) before the ban check and include it in the return value for all accounts.
                return "Account not banned"
            status = self.determine_ban_status(account.bans)
            profile_response = requests.get(PROFILE_URL, headers=headers)
            if profile_response.status_code == 200:
                profile_data = profile_response.json()
                # TODO: Potential exception - profile_data.get('accounts', []) may contain dicts without 'provider' or 'username' keys
                # WHY: The next() comprehension assumes all account dicts have 'provider' and 'username' keys.
                # If a malformed account dict is returned by the API, accessing acc['provider'] will raise KeyError.
                # FIX: Use acc.get('provider') and acc.get('username') instead of direct key access.
                account.psn_id = next((acc['username'] for acc in profile_data.get('accounts', []) if acc['provider'] == 'psn'), None)
                account.xbl_id = next((acc['username'] for acc in profile_data.get('accounts', []) if acc['provider'] == 'xbl'), None)
                account.steam_id = next((acc['username'] for acc in profile_data.get('accounts', []) if acc['provider'] == 'steam'), None)
                account.battle_id = next((acc['username'] for acc in profile_data.get('accounts', []) if acc['provider'] == 'battle'), None)
            cookie_status = self.decode_sso_cookie(account.sso_cookie)
            if "Error decoding cookie" in cookie_status:
                account.cookie_error = cookie_status
            else:
                status += f"\n{cookie_status}"
            return status
        except Exception as e:
            # TODO: Overly broad exception handling masks specific errors
            # WHY: Catching all Exception types makes debugging difficult and can hide serious issues like
            # network errors, authentication failures, or JSON parsing errors. Users only see "Error: ..."
            # without understanding what went wrong or how to fix it.
            # FIX: Catch specific exceptions (requests.RequestException, json.JSONDecodeError, KeyError, etc.)
            # and provide actionable error messages for each type.
            return f"Error: {str(e)}"

    def determine_ban_status(self, bans):
        # TODO: Potential KeyError - assumes all ban dicts have 'enforcement' key
        # WHY: Lines 851 and 858 directly access ban["enforcement"] without using .get(), which will
        # raise KeyError if the API returns a malformed ban dict without this field.
        # FIX: Use ban.get("enforcement", "UNKNOWN") instead of ban["enforcement"].
        if any(ban["enforcement"] == "PERMANENT" for ban in bans):
            if any(ban.get("bar", {}).get("Status") == "Open" for ban in bans):
                return "Permanently banned (Appeal Open)"
            elif any(ban.get("bar", {}).get("Status") == "Closed" for ban in bans):
                return "Permanently banned (Appeal Denied)"
            else:
                return "Permanently banned"
        elif any(ban["enforcement"] == "UNDER_REVIEW" for ban in bans):
            return "Shadowbanned"
        else:
            return f"Unknown ban status: {bans[0]['enforcement']}"
    
    def check_account_age(self, account):
        headers = {
            "Cookie": f"ACT_SSO_COOKIE={account.sso_cookie}",
            "User-Agent": "Mozilla/5.0(Windows NT 10.0; Win64; x64) AppleWebKit/537.36(KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3",
        }
        try:
            response = requests.get(PROFILE_URL, headers=headers)
            response.raise_for_status()
            profile_data = response.json()
            created_date = profile_data.get("created")
            if created_date:
                created = iso8601.parse_date(created_date)
                now = datetime.now(timezone.utc)
                age = now - created
                # TODO: Inaccurate date calculation - assumes all months have 30 days
                # WHY: Using (age.days % 365) // 30 for months incorrectly treats all months as 30 days,
                # causing inaccurate age calculations. A year doesn't have exactly 12 * 30 = 360 days.
                # FIX: Use relativedelta from dateutil.relativedelta for accurate year/month/day calculations,
                # or at minimum document that ages are approximate.
                years = age.days // 365
                months =(age.days % 365) // 30
                days =(age.days % 365) % 30
                return f"{years} years, {months} months, {days} days"
            else:
                return "Unknown"
        except Exception as e:
            # TODO: Overly broad exception handling - same issue as check_account method (see TODO at line 848)
            # FIX: Catch specific exceptions for better error reporting.
            return f"Error: {str(e)}"

    def decode_sso_cookie(self, sso_cookie):
        try:
            decoded_cookie = base64.b64decode(sso_cookie).decode('utf-8')
            parts = decoded_cookie.split(':')
            if len(parts) != 3:
                return "Unexpected cookie format"

            account_id, expiration_timestamp, hash_value = parts
            # TODO: Potential ValueError - int() conversion can fail on malformed timestamp
            # WHY: If expiration_timestamp contains non-numeric characters or is malformed,
            # int(expiration_timestamp) will raise ValueError, jumping to the generic exception handler.
            # FIX: Validate that expiration_timestamp is numeric before converting, or catch ValueError
            # specifically to provide a clear "Invalid cookie timestamp format" message.
            expiration_date = datetime.fromtimestamp(int(expiration_timestamp), tz = timezone.utc)
            now = datetime.now(timezone.utc)
            time_left = expiration_date - now

            if time_left.total_seconds() > 0:
                days_left = time_left.days
                hours_left = time_left.seconds // 3600
                minutes_left =(time_left.seconds % 3600) // 60
                return f"Cookie expires in: {days_left} days, {hours_left} hours, {minutes_left} minutes"
            else:
                return "Cookie has expired"
        except Exception as e:
            # TODO: Overly broad exception handling - catches base64 errors, decode errors, and conversion errors together
            # WHY: Different error types (base64.binascii.Error, UnicodeDecodeError, ValueError) have different
            # causes and solutions, but all are reported as generic "Error decoding cookie".
            # FIX: Catch specific exceptions and provide targeted error messages for each failure mode.
            return f"Error decoding cookie: {str(e)}"

    def solve_status_check_captcha(self):
        create_task_payload = {
            "clientKey": self.config.ez_captcha_key,
            "appId": EZ_CAPTCHA_APP_ID,
            "task": {
                "type": "ReCaptchaV2TaskProxyless",
                "websiteURL": self.config.page_url,
                "websiteKey": self.config.status_site_key,
                "isInvisible": False,
            },
        }
        try:
            response = requests.post(EZ_CAPTCHA_API_URL, json=create_task_payload)
            response.raise_for_status()
            create_task_result = response.json()
            if create_task_result.get("errorId") != 0:
                self.log_message.emit(f"Error creating captcha task: {create_task_result.get('errorDescription')}")
                return None
            task_id = create_task_result["taskId"]
            get_result_payload = {
                "clientKey": self.config.ez_captcha_key,
                "taskId": task_id,
            }
            start_time = time.time()
            while time.time() - start_time < CAPTCHA_TIMEOUT:
                response = requests.post(EZ_CAPTCHA_RESULT_URL, json=get_result_payload)
                response.raise_for_status()
                result = response.json()
                if result.get("status") == "ready":
                    return result.get("solution", {}).get("gRecaptchaResponse")
                elif result.get("status") == "processing":
                    time.sleep(10)
                else:
                    self.log_message.emit(f"Unexpected captcha status: {result.get('status')}")
                    return None
            self.log_message.emit("Captcha solving timed out")
        except requests.RequestException as e:
            self.log_message.emit(f"HTTP error occurred: {e}")
        except Exception as e:
            self.log_message.emit(f"Error solving status captcha: {str(e)}")
        return None

    def cancel(self):
        self.is_cancelled = True
        
class LoginThread(QThread):
    log_message = pyqtSignal(str)
    finished = pyqtSignal()
    progress_updated = pyqtSignal(int)

    def __init__(self, login_credentials, accounts, config, save_accounts_func):
        super().__init__()
        self.login_credentials = login_credentials
        self.accounts = accounts
        self.config = config
        self.save_accounts = save_accounts_func
        self.is_cancelled = False

        # TODO: Redundant attribute assignment - DRIVER and CHROME are already defined as module-level constants
        # WHY: These exact same values are defined at lines 28-29 as CHROME and DRIVER constants.
        # Duplicating them as instance attributes is unnecessary and creates maintenance burden.
        # FIX: Remove these lines and use the module-level constants directly (DRIVER and CHROME).
        self.DRIVER = "chromedriver/chromedriver.exe"
        self.CHROME = "chrome/chrome.exe"

    def run(self):
        total_accounts = len(self.login_credentials)
        for i, cred in enumerate(self.login_credentials):
            if self.is_cancelled:
                break
            self.progress_updated.emit(i * 100 // total_accounts)
            try:
                self.log_message.emit(f"Logging in for account: {cred.email}")
                success, account_info = self.perform_login(cred)
                if success:
                    self.update_account(account_info)
                    self.save_accounts()
                    self.log_message.emit(f"Successfully logged in and updated info for {cred.email}")
                else:
                    self.log_message.emit(f"Failed to log in for {cred.email}")
            except Exception as e:
                self.log_message.emit(f"Error processing account {cred.email}: {str(e)}")
            finally:
                progress = int((i + 1) / total_accounts * 100)
                self.progress_updated.emit(progress)
        self.finished.emit()

    def cancel(self):
        self.is_cancelled = True

    def perform_login(self, cred):
        options = uc.ChromeOptions()
        options.binary_location = self.CHROME
        if self.config.extra_options_mode:
            options.add_argument('--start-minimized')
            # TODO: Dead code - Multiple Chrome options are commented out and serve no purpose
            # WHY: These commented-out options suggest incomplete feature implementation or abandoned configuration.
            # They provide no value and clutter the codebase, making it unclear what extra_options_mode actually does.
            # FIX: Either uncomment and enable these options if they're needed for extra_options_mode functionality,
            # or remove them entirely to clean up the code. Document what extra_options_mode is supposed to do.
            #options.add_argument('--enable-fast-unload')
            #options.add_argument('--disable-gpu')
            #options.add_argument('--enable-precache')
            #options.add_argument('--allow-cross-origin-auth-prompt')
            #options.add_argument('--disable-low-res-tiling')
            #options.add_argument('--no-sandbox')
            #options.add_argument('--enable-automation')
            #options.add_argument('--disable-blink-features=AutomationControlled')
            #options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--window-size=200,100')
        driver = None
        try:
            # TODO: Missing error handling - ChromeDriver initialization can fail in multiple ways
            # WHY: If chromedriver.exe is missing, wrong version, or Chrome binary is not found,
            # uc.Chrome() will raise exceptions that aren't caught here, causing the entire thread to crash.
            # FIX: Add try-except around driver initialization with specific error messages for common failures
            # (missing chromedriver, version mismatch, missing Chrome binary).
            driver = uc.Chrome(options=options, driver_executable_path=self.DRIVER)
            driver.get(SUPPORT_URL)
            login_link = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, ".log-in-link"))
            )
            login_link.click()
            WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.ID, "username")))
            driver.find_element(By.ID, "username").send_keys(cred.email)
            driver.find_element(By.ID, "password").send_keys(cred.password)
            captcha_response = self.solve_login_captcha()
            if not captcha_response:
                self.log_message.emit("Failed to solve captcha")
                return False, None
            # TODO: Potential XSS/injection risk - captcha_response is inserted into JavaScript without escaping
            # WHY: If captcha_response contains quotes or special characters, it could break the JavaScript
            # string literal and cause syntax errors or unexpected behavior. While captcha_response should be
            # base64-encoded (safe), this is still a risky pattern.
            # FIX: Use json.dumps() or proper JavaScript escaping for captcha_response before inserting into script.
            driver.execute_script(
                f"""
                document.getElementById('g-recaptcha-response').innerHTML = '{captcha_response}';
                grecaptcha.getResponse = function() {{ return '{captcha_response}'; }};
            """
            )
            login_button = WebDriverWait(driver, 3).until(EC.element_to_be_clickable((By.ID, "login-button")))
            login_button.click()
            # TODO: Insufficient error handling - login failure is not detected
            # WHY: This waits for URL to contain "support.activision.com" but doesn't verify successful login.
            # If login fails (wrong password, rate limiting, captcha rejected), the page might redirect elsewhere
            # or show an error, but the code doesn't check for these conditions. It will timeout and fail generically.
            # FIX: After clicking login, check for error messages or failed login indicators before assuming success.
            WebDriverWait(driver, LOGIN_TIMEOUT).until(EC.url_contains("support.activision.com"))
            sso_cookie = self.get_sso_cookie(driver)
            if not sso_cookie:
                self.log_message.emit("Failed to retrieve SSO cookie")
                return False, None
            profile_data = self.get_profile_data(driver)
            return True, self.extract_account_info(profile_data, sso_cookie)
        except Exception as e:
            self.log_message.emit(f"An error occurred during login: {str(e)}")
            return False, None
        finally:
            if driver:
                driver.quit()
    def get_sso_cookie(self, driver):
        all_cookies = driver.get_cookies()
        return next(
           (
                cookie["value"]
                for cookie in all_cookies
                if cookie["name"] == "ACT_SSO_COOKIE"
            ),
            None,
        )
    def get_profile_data(self, driver):
        driver.get(PROFILE_URL)
        return json.loads(driver.find_element(By.TAG_NAME, "body").text)
    
    def extract_account_info(self, profile_data, sso_cookie):
        username = profile_data.get("username")
        email = profile_data.get("email")
        uno_account = next(
            (
                acc
                for acc in profile_data.get("accounts", [])
                if acc.get("provider") == "uno"
            ),
            None,
        )
        uno_id = uno_account.get("username") if uno_account else None
        return {
            "email": email,
            "username": username,
            "uno_id": uno_id,
            "sso_cookie": sso_cookie,
        }
    def update_account(self, account_info):
        existing_account = next((acc for acc in self.accounts if acc.email == account_info["email"]), None)
        if existing_account:
            existing_account.username = account_info["username"]
            existing_account.uno_id = account_info["uno_id"]
            existing_account.sso_cookie = account_info["sso_cookie"]
        else:
            # TODO: CRITICAL BUG - Account constructor parameters are in WRONG ORDER
            # WHY: Account.__init__ signature is (email, username, uno_id, sso_cookie, password, platform, last_status)
            # but this call passes: email, username, sso_cookie (as uno_id), "" (as sso_cookie), "" (as password)
            # This completely corrupts the account data - sso_cookie goes into uno_id field and sso_cookie field gets empty string.
            # Authentication will fail because sso_cookie is in the wrong field.
            # FIX: Change to Account(account_info["email"], account_info["username"], account_info["uno_id"],
            # account_info["sso_cookie"], "", "", "")
            new_account = Account(
                account_info["email"],
                account_info["username"],
                account_info["sso_cookie"],
                "",
                ""
            )
            self.accounts.append(new_account)

    def solve_login_captcha(self):
        create_task_payload = {
            "clientKey": self.config.ez_captcha_key,
            # TODO: CRITICAL BUG - Incorrect JSON key will cause API request to fail
            # WHY: The key is "appid" but should be "appId" (camelCase). Compare with line 912 in
            # solve_status_check_captcha which correctly uses "appId". This inconsistency will cause
            # the EZ-Captcha API to reject the request or ignore the app ID, leading to login failures.
            # FIX: Change "appid" to "appId" to match the correct API specification.
            "appid": EZ_CAPTCHA_APP_ID,
            "task": {
                "type": "ReCaptchaV2TaskProxyless",
                "websiteURL": self.config.login_url,
                "websiteKey": self.config.login_site_key,
                "isInvisible": False,
            },
        }
        try:
            response = requests.post(EZ_CAPTCHA_API_URL, json=create_task_payload)
            response.raise_for_status()
            create_task_result = response.json()
            if create_task_result.get("errorId") != 0:
                return None
            task_id = create_task_result["taskId"]
            get_result_payload = {
                "clientKey": self.config.ez_captcha_key,
                "taskId": task_id,
            }
            start_time = time.time()
            while time.time() - start_time < CAPTCHA_TIMEOUT:
                response = requests.post(EZ_CAPTCHA_RESULT_URL, json=get_result_payload)
                response.raise_for_status()
                result = response.json()
                if result.get("status") == "ready":
                    return result.get("solution", {}).get("gRecaptchaResponse")
                elif result.get("status") == "processing":
                    time.sleep(10)
                else:
                    return None
            self.log_message.emit("Captcha solving timed out")
        except requests.RequestException as e:
            self.log_message.emit(f"HTTP error occurred: {e}")
        except Exception as e:
            self.log_message.emit(f"Error solving captcha: {str(e)}")
        return None

config = Config()
accounts = []
login_credentials = []

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()

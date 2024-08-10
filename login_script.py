import asyncio
import json
import sys
import logging
import aiohttp
import nodriver as uc
from typing import List, Dict
import time

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Configuration
CONFIG_FILE_NAME = "config.json"
ACCOUNTS_FILE_NAME = "accounts.json"
CREDENTIALS_FILE_NAME = "login_credentials.json"
LOGIN_URL = "https://s.activision.com/activision/login"
PROFILE_URL = "https://support.activision.com/api/profile"
LOGIN_TIMEOUT = 120  # seconds


class Config:
    def __init__(self):
        self.ez_captcha_key = ""
        self.site_key = "6LfjPWwbAAAAAKhf5D1Ag5nIS-QO2M4rX52LcnDt"
        self.page_url = LOGIN_URL
        self.debug_mode = False


class Account:
    def __init__(self, email: str, password: str, username: str = None, uno_id: str = None, sso_cookie: str = None):
        self.email = email
        self.password = password
        self.username = username
        self.uno_id = uno_id
        self.sso_cookie = sso_cookie


config = Config()
accounts = []


def load_config():
    global config
    try:
        with open(CONFIG_FILE_NAME, 'r') as f:
            config_data = json.load(f)
            config.ez_captcha_key = config_data.get('ez_captcha_key', '')
            config.site_key = config_data.get('site_key', config.site_key)
            config.page_url = config_data.get('page_url', config.page_url)
            config.debug_mode = config_data.get('debug_mode', False)
    except FileNotFoundError:
        logging.error(f"Config file {CONFIG_FILE_NAME} not found. Using default values.")
    except json.JSONDecodeError:
        logging.error(f"Error parsing {CONFIG_FILE_NAME}. Using default values.")


def load_accounts():
    global accounts
    try:
        with open(CREDENTIALS_FILE_NAME, 'r') as f:
            credentials_data = json.load(f)

        accounts = [Account(cred['email'], cred['password']) for cred in credentials_data]

        # Load existing data if available
        try:
            with open(ACCOUNTS_FILE_NAME, 'r') as f:
                existing_accounts = json.load(f)
                for account in accounts:
                    existing = next((acc for acc in existing_accounts if acc.get('email') == account.email), None)
                    if existing:
                        account.username = existing.get('username')
                        account.uno_id = existing.get('uno_id')
                        account.sso_cookie = existing.get('sso_cookie')
        except FileNotFoundError:
            logging.warning(f"Accounts file {ACCOUNTS_FILE_NAME} not found. Will create new file after login.")
        except json.JSONDecodeError:
            logging.error(f"Error parsing {ACCOUNTS_FILE_NAME}. Ignoring existing data.")

    except FileNotFoundError as e:
        logging.error(f"File not found: {e.filename}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logging.error(f"Error parsing JSON: {e}")
        sys.exit(1)


async def solve_captcha() -> str:
    async with aiohttp.ClientSession() as session:
        # Create task
        create_task_url = "https://api.ez-captcha.com/createTask"
        create_task_payload = {
            "clientKey": config.ez_captcha_key,
            "task": {
                "websiteURL": config.page_url,
                "websiteKey": config.site_key,
                "type": "ReCaptchaV2TaskProxyless",
                "isInvisible": False
            }
        }
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
            'Content-Type': 'application/json'
        }

        async with session.post(create_task_url, json=create_task_payload, headers=headers) as response:
            create_task_result = await response.json()
            if create_task_result.get("errorId") != 0:
                raise Exception(f"Error creating captcha task: {create_task_result.get('errorDescription')}")
            task_id = create_task_result.get("taskId")

        # Get task result
        get_result_url = "https://api.ez-captcha.com/getTaskResult"
        get_result_payload = {
            "clientKey": config.ez_captcha_key,
            "taskId": task_id
        }

        max_attempts = 30
        for attempt in range(max_attempts):
            async with session.post(get_result_url, json=get_result_payload, headers=headers) as response:
                result = await response.json()
                if result.get("status") == "ready":
                    return result.get("solution", {}).get("gRecaptchaResponse")
                elif result.get("status") == "processing":
                    await asyncio.sleep(2)
                else:
                    raise Exception(f"Error solving captcha: {result.get('errorDescription')}")
    pass


async def login_and_get_cookie(account: Account) -> bool:
    browser = None
    try:
        browser = await uc.start()
        logging.info(f"Logging in for account: {account.email}")
        tab = await browser.new_tab()
        await tab.goto(LOGIN_URL)

        # Wait for the login form to load
        logging.info("Waiting for login form")
        await tab.wait_for_selector("#frmLogin", timeout=30000)

        # Solve captcha before filling in credentials
        logging.info("Solving captcha")
        captcha_response = await solve_captcha()
        await tab.evaluate(f"""
            document.getElementById('g-recaptcha-response').innerHTML = '{captcha_response}';
            grecaptcha.getResponse = function() {{ return '{captcha_response}'; }};
        """)

        # Fill in the username and password
        logging.info("Filling in login credentials")
        await tab.type("#username", account.email)
        await tab.type("#password", account.password)

        # Submit the form
        logging.info("Submitting login form")
        submit_button = await tab.query_selector("#login-button")
        await submit_button.click()

        # Wait for login to complete with timeout
        logging.info("Waiting for login to complete")
        start_time = time.time()
        while time.time() - start_time < LOGIN_TIMEOUT:
            try:
                await tab.wait_for_selector("#logged-in-indicator", timeout=5000)
                break
            except:
                if time.time() - start_time >= LOGIN_TIMEOUT:
                    raise Exception("Login timed out")

        # Retrieve the ACT_SSO_COOKIE
        logging.info("Retrieving cookies")
        cookies = await tab.get_cookies()
        sso_cookie = next((cookie for cookie in cookies if cookie["name"] == "ACT_SSO_COOKIE"), None)

        if sso_cookie:
            logging.info("Successfully retrieved SSO cookie")
            account.sso_cookie = sso_cookie["value"]

            # Retrieve profile information
            logging.info("Retrieving profile information")
            await tab.goto(PROFILE_URL)
            profile_data = await tab.evaluate("() => JSON.parse(document.body.innerText)")

            account.username = profile_data.get('username')
            account.email = profile_data.get('email')
            uno_account = next((acc for acc in profile_data.get('accounts', []) if acc.get('provider') == 'uno'), None)
            if uno_account:
                account.uno_id = uno_account.get('username')

            logging.info(f"Profile retrieved: Username: {account.username}, UNO ID: {account.uno_id}")
            return True
        else:
            logging.error("Failed to retrieve SSO cookie")
            return False
    except Exception as e:
        logging.error(f"An error occurred during login: {str(e)}")
        return False
    finally:
        if browser:
            await browser.stop()


async def process_accounts() -> List[Dict]:
    results = []
    for account in accounts:
        success = await login_and_get_cookie(account)
        if success:
            results.append({
                "email": account.email,
                "username": account.username,
                "uno_id": account.uno_id,
                "success": True,
                "cookie": account.sso_cookie
            })
        else:
            results.append({
                "email": account.email,
                "success": False,
                "error": "Failed to login or retrieve information"
            })
    return results


async def main():
    load_config()
    load_accounts()

    results = await process_accounts()
    print(json.dumps(results, indent=2))

    # Update accounts file with new information
    updated_accounts = [
        {
            "email": account.email,
            "username": account.username,
            "uno_id": account.uno_id,
            "sso_cookie": account.sso_cookie
        }
        for account in accounts if account.sso_cookie
    ]
    with open(ACCOUNTS_FILE_NAME, 'w') as f:
        json.dump(updated_accounts, f, indent=2)


if __name__ == "__main__":
    uc.loop().run_until_complete(main())

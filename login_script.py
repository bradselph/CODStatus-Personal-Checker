import asyncio
import json
import sys
import logging
import aiohttp
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.action_chains import ActionChains
from typing import List, Dict
import time

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Configuration
CONFIG_FILE_NAME = "config.json"
ACCOUNTS_FILE_NAME = "accounts.json"
CREDENTIALS_FILE_NAME = "login_credentials.json"
SUPPORT_URL = "https://support.activision.com"
LOGIN_URL = "https://s.activision.com/do_login?new_SiteId=activision"
PROFILE_URL = "https://support.activision.com/api/profile"
LOGIN_TIMEOUT = 120  # seconds
CAPTCHA_TIMEOUT = 120  # seconds

class Config:
    def __init__(self):
        self.ez_captcha_key = ""
        self.site_key = "6LfjPWwbAAAAAKhf5D1Ag5nIS-QO2M4rX52LcnDt"
        self.page_url = SUPPORT_URL
        self.debug_mode = True

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
            config.ez_captcha_key = config_data.get('ez_captcha_key', config.ez_captcha_key)
            config.site_key = config_data.get('site_key', config.site_key)
            config.page_url = config_data.get('page_url', config.page_url)
            config.debug_mode = config_data.get('debug_mode', config.debug_mode)
        logging.info("Config loaded successfully")
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
        logging.info(f"Loaded {len(accounts)} accounts from credentials file")

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
            logging.info("Existing account data loaded successfully")
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
    logging.info("Starting captcha solving process")
    async with aiohttp.ClientSession() as session:
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
            'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
            'Content-Type': 'application/json'
        }

        try:
            async with session.post(create_task_url, json=create_task_payload, headers=headers) as response:
                if response.status != 200:
                    logging.error(f"Error creating captcha task. Status: {response.status}")
                    return None
                create_task_result = await response.json()
                if create_task_result.get("errorId") != 0:
                    raise Exception(f"Error creating captcha task: {create_task_result.get('errorDescription')}")
                task_id = create_task_result.get("taskId")
                logging.info(f"Captcha task created with ID: {task_id}")

            get_result_url = "https://api.ez-captcha.com/getTaskResult"
            get_result_payload = {
                "clientKey": config.ez_captcha_key,
                "taskId": task_id
            }

            start_time = time.time()
            while time.time() - start_time < CAPTCHA_TIMEOUT:
                async with session.post(get_result_url, json=get_result_payload, headers=headers) as response:
                    if response.status != 200:
                        logging.error(f"Error getting captcha result. Status: {response.status}")
                        return None
                    result = await response.json()
                    if result.get("status") == "ready":
                        logging.info("Captcha solved successfully")
                        return result.get("solution", {}).get("gRecaptchaResponse")
                    elif result.get("status") == "processing":
                        logging.debug(f"Captcha still processing. Waiting 10 seconds before next attempt.")
                        await asyncio.sleep(10)
                    else:
                        logging.error(f"Unexpected captcha status: {result.get('status')}")
                        return None

            logging.error(f"Captcha solving timed out after {CAPTCHA_TIMEOUT} seconds")
            return None

        except Exception as e:
            logging.error(f"Error in solve_captcha: {str(e)}")
            return None

async def login_and_get_cookie(account: Account) -> bool:
    driver = None
    try:
        options = uc.ChromeOptions()
        # options.add_argument("--headless")  # Uncomment this line if you want to run in headless mode
        logging.info("Initializing Chrome driver")
        driver = uc.Chrome(options=options)

        logging.info(f"Logging in for account: {account.email}")

        # Step 1: Open the support page
        driver.get(SUPPORT_URL)
        logging.info("Opened support page")

        # Step 2: Click the login link
        login_link = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".log-in-link"))
        )
        login_link.click()
        logging.info("Clicked login link")

        # Wait for the login form to load
        logging.info("Waiting for login form")
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.ID, "username")))

        # Fill in the username and password
        logging.info("Filling in login credentials")
        driver.find_element(By.ID, "username").send_keys(account.email)
        driver.find_element(By.ID, "password").send_keys(account.password)

        # Solve captcha
        logging.info("Solving captcha")
        captcha_response = await solve_captcha()
        if not captcha_response:
            logging.error("Failed to solve captcha")
            return False

        # Inject the captcha response
        driver.execute_script(f"""
            document.getElementById('g-recaptcha-response').innerHTML = '{captcha_response}';
            grecaptcha.getResponse = function() {{ return '{captcha_response}'; }};
        """)
        logging.info("Captcha response injected into page")

        # Submit the form
        logging.info("Submitting login form")
        login_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "login-button"))
        )
        login_button.click()

        # Wait for login to complete with timeout
        logging.info("Waiting for login to complete")
        try:
            WebDriverWait(driver, LOGIN_TIMEOUT).until(EC.url_contains("support.activision.com"))
            logging.info("Successfully logged in")
        except TimeoutException:
            logging.error("Login timed out")
            return False

        # Retrieve only the SSO cookie
        logging.info("Retrieving SSO cookie")
        all_cookies = driver.get_cookies()
        sso_cookie = next((cookie for cookie in all_cookies if cookie["name"] == "ACT_SSO_COOKIE"), None)

        if sso_cookie:
            logging.info("Successfully retrieved SSO cookie")
            account.sso_cookie = sso_cookie["value"]

            # Retrieve profile information
            logging.info("Retrieving profile information")
            driver.get(PROFILE_URL)
            profile_data = json.loads(driver.find_element(By.TAG_NAME, "body").text)

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
    except WebDriverException as e:
        logging.error(f"WebDriver exception occurred: {str(e)}")
        return False
    except Exception as e:
        logging.error(f"An error occurred during login: {str(e)}")
        return False
    finally:
        if driver:
            logging.info("Closing Chrome driver")
            driver.quit()

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
    asyncio.run(main())

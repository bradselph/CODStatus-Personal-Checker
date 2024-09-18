# CODStatus Personal Checker

CODStatus Personal Checker is a desktop application that allows users to manage and check the status of their
Call of Duty accounts. It provides an easy-to-use interface for validating SSO cookies, checking account status,
and updating account information.

## Features

- Manage multiple Call of Duty accounts
- Validate SSO cookies
- Check account status and ban information
- Solve reCAPTCHA automatically using EZ-Captcha service
- Login and update SSO cookies automatically
- View account details including linked platforms and account age if available
- Save and load account configurations from a JSON file
- Bulk account import functionality

## Getting Started

1. Extract the zip file containing the CODStatus Personal Checker application.
2. Ensure that the following files and folders are present in the extracted directory:
   - `CODStatus_Personal_Checker_2.0.exe` (main application)
   - `chrome` folder (containing the automation Chrome browser)
   - `chromedriver` folder (containing the ChromeDriver executable)
   - `accounts.json` (created after adding an account)
   - `config.json` (created after the first run)
   - `login_credentials.json` (optional, for bulk account import)

3. Double-click on `CODStatus_Personal_Checker_2.0.exe` to launch the application.

4. On first run, you'll be prompted to enter your EZ-Captcha API key. If you don't have one, sign up at
   [EZ-Captcha](https://dashboard.ez-captcha.com/#/register?inviteCode=uyNrRgWlEKy) and obtain
   your API key from the dashboard.

## Usage Guide

### Adding Accounts

There are two ways to add accounts:

#### 1. Adding Accounts Manually

1. Click on the "Add Account" button.
2. Enter the account information:
   - Email (required if providing a password, optional with SSO cookie)
   - Password (required if providing an email, optional with SSO cookie)
   - Username (optional)
   - SSO cookie (if available, required if not providing email/password)
3. Click "OK" to add the account.

Note: SSO cookies expire after 14 days. If you only provide an SSO cookie, you'll need to manually
 update it when it becomes invalid. Providing both email and password allows the application to
  automatically update the SSO cookie when needed.

#### 2. Adding Accounts in Bulk

1. Create a JSON file named `login_credentials.json` (or any name you prefer) with the following structure:

```json
[
  {
    "email": "yourfirstaccount@example.com",
    "password": "your-password-here"
  },
  {
    "email": "secondaccount@example.com",
    "password": "another-password"
  }
]
```

2. Click on "File" in the top menu.
3. Select "Load Credentials from File" and choose your JSON file.
4. The application will import all accounts from the file.

### Checking Account Status

1. Select an account from the list.
2. Click on the "Check Selected Account" button.
3. The application will solve the CAPTCHA and retrieve the account status.

### Validating SSO Cookies

1. Click on the "Validate SSO Cookies" button.
2. The application will check the validity of SSO cookies for all accounts.

### Logging In and Updating SSO Cookies

1. Click on the "Login and Update SSO Cookies" button.
2. The application will attempt to log in to each account with provided email/password
   and update the SSO cookies.

### Viewing Account Details

1. Select an account from the list.
2. The account details will be displayed in the right panel, including:
   - Email
   - Username
   - UNO ID
   - SSO Cookie (partially hidden)
   - Last Status
   - Last Check Time
   - Account Age
   - Linked Accounts (PSN, Xbox Live, Steam, Battle.net)
   - Ban Information (if any)

### Additional Features

- **Check All Accounts**: Checks the status of all accounts in the list.
- **Check Captcha Balance**: Displays your current EZ-Captcha balance.
- **Refresh Accounts**: Reloads the account list from the saved file.
- **Extra Options Mode**: Enables additional Chrome options (currently in development).

## Configuration

The application uses a `config.json` file for storing settings. While it's possible to modify this file
   manually, it's not recommended unless you're an advanced user. The main configurable options are:

- `ez_captcha_key`: Your EZ-Captcha API key
- `login_site_key`: reCAPTCHA site key for the login page
- `status_site_key`: reCAPTCHA site key for the status check page
- `login_url`: URL for the login page
- `page_url`: URL for the support page
- `extra_options_mode`: Enable/disable extra Chrome options

## Troubleshooting

1. **Invalid SSO Cookie**: 
   - For manually added SSO cookies: Log out of your Call of Duty account and log back in to obtain a
     fresh SSO cookie.
   - Update the account in the application with the new SSO cookie.
   - If using email/password, try the "Login and Update SSO Cookies" feature.

2. **Login Failures**:
   - Double-check your account credentials.
   - Verify your EZ-Captcha API key and balance.
   - Ensure email and password in the JSON file are correctly formatted.
   - Wait a few minutes and try again.
   - Attempt to log in through a web browser to check for any account-specific issues.

3. **Application Not Starting**:
   - Verify all required files and folders are in the same directory as the executable.
   - Check if your antivirus is blocking the application (false positives can occur).
   - Try running the application as administrator.

4. **Slow Performance**:
   - The CAPTCHA solving process can be time-consuming. The application currently checks one account at a time.
   - Check for and close any "zombie" Chrome processes left running in the background.
   - Restart the application after ensuring no background processes are running.
   - The "Extra Options Mode" is still in development and may not have an effect currently.

5. **CAPTCHA Solving Issues**:
   - Verify your EZ-Captcha API key and balance.
   - The solving service may be temporarily down. Wait a few minutes and try again.

## Privacy and Security

- Account information is stored locally on your computer in unencrypted JSON files. 
   Exercise caution with these files.
- SSO cookies and passwords are sensitive information. Ensure your computer is secure.
- The application uses a dedicated Chrome browser for automation purposes:
  - Chrome version: 128 (does not auto-update)
  - ChromeDriver: Must match the Chrome version (128)
- No personal information is collected or transmitted beyond what's necessary for account checks and
   CAPTCHA solving.

## Technical Details

- The application is built using Python and PyQt5 for the GUI.
- It uses Selenium WebDriver with undetected-chromedriver for web automation.
- CAPTCHA solving is handled through the EZ-Captcha API.
- Account data is stored in JSON format for easy management and portability.

## Future Developments

- Improved multi-threading for faster account checking
- Enhanced security features for storing sensitive information
- Expanded account management capabilities
- Regular updates to maintain compatibility with Call of Duty services

## Disclaimer

This application is not affiliated with, maintained, authorized, endorsed, or sponsored by Activision or
any of its affiliates. Use at your own risk and responsibility.

## License

This project is licensed under the AGPL-3.0 License - see the [LICENSE](LICENSE) file for details.

## Support and Contributions

For support, please open an issue on the project's GitHub repository. Contributions to improve the
application are welcome. Please fork the repository and submit a pull request with your changes.
[![Go](https://github.com/bradselph/CODStatus-Personal-Checker/actions/workflows/GoBuild.yml/badge.svg)](https://github.com/bradselph/CODStatus-Personal-Checker/actions/workflows/GoBuild.yml)
# CODStatus Personal Checker

CODStatus Personal Checker is a desktop application that allows users to check the status of their Call of Duty account. It provides an easy-to-use interface for validating SSO cookies and checking account status.

```
 ▄████▄   ▒█████  ▓█████▄   ██████ ▄▄▄█████▓ ▄▄▄      ▄▄▄█████▓ █    ██   ██████ 
▒██▀ ▀█  ▒██▒  ██▒▒██▀ ██▌▒██    ▒ ▓  ██▒ ▓▒▒████▄    ▓  ██▒ ▓▒ ██  ▓██▒▒██    ▒ 
▒▓█    ▄ ▒██░  ██▒░██   █▌░ ▓██▄   ▒ ▓██░ ▒░▒██  ▀█▄  ▒ ▓██░ ▒░▓██  ▒██░░ ▓██▄   
▒▓▓▄ ▄██▒▒██   ██░░▓█▄   ▌  ▒   ██▒░ ▓██▓ ░ ░██▄▄▄▄██ ░ ▓██▓ ░ ▓▓█  ░██░  ▒   ██▒
▒ ▓███▀ ░░ ████▓▒░░▒████▓ ▒██████▒▒  ▒██▒ ░  ▓█   ▓██▒  ▒██▒ ░ ▒▒█████▓ ▒██████▒▒
░ ░▒ ▒  ░░ ▒░▒░▒░  ▒▒▓  ▒ ▒ ▒▓▒ ▒ ░  ▒ ░░    ▒▒   ▓▒█░  ▒ ░░   ░▒▓▒ ▒ ▒ ▒ ▒▓▒ ▒ ░
  ░  ▒     ░ ▒ ▒░  ░ ▒  ▒ ░ ░▒  ░ ░    ░      ▒   ▒▒ ░    ░    ░░▒░ ░ ░ ░ ░▒  ░ ░
░        ░ ░ ░ ▒   ░ ░  ░ ░  ░  ░    ░        ░   ▒     ░       ░░░ ░ ░ ░  ░  ░  
░ ░          ░ ░     ░          ░                 ░  ░            ░           ░  
░                    ░

```

## Features

- Validate SSO cookies
- Check account status
- Solve reCAPTCHA automatically using EZ-Captcha service
- Save and load configuration
- User-friendly command-line interface

## Prerequisites

- Go 1.16 or higher
- An active Call of Duty account
- An EZ-Captcha API key

## Installation

If you prefer not to build the application from source, you can download a prebuilt executable for Windows from the [Releases](https://github.com/bradselph/codstatus-personal-checker/releases) tab.

To build from source:

1. Clone this repository:
   ```
   git clone https://github.com/bradselph/codstatus-personal-checker.git
   ```

2. Navigate to the project directory:
   ```
   cd codstatus-personal-checker
   ```

3. Build the application:
   ```
   go build main.go
   ```

## Usage

1. Run the application:
   ```
   codstatus-personal-checker.exe
   ```

2. On first run, you'll be prompted to enter your SSO Cookie and EZ-Captcha API key.

3. Use the following commands:
   - `check`: Check your account status
   - `validate`: Validate your SSO cookie
   - `exit`: Quit the application

## Configuration

The application stores your configuration in a file named `config.json`. You can update your configuration by selecting the 'update' option when prompted at startup.

## Obtaining Required Information

### SSO Cookie

1. Log in to your Call of Duty account at [https://www.activision.com/](https://www.activision.com/)
2. Open your browser's developer tools (usually F12)
3. Go to the "Application" or "Storage" tab
4. Under "Cookies", find the `ACT_SSO_COOKIE` value

### EZ-Captcha API Key

1. Sign up for an account at [EZ-Captcha](https://dashboard.ez-captcha.com/#/register?inviteCode=uyNrRgWlEKy)
2. Obtain your API key from your account dashboard

## Troubleshooting

- If you encounter any issues with your SSO cookie, try logging out and back into your Call of Duty account to obtain a fresh cookie.
- Ensure your EZ-Captcha API key is valid and has sufficient balance.

## Disclaimer

This application is not affiliated with, maintained, authorized, endorsed, or sponsored by Activision or any of its affiliates. Use at your own risk.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the AGPL-3.0 License - see the [LICENSE](LICENSE) file for details.

package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"fmt"
	"golang.org/x/net/publicsuffix"
	"io"
	"net/http"
	"net/http/cookiejar"
	"net/url"
	"os"
	"os/exec"
	"strconv"
	"strings"
	"sync"
	"time"
)

const (
	EZCaptchaAPIURL     = "https://api.ez-captcha.com/createTask"
	EZCaptchaResultURL  = "https://api.ez-captcha.com/getTaskResult"
	EZCaptchaBalanceURL = "https://api.ez-captcha.com/getBalance"
	AccountCheckURL     = "https://support.activision.com/api/bans/v2/appeal?locale=en"
	ProfileURL          = "https://support.activision.com/api/profile?accts=false"
	LoginURL            = "https://s.activision.com/activision/login"
	MaxRetries          = 12
	RetryInterval       = 10 * time.Second
	ConfigFileName      = "config.json"
	AccountsFileName    = "accounts.json"
	MaxConcurrentChecks = 25
	EZCaptchaAppId      = 84291
	LoginSiteKey        = "6LfjPWwbAAAAAKhf5D1Ag5nIS-QO2M4rX52LcnDt"
)

type Config struct {
	EZCaptchaKey string `json:"ez_captcha_key"`
	SiteKey      string `json:"site_key"`
	PageURL      string `json:"page_url"`
	DebugMode    bool   `json:"debug_mode"`
}

type Account struct {
	Title     string `json:"title"`
	SSOCookie string `json:"sso_cookie"`
	XSRFToken string `json:"xsrf_token"`
}

type LoginCredentials struct {
	Email    string `json:"email"`
	Password string `json:"password"`
}

var (
	config           Config
	accounts         []Account
	loginCredentials []LoginCredentials
	sem              = make(chan struct{}, MaxConcurrentChecks)
)

func main() {
	printIntro()

	loadOrCreateConfig()
	loadOrCreateAccounts()
	loadOrCreateLoginCredentials()

	for {
		fmt.Println("\nEnter 'check' to check account status, 'validate' to validate SSO cookies, 'balance' to check captcha solver balance, 'login' to login and save SSO cookies, or 'exit' to quit:")
		command := readInput()

		switch command {
		case "check":
			checkAccounts()
		case "validate":
			validateAccounts()
		case "balance":
			checkCaptchaBalance()
		case "login":
			loginAndSaveSSO()
		case "exit":
			fmt.Println("Exiting application.")
			return
		default:
			fmt.Println("Invalid command. Please try again.")
		}
	}
}

func printIntro() {
	intro := `
 ▄████▄   ▒█████  ▓█████▄   ██████ ▄▄▄█████▓ ▄▄▄      ▄▄▄█████▓ █    ██   ██████ 
▒██▀ ▀█  ▒██▒  ██▒▒██▀ ██▌▒██    ▒ ▓  ██▒ ▓▒▒████▄    ▓  ██▒ ▓▒ ██  ▓██▒▒██    ▒ 
▒▓█    ▄ ▒██░  ██▒░██   █▌░ ▓██▄   ▒ ▓██░ ▒░▒██  ▀█▄  ▒ ▓██░ ▒░▓██  ▒██░░ ▓██▄   
▒▓▓▄ ▄██▒▒██   ██░░▓█▄   ▌  ▒   ██▒░ ▓██▓ ░ ░██▄▄▄▄██ ░ ▓██▓ ░ ▓▓█  ░██░  ▒   ██▒
▒ ▓███▀ ░░ ████▓▒░░▒████▓ ▒██████▒▒  ▒██▒ ░  ▓█   ▓██▒  ▒██▒ ░ ▒▒█████▓ ▒██████▒▒
░ ░▒ ▒  ░░ ▒░▒░▒░  ▒▒▓  ▒ ▒ ▒▓▒ ▒ ░  ▒ ░░    ▒▒   ▓▒█░  ▒ ░░   ░▒▓▒ ▒ ▒ ▒ ▒▓▒ ▒ ░
  ░  ▒     ░ ▒ ▒░  ░ ▒  ▒ ░ ░▒  ░ ░    ░      ▒   ▒▒ ░    ░    ░░▒░ ░ ░ ░ ░▒  ░ ░
░        ░ ░ ░ ▒   ░ ░  ░ ░  ░  ░    ░        ░   ▒     ░       ░░░ ░ ░ ░  ░  ░  
░ ░          ░ ░     ░          ░                 ░  ░            ░           ░  
░                  ░
`
	fmt.Println(intro)
}

func loadOrCreateConfig() {
	if _, err := os.Stat(ConfigFileName); os.IsNotExist(err) {
		config = Config{
			SiteKey: "6LdB2NUpAAAAANcdcy9YcjBOBD4rY-TIHOeolkkk",
			PageURL: "https://support.activision.com",
		}
		saveConfig()
	} else {
		loadConfig()
	}

	fmt.Println("Configuration loaded. Enter 'update' to update configuration, or press Enter to continue with current config.")
	if readInput() == "update" {
		updateConfig()
		saveConfig()
	}
}

func loadOrCreateAccounts() {
	if _, err := os.Stat(AccountsFileName); os.IsNotExist(err) {
		accounts = []Account{}
		saveAccounts()
	} else {
		loadAccounts()
	}

	fmt.Println("Accounts loaded. Enter 'update' to update accounts, or press Enter to continue with current accounts.")
	if readInput() == "update" {
		updateAccounts()
		saveAccounts()
	}
}

func loadOrCreateLoginCredentials() {
	if _, err := os.Stat("login_credentials.json"); os.IsNotExist(err) {
		loginCredentials = []LoginCredentials{}
		saveLoginCredentials()
	} else {
		loadLoginCredentials()
	}

	fmt.Println("Login credentials loaded. Enter 'update' to update credentials, or press Enter to continue with current credentials.")
	if readInput() == "update" {
		updateLoginCredentials()
		saveLoginCredentials()
	}
}

func loadConfig() {
	data, err := os.ReadFile(ConfigFileName)
	if err != nil {
		fmt.Printf("Error reading config file: %v\n", err)
		return
	}

	err = json.Unmarshal(data, &config)
	if err != nil {
		fmt.Printf("Error parsing config file: %v\n", err)
	}
}

func saveConfig() {
	data, err := json.MarshalIndent(config, "", "  ")
	if err != nil {
		fmt.Printf("Error encoding config: %v\n", err)
		return
	}

	err = os.WriteFile(ConfigFileName, data, 0644)
	if err != nil {
		fmt.Printf("Error saving config file: %v\n", err)
	} else {
		fmt.Println("Configuration saved successfully.")
	}
}

func updateConfig() {
	fmt.Print("Enter your EZ-Captcha API Key (leave empty to keep current): ")
	input := readInput()
	if input != "" {
		config.EZCaptchaKey = input
	}

	fmt.Print("Enter debug mode (true/false, leave empty to keep current): ")
	input = readInput()
	if input == "true" || input == "false" {
		config.DebugMode = (input == "true")
	}
}

func loadAccounts() {
	data, err := os.ReadFile(AccountsFileName)
	if err != nil {
		fmt.Printf("Error reading accounts file: %v\n", err)
		return
	}

	err = json.Unmarshal(data, &accounts)
	if err != nil {
		fmt.Printf("Error parsing accounts file: %v\n", err)
	}
}

func saveAccounts() {
	data, err := json.MarshalIndent(accounts, "", "  ")
	if err != nil {
		fmt.Printf("Error encoding accounts: %v\n", err)
		return
	}

	err = os.WriteFile(AccountsFileName, data, 0644)
	if err != nil {
		fmt.Printf("Error saving accounts file: %v\n", err)
	} else {
		fmt.Println("Accounts saved successfully.")
	}
}

func updateAccounts() {
	accounts = []Account{}
	fmt.Println("Enter accounts in the format 'title:ssocookie:xsrftoken', one per line. Enter an empty line when done:")
	for {
		input := readInput()
		if input == "" {
			break
		}
		parts := strings.SplitN(input, ":", 3)
		if len(parts) == 3 {
			accounts = append(accounts, Account{Title: parts[0], SSOCookie: parts[1], XSRFToken: parts[2]})
		} else {
			fmt.Println("Invalid format. Please use 'title:ssocookie:xsrftoken'")
		}
	}
}

func loadLoginCredentials() {
	data, err := os.ReadFile("login_credentials.json")
	if err != nil {
		fmt.Printf("Error reading login credentials file: %v\n", err)
		return
	}

	err = json.Unmarshal(data, &loginCredentials)
	if err != nil {
		fmt.Printf("Error parsing login credentials file: %v\n", err)
	}
}

func saveLoginCredentials() {
	data, err := json.MarshalIndent(loginCredentials, "", "  ")
	if err != nil {
		fmt.Printf("Error encoding login credentials: %v\n", err)
		return
	}

	err = os.WriteFile("login_credentials.json", data, 0644)
	if err != nil {
		fmt.Printf("Error saving login credentials file: %v\n", err)
	} else {
		fmt.Println("Login credentials saved successfully.")
	}
}

func updateLoginCredentials() {
	loginCredentials = []LoginCredentials{}
	fmt.Println("Enter login credentials in the format 'email:password', one per line. Enter an empty line when done:")
	for {
		input := readInput()
		if input == "" {
			break
		}
		parts := strings.SplitN(input, ":", 2)
		if len(parts) == 2 {
			loginCredentials = append(loginCredentials, LoginCredentials{Email: parts[0], Password: parts[1]})
		} else {
			fmt.Println("Invalid format. Please use 'email:password'")
		}
	}
}

func readInput() string {
	reader := bufio.NewReader(os.Stdin)
	input, _ := reader.ReadString('\n')
	return strings.TrimSpace(input)
}

func loginAndSaveSSO() {
	fmt.Println("Running Python login script...")
	cmd := exec.Command("python", "login_script.py")
	var out bytes.Buffer
	cmd.Stdout = &out
	err := cmd.Run()
	if err != nil {
		fmt.Printf("Error running Python script: %v\n", err)
		return
	}

	var results []map[string]interface{}
	err = json.Unmarshal(out.Bytes(), &results)
	if err != nil {
		fmt.Printf("Error parsing Python script output: %v\n", err)
		return
	}

	for _, result := range results {
		email, _ := result["email"].(string)
		success, _ := result["success"].(bool)
		if success {
			cookie, _ := result["cookie"].(string)
			username, _ := result["username"].(string)
			unoID, _ := result["uno_id"].(string)

			// Check if account already exists
			existingIndex := -1
			for i, acc := range accounts {
				if acc.Title == email {
					existingIndex = i
					break
				}
			}

			if existingIndex != -1 {
				// Update existing account
				accounts[existingIndex].SSOCookie = cookie
				fmt.Printf("Updated SSO cookie for existing account: %s\n", email)
			} else {
				// Add new account
				accounts = append(accounts, Account{
					Title:     email,
					SSOCookie: cookie,
				})
				fmt.Printf("Added new account: %s\n", email)
			}

			fmt.Printf("Successfully logged in and saved SSO cookie for %s (Username: %s, UNO ID: %s)\n", email, username, unoID)
		} else {
			errorMsg, _ := result["error"].(string)
			fmt.Printf("Failed to log in for %s: %s\n", email, errorMsg)
		}
	}

	saveAccounts()
}

func validateAccounts() {
	for i, account := range accounts {
		isValid := validateSSOCookie(account.SSOCookie)
		status := "Valid"
		if !isValid {
			status = "Invalid"
			// Remove invalid SSO cookie
			accounts[i].SSOCookie = ""
		}
		fmt.Printf("%s: SSO Cookie is %s\n", account.Title, status)
	}

	// Save accounts after validation
	saveAccounts()
}

func validateSSOCookie(ssoCookie string) bool {
	client := &http.Client{}
	req, err := http.NewRequest("GET", ProfileURL, nil)
	if err != nil {
		fmt.Printf("Error creating request: %v\n", err)
		return false
	}

	req.Header.Set("Cookie", fmt.Sprintf("ACT_SSO_COOKIE=%s", ssoCookie))
	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, "+
		"like Gecko) Chrome/58.0.3029.110 Safari/537.3")

	resp, err := client.Do(req)
	if err != nil {
		fmt.Printf("Error sending request: %v\n", err)
		return false
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		fmt.Printf("Invalid SSO cookie. Status code: %d\n", resp.StatusCode)
		return false
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		fmt.Printf("Error reading response body: %v\n", err)
		return false
	}

	if len(body) == 0 {
		fmt.Println("Invalid SSO cookie. Empty response body.")
		return false
	}

	return true
}

func checkAccounts() {
	if len(accounts) == 0 {
		fmt.Println("No accounts configured. Please update your accounts.")
		return
	}

	fmt.Println("Select accounts to check (comma-separated numbers) or 'all':")
	for i, account := range accounts {
		fmt.Printf("%d. %s\n", i+1, account.Title)
	}

	selection := readInput()
	var accountsToCheck []Account

	if selection == "all" {
		accountsToCheck = accounts
	} else {
		indices := strings.Split(selection, ",")
		for _, index := range indices {
			i, err := strconv.Atoi(strings.TrimSpace(index))
			if err == nil && i > 0 && i <= len(accounts) {
				accountsToCheck = append(accountsToCheck, accounts[i-1])
			}
		}
	}

	results := make([]string, len(accountsToCheck))
	var wg sync.WaitGroup

	fmt.Println("Checking accounts...")
	for i, account := range accountsToCheck {
		wg.Add(1)
		go func(i int, account Account) {
			defer wg.Done()
			sem <- struct{}{}
			defer func() { <-sem }()

			result := checkAccount(account)
			results[i] = result
			fmt.Printf("Progress: %d/%d\n", i+1, len(accountsToCheck))
		}(i, account)
	}

	wg.Wait()

	for _, result := range results {
		fmt.Println(result)
	}

	exportResults(results)
}

func checkAccount(account Account) string {
	if !validateSSOCookie(account.SSOCookie) {
		return fmt.Sprintf("%s: Invalid SSO cookie", account.Title)
	}

	captchaResponse, err := solveCaptcha()
	if err != nil {
		return fmt.Sprintf("%s: Error solving captcha: %v", account.Title, err)
	}

	status, err := sendAccountCheckRequest(account.SSOCookie, captchaResponse)
	if err != nil {
		return fmt.Sprintf("%s: Error checking account status: %v", account.Title, err)
	}

	return fmt.Sprintf("%s: %s", account.Title, status)
}

func checkCaptchaBalance() {
	balance, err := getEZCaptchaBalance()
	if err != nil {
		fmt.Printf("Error checking EZ-Captcha balance: %v\n", err)
	} else {
		fmt.Printf("EZ-Captcha balance: %s\n", balance)
	}
}

func solveCaptcha() (string, error) {
	return solveEZCaptcha()
}

func solveEZCaptcha() (string, error) {
	debugLog("Starting EZ-Captcha solving process")

	payload := map[string]interface{}{
		"clientKey": config.EZCaptchaKey,
		"appId":     EZCaptchaAppId,
		"task": map[string]interface{}{
			"type":        "ReCaptchaV2TaskProxyless",
			"websiteURL":  config.PageURL,
			"websiteKey":  config.SiteKey,
			"isInvisible": false,
		},
	}

	jsonPayload, _ := json.Marshal(payload)
	resp, err := http.Post(EZCaptchaAPIURL, "application/json", strings.NewReader(string(jsonPayload)))
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	var result struct {
		ErrorId          int    `json:"errorId"`
		ErrorCode        string `json:"errorCode"`
		ErrorDescription string `json:"errorDescription"`
		TaskId           string `json:"taskId"`
	}
	json.NewDecoder(resp.Body).Decode(&result)

	if result.ErrorId != 0 {
		return "", fmt.Errorf("EZ-Captcha error: %s - %s", result.ErrorCode, result.ErrorDescription)
	}

	debugLog(fmt.Sprintf("EZ-Captcha task created: %s", result.TaskId))

	for i := 0; i < MaxRetries; i++ {
		time.Sleep(RetryInterval)

		solution, err := getEZCaptchaResult(result.TaskId)
		if err == nil {
			debugLog("EZ-Captcha solved successfully")
			return solution, nil
		}

		debugLog(fmt.Sprintf("EZ-Captcha solving attempt %d failed: %v", i+1, err))
	}

	return "", fmt.Errorf("failed to solve EZ-Captcha after %d attempts", MaxRetries)
}

func getEZCaptchaResult(taskId string) (string, error) {
	payload := map[string]string{
		"clientKey": config.EZCaptchaKey,
		"taskId":    taskId,
	}

	jsonPayload, _ := json.Marshal(payload)
	resp, err := http.Post(EZCaptchaResultURL, "application/json", strings.NewReader(string(jsonPayload)))
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	var result struct {
		Status   string `json:"status"`
		Solution struct {
			GRecaptchaResponse string `json:"gRecaptchaResponse"`
		} `json:"solution"`
	}
	json.NewDecoder(resp.Body).Decode(&result)

	if result.Status == "ready" {
		return result.Solution.GRecaptchaResponse, nil
	}

	return "", fmt.Errorf("captcha not ready")
}

func sendAccountCheckRequest(ssoCookie, captchaResponse string) (string, error) {
	client := &http.Client{}

	reqURL := fmt.Sprintf("%s&g-cc=%s", AccountCheckURL, url.QueryEscape(captchaResponse))
	req, err := http.NewRequest("GET", reqURL, nil)
	if err != nil {
		return "", err
	}

	req.Header.Set("Cookie", fmt.Sprintf("ACT_SSO_COOKIE=%s", ssoCookie))
	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3")

	resp, err := client.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", err
	}

	var result struct {
		Error     string `json:"error"`
		Success   string `json:"success"`
		CanAppeal bool   `json:"canAppeal"`
		Bans      []struct {
			Enforcement string `json:"enforcement"`
			Title       string `json:"title"`
			CanAppeal   bool   `json:"canAppeal"`
		} `json:"bans"`
	}

	err = json.Unmarshal(body, &result)
	if err != nil {
		return "", fmt.Errorf("failed to parse response: %v", err)
	}

	if result.Error != "" {
		return "", fmt.Errorf("API error: %s", result.Error)
	}

	if len(result.Bans) == 0 {
		return "Account not banned", nil
	}

	var status string
	for _, ban := range result.Bans {
		switch ban.Enforcement {
		case "PERMANENT":
			status = "Permanently banned"
		case "UNDER_REVIEW":
			status = "Shadowbanned"
		default:
			status = "Unknown ban status"
		}
		break
	}

	return status, nil
}

func exportResults(results []string) {
	filename := fmt.Sprintf("account_status_%s.txt", time.Now().Format("2006-01-02_15-04-05"))
	file, err := os.Create(filename)
	if err != nil {
		fmt.Printf("Error creating file: %v\n", err)
		return
	}
	defer file.Close()

	for _, result := range results {
		_, err := file.WriteString(result + "\n")
		if err != nil {
			fmt.Printf("Error writing to file: %v\n", err)
			return
		}
	}

	fmt.Printf("Results exported to %s\n", filename)
}

func getEZCaptchaBalance() (string, error) {
	payload := map[string]string{
		"clientKey": config.EZCaptchaKey,
	}

	jsonPayload, err := json.Marshal(payload)
	if err != nil {
		return "", fmt.Errorf("error creating JSON payload: %v", err)
	}

	resp, err := http.Post(EZCaptchaBalanceURL, "application/json", bytes.NewBuffer(jsonPayload))
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	var result struct {
		ErrorId          int     `json:"errorId"`
		Balance          float64 `json:"balance"`
		ErrorCode        string  `json:"errorCode"`
		ErrorDescription string  `json:"errorDescription"`
	}
	err = json.NewDecoder(resp.Body).Decode(&result)
	if err != nil {
		return "", fmt.Errorf("error decoding response: %v", err)
	}

	if result.ErrorId != 0 {
		return "", fmt.Errorf("EZ-Captcha error: %s - %s", result.ErrorCode, result.ErrorDescription)
	}

	return fmt.Sprintf("%.2f", result.Balance), nil
}

func debugLog(message string) {
	if config.DebugMode {
		fmt.Printf("[DEBUG] %s\n", message)
	}
}

/*
	func loginAndSaveSSO() {
		if len(loginCredentials) == 0 {
			fmt.Println("No login credentials configured. Please update your credentials.")
			return
		}

		for _, cred := range loginCredentials {
			fmt.Printf("Attempting to log in with email: %s\n", cred.Email)
			ssoCookie, err := login(cred.Email, cred.Password)
			if err != nil {
				fmt.Printf("Error logging in with email %s: %v\n", cred.Email, err)
				continue
			}

			accounts = append(accounts, Account{
				Title:     cred.Email,
				SSOCookie: ssoCookie,
			})

			fmt.Printf("Successfully logged in and saved SSO cookie and XSRF token for %s\n", cred.Email)
		}

		saveAccounts()
	}
*/
func login(email, password string) (string, error) {
	jar, err := cookiejar.New(&cookiejar.Options{PublicSuffixList: publicsuffix.List})
	if err != nil {
		return "", fmt.Errorf("error creating cookie jar: %v", err)
	}
	client := &http.Client{
		Jar: jar,
		CheckRedirect: func(req *http.Request, via []*http.Request) error {
			return http.ErrUseLastResponse
		},
	}

	// Define loginURL at the beginning of the function
	loginURL := "https://s.activision.com/activision/login?redirectUrl=https://www.activision.com/"

	// Step 1: Initial GET request to the login page
	resp, err := client.Get(loginURL)
	if err != nil {
		return "", fmt.Errorf("error getting login page: %v", err)
	}
	defer resp.Body.Close()

	// Extract cookies from the response
	var bmSz, abck string
	for _, cookie := range resp.Cookies() {
		switch cookie.Name {
		case "bm_sz":
			bmSz = cookie.Value
		case "_abck":
			abck = cookie.Value
		}
	}

	// Step 2: GET request for site configuration
	_, err = client.Get("https://s.activision.com/activision/script/siteConfig/loc_en")
	if err != nil {
		return "", fmt.Errorf("error getting site configuration: %v", err)
	}

	// Step 3: Check email format
	checkEmailURL := "https://s.activision.com/activision/checkEmailFormat"
	emailData := url.Values{}
	emailData.Set("email", email)

	req, err := http.NewRequest("POST", checkEmailURL, strings.NewReader(emailData.Encode()))
	if err != nil {
		return "", fmt.Errorf("error creating email check request: %v", err)
	}
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")

	resp, err = client.Do(req)
	if err != nil {
		return "", fmt.Errorf("error checking email format: %v", err)
	}
	defer resp.Body.Close()

	// Step 4: Solve captcha
	captchaResponse, err := solveCaptchaForLogin()
	if err != nil {
		return "", fmt.Errorf("error solving captcha for login: %v", err)
	}

	// New Step: OPTIONS call
	optionsURL := "https://s.activision.com/do_login?new_SiteId=activision"
	optionsReq, err := http.NewRequest("OPTIONS", optionsURL, nil)
	if err != nil {
		return "", fmt.Errorf("error creating OPTIONS request: %v", err)
	}
	optionsReq.Header.Set("Access-Control-Request-Method", "POST")
	optionsReq.Header.Set("Access-Control-Request-Headers", "content-type,x-xsrf-token")
	optionsReq.Header.Set("Origin", "https://s.activision.com")
	optionsReq.Header.Set("Referer", loginURL)

	optionsResp, err := client.Do(optionsReq)
	if err != nil {
		return "", fmt.Errorf("error sending OPTIONS request: %v", err)
	}
	optionsResp.Body.Close()

	// Check if OPTIONS request was successful
	if optionsResp.StatusCode != http.StatusOK {
		return "", fmt.Errorf("OPTIONS request failed with status: %d", optionsResp.StatusCode)
	}

	// Step 5: Submit login credentials
	loginPostURL := "https://s.activision.com/do_login?new_SiteId=activision"
	loginData := url.Values{}
	loginData.Set("username", email)
	loginData.Set("password", password)
	loginData.Set("remember_me", "true")
	loginData.Set("g-recaptcha-response", captchaResponse)

	req, err = http.NewRequest("POST", loginPostURL, strings.NewReader(loginData.Encode()))
	if err != nil {
		return "", fmt.Errorf("error creating login request: %v", err)
	}

	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36")
	req.Header.Set("Referer", loginURL)
	req.Header.Set("Origin", "https://s.activision.com")
	req.Header.Set("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7")
	req.Header.Set("Accept-Language", "en-US,en;q=0.9")
	req.Header.Set("Cookie", fmt.Sprintf("bm_sz=%s; _abck=%s", bmSz, abck))

	resp, err = client.Do(req)
	if err != nil {
		return "", fmt.Errorf("error sending login request: %v", err)
	}
	defer resp.Body.Close()

	// Step 6: Handle redirects and check for success
	for resp.StatusCode == http.StatusFound {
		location := resp.Header.Get("Location")
		req, err = http.NewRequest("GET", location, nil)
		if err != nil {
			return "", fmt.Errorf("error creating redirect request: %v", err)
		}
		resp, err = client.Do(req)
		if err != nil {
			return "", fmt.Errorf("error following redirect: %v", err)
		}
	}

	// Extract SSO cookie
	var ssoCookie string
	for _, cookie := range resp.Cookies() {
		switch cookie.Name {
		case "ACT_SSO_COOKIE":
			ssoCookie = cookie.Value
		case "ACT_SSO_EVENT":
			if cookie.Value == "LOGIN_SUCCESS" {
				return ssoCookie, nil
			}
		}
	}

	if ssoCookie == "" {
		return "", fmt.Errorf("SSO cookie not found in response")
	}

	return "", fmt.Errorf("login process completed but success cookie not found")
}

func solveCaptchaForLogin() (string, error) {
	debugLog("Starting captcha solving process for login")

	payload := map[string]interface{}{
		"clientKey": config.EZCaptchaKey,
		"appId":     EZCaptchaAppId,
		"task": map[string]interface{}{
			"type":        "ReCaptchaV2TaskProxyless",
			"websiteURL":  LoginURL,
			"websiteKey":  LoginSiteKey,
			"isInvisible": false,
		},
	}

	jsonPayload, _ := json.Marshal(payload)
	resp, err := http.Post(EZCaptchaAPIURL, "application/json", strings.NewReader(string(jsonPayload)))
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	var result struct {
		ErrorId          int    `json:"errorId"`
		ErrorCode        string `json:"errorCode"`
		ErrorDescription string `json:"errorDescription"`
		TaskId           string `json:"taskId"`
	}
	json.NewDecoder(resp.Body).Decode(&result)

	if result.ErrorId != 0 {
		return "", fmt.Errorf("EZ-Captcha error: %s - %s", result.ErrorCode, result.ErrorDescription)
	}

	debugLog(fmt.Sprintf("EZ-Captcha task created for login: %s", result.TaskId))

	for i := 0; i < MaxRetries; i++ {
		time.Sleep(RetryInterval)

		solution, err := getEZCaptchaResult(result.TaskId)
		if err == nil {
			debugLog("Captcha solved successfully for login")
			return solution, nil
		}

		debugLog(fmt.Sprintf("Captcha solving attempt %d failed for login: %v", i+1, err))
	}

	return "", fmt.Errorf("failed to solve captcha for login after %d attempts", MaxRetries)
}

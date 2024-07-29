package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"
)

const (
	EZCaptchaAPIURL     = "https://api.ez-captcha.com/createTask"
	EZCaptchaResultURL  = "https://api.ez-captcha.com/getTaskResult"
	EZCaptchaBalanceURL = "https://api.ez-captcha.com/getBalance"
	/*	TwoCaptchaAPIURL     = "https://api.2captcha.com/createTask"
		/	TwoCaptchaResultURL  = "https://api.2captcha.com/getTaskResult"
			TwoCaptchaBalanceURL = "https://api.2captcha.com/getBalance"
	*/AccountCheckURL   = "https://support.activision.com/api/bans/v2/appeal?locale=en"
	ProfileURL          = "https://support.activision.com/api/profile?accts=false"
	MaxRetries          = 22
	RetryInterval       = 5 * time.Second
	ConfigFileName      = "config.json"
	AccountsFileName    = "accounts.json"
	MaxConcurrentChecks = 5
	EZCaptchaAppId      = 84291
)

type Config struct {
	EZCaptchaKey string `json:"ez_captcha_key"`
	/*	TwoCaptchaKey           string `json:"two_captcha_key"`
		PreferredCaptchaService string `json:"preferred_captcha_service"`
	*/SiteKey string `json:"site_key"`
	PageURL   string `json:"page_url"`
	DebugMode bool   `json:"debug_mode"`
}

type Account struct {
	Title     string `json:"title"`
	SSOCookie string `json:"sso_cookie"`
}

var (
	config   Config
	accounts []Account
	sem      = make(chan struct{}, MaxConcurrentChecks)
)

func main() {
	printIntro()

	loadOrCreateConfig()
	loadOrCreateAccounts()

	for {
		fmt.Println("\nEnter 'check' to check account status, 'validate' to validate SSO cookies, 'balance' to check captcha solver balance, or 'exit' to quit:")
		command := readInput()

		switch command {
		case "check":
			checkAccounts()
		case "validate":
			validateAccounts()
		case "balance":
			checkCaptchaBalance()
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
			//			PreferredCaptchaService: "ez_captcha",
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

	/*	fmt.Print("Enter your 2Captcha API Key (leave empty to keep current): ")
		input = readInput()
		if input != "" {
			config.TwoCaptchaKey = input
		}

		fmt.Print("Enter preferred captcha service (ez_captcha/two_captcha, leave empty to keep current): ")
		input = readInput()
		if input == "ez_captcha" || input == "two_captcha" {
			config.PreferredCaptchaService = input
		}
	*/
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
	fmt.Println("Enter accounts in the format 'title:ssocookie', one per line. Enter an empty line when done:")
	for {
		input := readInput()
		if input == "" {
			break
		}
		parts := strings.SplitN(input, ":", 2)
		if len(parts) == 2 {
			accounts = append(accounts, Account{Title: parts[0], SSOCookie: parts[1]})
		} else {
			fmt.Println("Invalid format. Please use 'title:ssocookie'")
		}
	}
}

func readInput() string {
	reader := bufio.NewReader(os.Stdin)
	input, _ := reader.ReadString('\n')
	return strings.TrimSpace(input)
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

func validateAccounts() {
	for _, account := range accounts {
		isValid := validateSSOCookie(account.SSOCookie)
		status := "Valid"
		if !isValid {
			status = "Invalid"
		}
		fmt.Printf("%s: SSO Cookie is %s\n", account.Title, status)
	}
}

func checkCaptchaBalance() {
	//	if config.EZCaptchaKey != "" {
	balance, err := getEZCaptchaBalance()
	if err != nil {
		fmt.Printf("Error checking EZ-Captcha balance: %v\n", err)
	} else {
		fmt.Printf("EZ-Captcha balance: %s\n", balance)
	}
}

/*
		if config.TwoCaptchaKey != "" {
			balance, err := getTwoCaptchaBalance()
			if err != nil {
				fmt.Printf("Error checking 2Captcha balance: %v\n", err)
			} else {
				fmt.Printf("2Captcha balance: %s\n", balance)
			}
		}

		if config.EZCaptchaKey == "" && config.TwoCaptchaKey == "" {
			fmt.Println("No captcha solving service configured.")
		}
	}
*/
func solveCaptcha() (string, error) {
	return solveEZCaptcha()
	/*	if config.PreferredCaptchaService == "ez_captcha" && config.EZCaptchaKey != "" {
			solution, err := solveEZCaptcha()
			if err == nil {
				return solution, nil
			}
			debugLog(fmt.Sprintf("EZ-Captcha failed: %v. Trying 2Captcha...", err))
		}

		if config.TwoCaptchaKey != "" {
			return solveTwoCaptcha()
		}

		return "", fmt.Errorf("no valid captcha solving service configured")
	*/
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

/*
	func solveTwoCaptcha() (string, error) {
		debugLog("Starting 2Captcha solving process")

		payload := map[string]interface{}{
			"clientKey": config.TwoCaptchaKey,
			"task": map[string]interface{}{
				"type":       "RecaptchaV2TaskProxyless",
				"websiteURL": config.PageURL,
				"websiteKey": config.SiteKey,
			},
		}

		jsonPayload, _ := json.Marshal(payload)
		resp, err := http.Post(TwoCaptchaAPIURL, "application/json", strings.NewReader(string(jsonPayload)))
		if err != nil {
			return "", err
		}
		defer resp.Body.Close()

		var result struct {
			ErrorId          int    `json:"errorId"`
			ErrorCode        string `json:"errorCode"`
			ErrorDescription string `json:"errorDescription"`
			TaskId           int    `json:"taskId"`
		}
		json.NewDecoder(resp.Body).Decode(&result)

		if result.ErrorId != 0 {
			return "", fmt.Errorf("2Captcha error: %s - %s", result.ErrorCode, result.ErrorDescription)
		}

		debugLog(fmt.Sprintf("2Captcha task created: %d", result.TaskId))

		for i := 0; i < MaxRetries; i++ {
			time.Sleep(RetryInterval)

			solution, err := getTwoCaptchaResult(result.TaskId)
			if err == nil {
				debugLog("2Captcha solved successfully")
				return solution, nil
			}

			debugLog(fmt.Sprintf("2Captcha solving attempt %d failed: %v", i+1, err))
		}

		return "", fmt.Errorf("failed to solve 2Captcha after %d attempts", MaxRetries)
	}

	func getTwoCaptchaResult(taskId int) (string, error) {
		payload := map[string]interface{}{
			"clientKey": config.TwoCaptchaKey,
			"taskId":    taskId,
		}

		jsonPayload, _ := json.Marshal(payload)
		resp, err := http.Post(TwoCaptchaResultURL, "application/json", strings.NewReader(string(jsonPayload)))
		if err != nil {
			return "", err
		}
		defer resp.Body.Close()

		var result struct {
			ErrorId          int    `json:"errorId"`
			ErrorCode        string `json:"errorCode"`
			ErrorDescription string `json:"errorDescription"`
			Status           string `json:"status"`
			Solution         struct {
				GRecaptchaResponse string `json:"gRecaptchaResponse"`
			} `json:"solution"`
		}
		json.NewDecoder(resp.Body).Decode(&result)

		if result.Status == "ready" {
			return result.Solution.GRecaptchaResponse, nil
		}

		return "", fmt.Errorf("captcha not ready")
	}

	func report2CaptchaResult(taskId int, success bool) error {
		payload := map[string]interface{}{
			"clientKey": config.TwoCaptchaKey,
			"taskId":    taskId,
		}

		var endpoint string
		if success {
			endpoint = "https://api.2captcha.com/reportCorrect"
		} else {
			endpoint = "https://api.2captcha.com/reportIncorrect"
		}

		jsonPayload, _ := json.Marshal(payload)
		resp, err := http.Post(endpoint, "application/json", strings.NewReader(string(jsonPayload)))
		if err != nil {
			return fmt.Errorf("network error: %v", err)
		}
		defer resp.Body.Close()

		var result struct {
			ErrorId          int    `json:"errorId"`
			ErrorCode        string `json:"errorCode"`
			ErrorDescription string `json:"errorDescription"`
		}
		json.NewDecoder(resp.Body).Decode(&result)

		if result.ErrorId != 0 {
			return fmt.Errorf("2Captcha error: %s - %s", result.ErrorCode, result.ErrorDescription)
		}

		return nil
	}
*/
func validateSSOCookie(ssoCookie string) bool {
	client := &http.Client{}
	req, err := http.NewRequest("GET", ProfileURL, nil)
	if err != nil {
		fmt.Printf("Error creating request: %v\n", err)
		return false
	}

	req.Header.Set("Cookie", fmt.Sprintf("ACT_SSO_COOKIE=%s", ssoCookie))
	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3")

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

	/*
	   return fmt.Sprintf("%.2f", result.Balance), nil
	   }

	   func getTwoCaptchaBalance() (string, error) {
	   	payload := map[string]string{
	   		"clientKey": config.TwoCaptchaKey,
	   	}

	   	jsonPayload, err := json.Marshal(payload)
	   	if err != nil {
	   		return "", fmt.Errorf("error creating JSON payload: %v", err)
	   	}

	   	resp, err := http.Post(TwoCaptchaBalanceURL, "application/json", bytes.NewBuffer(jsonPayload))
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
	   		return "", fmt.Errorf("2Captcha error: %s - %s", result.ErrorCode, result.ErrorDescription)
	   	}
	*/
	return fmt.Sprintf("%.2f", result.Balance), nil
}

func debugLog(message string) {
	if config.DebugMode {
		fmt.Printf("[DEBUG] %s\n", message)
	}
}

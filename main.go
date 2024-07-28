package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"strings"
	"time"
)

const (
	EZCaptchaAPIURL    = "https://api.ez-captcha.com/createTask"
	EZCaptchaResultURL = "https://api.ez-captcha.com/getTaskResult"
	AccountCheckURL    = "https://support.activision.com/api/bans/v2/appeal?locale=en"
	ProfileURL         = "https://support.activision.com/api/profile?accts=false"
	MaxRetries         = 40
	RetryInterval      = 3 * time.Second
	ConfigFileName     = "config.json"
)

type Config struct {
	SSOCookie    string `json:"sso_cookie"`
	EZCaptchaKey string `json:"ez_captcha_key"`
	SiteKey      string `json:"site_key"`
	PageURL      string `json:"page_url"`
}

func main() {
	printIntro()

	config := loadConfig()

	if config == nil {
		config = getInitialConfig()
		saveConfig(config)
	} else {
		fmt.Println("Configuration loaded from file.")
		fmt.Println("Enter 'update' to update configuration, or press Enter to continue with saved config.")
		if readInput() == "update" {
			updateConfig(config)
			saveConfig(config)
		}
	}

	for {
		fmt.Println("\nEnter 'check' to check account status, 'validate' to validate SSO cookie, or 'exit' to quit:")
		command := readInput()

		switch command {
		case "check":
			if validateSSOCookie(config) {
				checkAccount(config)
			} else {
				fmt.Println("Invalid SSO cookie. Please update your configuration.")
			}
		case "validate":
			if validateSSOCookie(config) {
				fmt.Println("SSO cookie is valid.")
			} else {
				fmt.Println("SSO cookie is invalid. Please update your configuration.")
			}
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
   ________ ____  _____ _____ __        __              
  / ____/ // __ \/ ___// ___// /_____ _/ /___  _______  
 / /   / // / / /\__ \ \__ \/ __/ __ '/ __/ / / / ___/  
/ /___/ // /_/ /___/ /___/ / /_/ /_/ / /_/ /_/ (__  )   
\____/_(_)____//____//____/\__/\__,_/\__/\__,_/____/    
                                                        
    ____                                  __   ________        __           
   / __ \___  ______________  ____  _____/ /  / ____/ /_  ____/ /_____  _____
  / /_/ / _ \/ ___/ ___/ __ \/ __ \/ ___/ /  / /   / __ \/ __  / ___/ |/_/ _ \
 / ____/  __/ /  (__  ) /_/ / / / / /  / /  / /___/ / / / /_/ / /__>  </  __/
/_/    \___/_/  /____/\____/_/ /_/_/  /_/   \____/_/ /_/\__,_/\___/_/|_|\___/ 
                                                                              
`
	fmt.Println(intro)
}

func loadConfig() *Config {
	data, err := os.ReadFile(ConfigFileName)
	if err != nil {
		return nil
	}

	var config Config
	err = json.Unmarshal(data, &config)
	if err != nil {
		fmt.Printf("Error parsing config file: %v\n", err)
		return nil
	}

	return &config
}

func saveConfig(config *Config) {
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

func getInitialConfig() *Config {
	config := &Config{
		SiteKey: "6LdB2NUpAAAAANcdcy9YcjBOBD4rY-TIHOeolkkk",
		PageURL: "https://support.activision.com",
	}

	fmt.Print("Enter your SSO Cookie: ")
	config.SSOCookie = readInput()

	fmt.Print("Enter your EZ-Captcha API Key: ")
	config.EZCaptchaKey = readInput()

	return config
}

func updateConfig(config *Config) {
	fmt.Printf("Enter your SSO Cookie (current: %s): ", config.SSOCookie)
	input := readInput()
	if input != "" {
		config.SSOCookie = input
	}

	fmt.Printf("Enter your EZ-Captcha API Key (current: %s): ", config.EZCaptchaKey)
	input = readInput()
	if input != "" {
		config.EZCaptchaKey = input
	}

	fmt.Printf("Enter the Site Key (current: %s): ", config.SiteKey)
	input = readInput()
	if input != "" {
		config.SiteKey = input
	}

	fmt.Printf("Enter the Page URL (current: %s): ", config.PageURL)
	input = readInput()
	if input != "" {
		config.PageURL = input
	}
}

func readInput() string {
	reader := bufio.NewReader(os.Stdin)
	input, _ := reader.ReadString('\n')
	return strings.TrimSpace(input)
}

func validateSSOCookie(config *Config) bool {
	client := &http.Client{}
	req, err := http.NewRequest("GET", ProfileURL, nil)
	if err != nil {
		fmt.Printf("Error creating request: %v\n", err)
		return false
	}

	req.Header.Set("Cookie", fmt.Sprintf("ACT_SSO_COOKIE=%s", config.SSOCookie))
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

func checkAccount(config *Config) {
	fmt.Println("Checking account status...")

	captchaResponse, err := solveCaptcha(config)
	if err != nil {
		fmt.Printf("Error solving captcha: %v\n", err)
		return
	}

	accountStatus, err := sendAccountCheckRequest(config, captchaResponse)
	if err != nil {
		fmt.Printf("Error checking account status: %v\n", err)
		return
	}

	saveResponseToFile(accountStatus)

	fmt.Println("Account status check complete. Response saved to 'account_status.txt'.")
}

func solveCaptcha(config *Config) (string, error) {
	taskID, err := createCaptchaTask(config)
	if err != nil {
		return "", err
	}

	for i := 0; i < MaxRetries; i++ {
		solution, err := getCaptchaResult(config, taskID)
		if err == nil {
			return solution, nil
		}
		time.Sleep(RetryInterval)
	}

	return "", fmt.Errorf("failed to solve captcha after %d attempts", MaxRetries)
}

func createCaptchaTask(config *Config) (string, error) {
	payload := map[string]interface{}{
		"clientKey": config.EZCaptchaKey,
		"appid": "84291",
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
		TaskID string `json:"taskId"`
	}
	json.NewDecoder(resp.Body).Decode(&result)

	return result.TaskID, nil
}

func getCaptchaResult(config *Config, taskID string) (string, error) {
	payload := map[string]string{
		"clientKey": config.EZCaptchaKey,
		"taskId":    taskID,
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

func sendAccountCheckRequest(config *Config, captchaResponse string) (string, error) {
	client := &http.Client{}

	reqURL := fmt.Sprintf("%s&g-cc=%s", AccountCheckURL, url.QueryEscape(captchaResponse))
	req, err := http.NewRequest("GET", reqURL, nil)
	if err != nil {
		return "", err
	}

	req.Header.Set("Cookie", fmt.Sprintf("ACT_SSO_COOKIE=%s", config.SSOCookie))
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

	return string(body), nil
}

func saveResponseToFile(response string) {
	err := os.WriteFile("account_status.txt", []byte(response), 0644)
	if err != nil {
		fmt.Printf("Error saving response to file: %v\n", err)
	}
}

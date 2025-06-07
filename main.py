import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
import requests

# Environment Variables (set these on Railway)
USERNAME = os.getenv("RAZA_USERNAME")
PASSWORD = os.getenv("RAZA_PASSWORD")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

LOGIN_URL = "https://miqaat.its52.com/Login.aspx?tag=2&"
STATUS_URL = "https://miqaat.its52.com/Registration/Status.aspx"

def send_slack_message(message):
    if not SLACK_WEBHOOK_URL:
        print("No Slack webhook URL provided.")
        return
    payload = {"text": message}
    try:
        requests.post(SLACK_WEBHOOK_URL, json=payload)
    except Exception as e:
        print(f"Failed to send slack message: {e}")

def check_status():
    # Set up headless Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=chrome_options)

    try:
        driver.get(LOGIN_URL)
        time.sleep(3)

        # Login
        driver.find_element(By.ID, "txtUserName").send_keys(USERNAME)
        driver.find_element(By.ID, "txtPassword").send_keys(PASSWORD)
        driver.find_element(By.ID, "btnLogin").click()
        time.sleep(5)

        # Handle possible waiting room page or redirect
        while True:
            current_url = driver.current_url
            if "WaitingRoom" in current_url:
                print("In waiting room, waiting 60 seconds...")
                time.sleep(60)
                driver.refresh()
                time.sleep(5)
            else:
                break

        # On post-login page, click the "Check Status" button
        try:
            check_status_button = driver.find_element(By.XPATH, "//button[contains(text(),'Check Status') or contains(text(),'🟢')]")
            check_status_button.click()
            time.sleep(5)
        except NoSuchElementException:
            print("Check Status button not found, trying again after wait...")
            time.sleep(30)
            driver.refresh()
            time.sleep(5)
            check_status_button = driver.find_element(By.XPATH, "//button[contains(text(),'Check Status') or contains(text(),'🟢')]")
            check_status_button.click()
            time.sleep(5)

        # Find Raza Status
        try:
            status_text = driver.find_element(By.XPATH, "//td[contains(text(),'Raza Status')]/following-sibling::td").text.strip()
            print(f"Current Raza Status: {status_text}")
            return status_text
        except NoSuchElementException:
            print("Raza Status not found.")
            return None

    finally:
        driver.quit()

def main():
    last_status = None

    while True:
        try:
            status = check_status()
            if status and status.lower() != "pending":
                if status != last_status:
                    message = f"🚨 Raza Status changed from '{last_status}' to '{status}'!"
                    print(message)
                    send_slack_message(message)
                    last_status = status
                else:
                    print(f"Status unchanged: {status}")
            else:
                print("Status is pending or unknown.")

        except Exception as e:
            print(f"Error occurred: {e}")

        # Wait 1 hour before next check
        time.sleep(3600)

if __name__ == "__main__":
    main()

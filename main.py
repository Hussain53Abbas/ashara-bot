import os
import asyncio
import requests
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

USERNAME = os.getenv("RAZA_USERNAME")
PASSWORD = os.getenv("RAZA_PASSWORD")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

LOGIN_URL = "https://miqaat.its52.com/Login.aspx?tag=2&"

async def send_slack_message(message):
    if not SLACK_WEBHOOK_URL:
        print("[Slack] No webhook URL configured, skipping notification.")
        return
    try:
        resp = requests.post(SLACK_WEBHOOK_URL, json={"text": message})
        if resp.status_code != 200:
            print(f"[Slack] Failed to send message: {resp.status_code} - {resp.text}")
    except Exception as e:
        print(f"[Slack] Exception sending message: {e}")

async def check_status(page):
    # Wait until login inputs are visible
    await page.goto(LOGIN_URL)
    await page.wait_for_selector("#txtUserName", timeout=10000)

    # Login
    print("[Browser] Logging in...")
    await page.fill("#txtUserName", USERNAME)
    await page.fill("#txtPassword", PASSWORD)
    await page.click("#btnLogin")
    await page.wait_for_load_state("networkidle")

    # Handle waiting room
    while True:
        url = page.url
        if "WaitingRoom" in url:
            print("[Browser] In waiting room, waiting 60 seconds...")
            await asyncio.sleep(60)
            print("[Browser] Checking if still in waiting room...")
            await page.reload()
            await page.wait_for_load_state("networkidle")
        else:
            break

    # On post-login page, click "Check Status" button (may have emoji)
    for attempt in range(3):
        try:
            # Try to find button by text or emoji - fuzzy match
            button = await page.wait_for_selector(
                "button:has-text('Check Status'), button:has-text('🟢'), button:has-text('🟡'), button:has-text('🔴')",
                timeout=5000
            )
            await button.click()
            print("[Browser] Clicked 'Check Status' button.")
            await page.wait_for_load_state("networkidle")
            break
        except PlaywrightTimeoutError:
            print("[Browser] 'Check Status' button not found, retrying after 30 seconds...")
            await asyncio.sleep(30)
            await page.reload()
    else:
        print("[Browser] Failed to find 'Check Status' button after retries.")
        return None

    # Find "Raza Status"
    try:
        # Wait for the element that contains 'Raza Status' label and then get sibling td text
        status_cell = await page.wait_for_selector("//td[contains(text(),'Raza Status')]/following-sibling::td", timeout=10000)
        status_text = (await status_cell.text_content()).strip()
        print(f"[Status] Current Raza Status: {status_text}")
        return status_text
    except PlaywrightTimeoutError:
        print("[Status] 'Raza Status' not found.")
        return None

async def main():
    if not USERNAME or not PASSWORD:
        print("[Error] Please set RAZA_USERNAME and RAZA_PASSWORD environment variables.")
        return

    last_status = None

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = await browser.new_context()
        page = await context.new_page()

        while True:
            try:
                status = await check_status(page)
                if status and status.lower() != "pending":
                    if status != last_status:
                        msg = f"🚨 Raza Status changed from '{last_status}' to '{status}'!"
                        print(msg)
                        await send_slack_message(msg)
                        last_status = status
                    else:
                        print(f"[Info] Status unchanged: {status}")
                else:
                    print("[Info] Status is pending or unknown, no Slack notification sent.")
            except Exception as e:
                print(f"[Error] Exception during status check: {e}")

            print("[Info] Waiting 1 hour before next check...")
            await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())

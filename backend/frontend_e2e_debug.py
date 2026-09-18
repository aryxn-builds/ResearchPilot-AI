import asyncio
from playwright.async_api import async_playwright
import time

async def run():
    email = "e2e_7755c2ec@example.com"
    password = "Password123!"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        page.on("console", lambda msg: print(f"BROWSER LOG: {msg.text}"))
        page.on("pageerror", lambda err: print(f"BROWSER ERROR: {err}"))
        page.on("response", lambda res: print(f"RESPONSE: {res.status} {res.url}") if res.status >= 400 else None)
        
        print("Navigating to login...")
        await page.goto("http://localhost:3000/login")
        
        print(f"Logging in with {email}...")
        await page.get_by_label("Email").fill(email)
        await page.get_by_label("Password").fill(password)
        await page.get_by_role("button", name="Sign In").click()
        
        print("Waiting for dashboard redirect...")
        await page.get_by_text("Start New Research").first.wait_for(timeout=15000)
        
        print("Navigating to report page...")
        await page.goto("http://localhost:3000/report/4bc2c55d-7813-493d-b07e-dab6f1b1fa1f")
        
        await page.wait_for_timeout(5000)
        await page.screenshot(path="e2e_report_page_debug.png")
        print("Done")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())

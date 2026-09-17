import asyncio
from playwright.async_api import async_playwright
import time

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            print("1. Navigating to login...")
            await page.goto("http://localhost:3000/login")
            
            print("2. Logging in...")
            await page.fill("input[type='email']", "e2e_tester@example.com")
            await page.fill("input[type='password']", "Password123!")
            await page.click("button[type='submit']")
            
            print("3. Waiting for dashboard...")
            await page.wait_for_url("**/dashboard")
            await page.screenshot(path="dashboard_screenshot.png", full_page=True)
            print("Dashboard loaded successfully.")
            
            print("4. Starting new research...")
            await page.click("text=Start New Research")
            await page.wait_for_url("**/research/new")
            
            print("5. Filling research question...")
            await page.fill("input#topic", "Compare the major differences between Python 3.11 and Python 3.12 for developers, including performance, typing, standard-library changes, and compatibility.")
            await page.click("button:has-text('Start Research')")
            
            print("6. Waiting for active research page and SSE...")
            await page.wait_for_url("**/research/active/**")
            await page.screenshot(path="active_research_start.png")
            
            print("7. Waiting for completion (this may take up to 3 minutes)...")
            # Wait for the view report button to appear
            await page.wait_for_selector("text=View Generated Report", timeout=180000)
            await page.screenshot(path="active_research_complete.png")
            print("Research completed successfully!")
            
            print("8. Viewing report...")
            await page.click("text=View Generated Report")
            await page.wait_for_url("**/report/**")
            await page.wait_for_timeout(2000) # Give markdown time to render
            await page.screenshot(path="report_screenshot.png", full_page=True)
            print("Report loaded.")
            
            print("9. Checking history...")
            await page.goto("http://localhost:3000/dashboard")
            await page.wait_for_load_state("networkidle")
            await page.screenshot(path="history_screenshot.png", full_page=True)
            print("History loaded.")
            
            print("E2E FLOW SUCCESSFUL")
        except Exception as e:
            print(f"E2E FLOW FAILED: {e}")
            await page.screenshot(path="error_screenshot.png")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())

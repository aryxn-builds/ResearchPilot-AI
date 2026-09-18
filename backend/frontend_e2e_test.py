import asyncio
import time
import uuid
from playwright.async_api import async_playwright, expect
from supabase._async.client import create_client
from app.core.config import settings

async def run():
    uid = uuid.uuid4().hex[:8]
    email = f"e2e_{uid}@example.com"
    password = "Password123!"
    
    print("Pre-creating user in Supabase to bypass email confirmation...")
    admin_supabase = await create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
    await admin_supabase.auth.admin.create_user({
        "email": email,
        "password": password,
        "email_confirm": True
    })
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        page.on("console", lambda msg: print(f"BROWSER: {msg.text}"))
        page.on("pageerror", lambda err: print(f"BROWSER ERROR: {err}"))

        print("Navigating to login...")
        await page.goto("http://localhost:3000/login")
        
        print(f"Logging in with {email}...")
        await page.get_by_label("Email").fill(email)
        await page.get_by_label("Password").fill(password)
        await page.get_by_role("button", name="Sign In").click()
        
        # Wait for redirect to dashboard
        print("Waiting for dashboard redirect...")
        try:
            await page.get_by_text("Start New Research").first.wait_for(timeout=15000)
        except Exception as e:
            print("Failed to redirect to dashboard. Checking for error messages...")
            try:
                error_msg = await page.locator(".text-status-error").text_content()
                print(f"Error on page: {error_msg}")
            except:
                pass
            await page.screenshot(path="login_failed.png")
            raise e
            
        print("Navigating to new research...")
        await page.goto("http://localhost:3000/research/new")
        
        # Fill the question using real keystrokes to ensure React state updates
        question = "Compare the major differences between Python 3.11 and Python 3.12 for developers, including performance, typing, standard-library changes, and compatibility."
        await page.locator("#topic").click()
        await page.locator("#topic").press_sequentially(question, delay=5)
        
        # Give React a moment to update state
        await page.wait_for_timeout(500)
        
        print("Submitting research...")
        await page.get_by_role("button", name="Start Research").click()
        
        # Wait for active research page
        print("Waiting for active research page...")
        try:
            await page.get_by_text("Agent Activity").first.wait_for(timeout=15000)
        except Exception as e:
            await page.screenshot(path="e2e_timeout.png")
            print("Saved e2e_timeout.png")
            raise e
        
        print("Research started. Waiting for completion (up to 10 minutes)...")
        # Wait for the "View Generated Report" button to appear and click it
        try:
            await page.get_by_role("button", name="View Generated Report").wait_for(timeout=600000)
            print("Research complete. Clicking to view report...")
            await page.get_by_role("button", name="View Generated Report").click()
        except Exception as e:
            await page.screenshot(path="e2e_timeout_report_button.png")
            print("Saved e2e_timeout_report_button.png")
            raise e
        
        print("Waiting for report page to load...")
        # The report page is at /report/{id} — wait for navigation to that URL
        try:
            await page.wait_for_url("**/report/**", timeout=20000)
        except Exception as e:
            print(f"URL did not navigate to /report/: {page.url}")
            await page.screenshot(path="e2e_report_url_timeout.png")
            raise e
        
        print(f"Report page loaded at: {page.url}")
        
        # Give the client component time to fetch data
        print("Waiting for report content to render...")
        try:
            # Wait for either the prose content (success) or error message (failure)
            await page.wait_for_selector(".prose, .text-status-error", timeout=20000)
        except Exception as e:
            print("Timeout waiting for report content.")
        
        # Take a screenshot to diagnose what's on the page
        await page.screenshot(path="e2e_report_page.png")
        print("Screenshot saved to e2e_report_page.png")
        
        # Check for various indicators of a rendered report page
        # The title h1 contains the research question
        h1_count = await page.locator("h1").count()
        print(f"Found {h1_count} H1 elements on page")
        
        # Try to find any card content
        card_count = await page.locator("[class*='card'], [class*='Card'], article, .max-w-4xl").count()
        print(f"Found {card_count} card/container elements")
        
        # Check the page text for research content
        page_text = await page.evaluate("() => document.body.innerText")
        print(f"Page text length: {len(page_text)}")
        
        if "Generated Research Report" in page_text or "Report" in page_text:
            print("Report header found in page text ✓")
        
        if "not found" in page_text.lower() or "404" in page_text:
            raise Exception(f"Report page shows 404/not found. Page text: {page_text[:200]}")
        
        # Check for meaningful content  
        if len(page_text.strip()) < 100:
            raise Exception(f"Report page appears empty. Page text: {page_text[:200]}")
            
        print(f"E2E Test Passed Successfully!")
        print(f"Report page content preview: {page_text[:300]}")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(run())

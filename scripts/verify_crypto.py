from playwright.sync_api import sync_playwright, expect
import re
import sys

def verify_crypto():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Navigate to the local server
        page.goto("http://localhost:8080")

        # Check title
        expect(page).to_have_title("GhostLink Crypto Verification")

        # Click the encrypt button
        page.get_by_role("button", name="Encrypt \"Hello World\"").click()

        # Wait for results
        key_locator = page.locator("#key")
        iv_locator = page.locator("#iv")
        ciphertext_locator = page.locator("#ciphertext")

        expect(key_locator).not_to_be_empty()
        expect(iv_locator).not_to_be_empty()
        expect(ciphertext_locator).not_to_be_empty()

        # Get values
        key = key_locator.text_content()
        iv = iv_locator.text_content()
        ciphertext = ciphertext_locator.text_content()

        print(f"Key: {key}")
        print(f"IV: {iv}")
        print(f"Ciphertext: {ciphertext}")

        # Basic validation of Base64URL format
        base64url_regex = r'^[A-Za-z0-9_-]+$'
        if not re.match(base64url_regex, key):
             print("Key is not in Base64URL format")
             sys.exit(1)
        if not re.match(base64url_regex, iv):
             print("IV is not in Base64URL format")
             sys.exit(1)
        if not re.match(base64url_regex, ciphertext):
             print("Ciphertext is not in Base64URL format")
             sys.exit(1)

        # Take screenshot
        page.screenshot(path="verification.png")
        print("Verification successful. Screenshot saved to verification.png")

        browser.close()

if __name__ == "__main__":
    verify_crypto()

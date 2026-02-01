import asyncio
import sys
import subprocess
import time
from playwright.async_api import async_playwright

async def run():
    # Start HTTP server
    port = 8001 # Use a different port than verify_crypto.py
    server = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--directory", "public"],
                              stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL)
    # Give it a moment to start
    time.sleep(2)

    base_url = f"http://localhost:{port}"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()

            # Step 1: Generate the link using test_harness and existing modules
            print("Navigating to test harness to generate link...")
            await page.goto(f"{base_url}/test_harness.html")
            await page.wait_for_function("window.testReady === true")

            print("Generating encrypted payload...")
            hash_fragment = await page.evaluate("""async () => {
                const Utils = await import('./js/utils.js');
                const Crypto = window.cryptoEngine;

                const key = await Crypto.generateKey();
                const text = "Secret Message " + Date.now();
                const encrypted = await Crypto.encrypt(text, key);
                const rawKey = await Crypto.exportKey(key);

                const cipherStr = Utils.bufferToBase64Url(encrypted.ciphertext);
                const ivStr = Utils.bufferToBase64Url(encrypted.iv);
                const keyStr = Utils.bufferToBase64Url(rawKey);

                return `#${cipherStr}|${ivStr}|${keyStr}`;
            }""")

            print(f"Generated hash: {hash_fragment}")

            # Step 2: Open the viewer with the hash
            target_url = f"{base_url}/index.html{hash_fragment}"
            print(f"Navigating to viewer: {target_url}")
            await page.goto(target_url)

            # Step 3: Verify message is displayed
            # The message starts with "Secret Message"
            print("Verifying message display...")
            # We wait for the message element to contain "Secret Message"
            message_locator = page.locator("#message")
            await message_locator.wait_for()

            text_content = await message_locator.text_content()
            print(f"Message content: {text_content}")

            if "Secret Message" not in text_content:
                print("FAIL: Message not displayed correctly")
                sys.exit(1)

            # Step 4: Verify URL is cleared (Burn-on-Read)
            print("Verifying URL cleared...")
            current_url = page.url
            print(f"Current URL: {current_url}")

            # Should be just the base path (e.g. /index.html or /)
            # The hash should be gone.
            if "#" in current_url:
                 print("FAIL: URL hash was not cleared")
                 sys.exit(1)

            # Step 5: Reload and verify message is gone
            print("Reloading page...")
            await page.reload()

            # The message element should be empty or not contain the secret
            text_content_reloaded = await message_locator.text_content()
            print(f"Message content after reload: '{text_content_reloaded}'")

            if "Secret Message" in text_content_reloaded:
                print("FAIL: Message persisted after reload (should have been cleared from URL)")
                sys.exit(1)

            print("PASS")
            await browser.close()

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        server.terminate()

if __name__ == "__main__":
    asyncio.run(run())

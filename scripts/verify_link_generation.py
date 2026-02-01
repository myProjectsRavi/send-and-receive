import asyncio
import sys
import subprocess
import time
import base64
from playwright.async_api import async_playwright

async def run():
    # Start HTTP server
    server = subprocess.Popen([sys.executable, "-m", "http.server", "8001", "--directory", "public"],
                              stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL)
    # Give it a moment to start
    time.sleep(2)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()

            print("Navigating to index.html...")
            await page.goto("http://localhost:8001/index.html")

            # Enter text
            test_message = "Super Secret Message"
            await page.fill("#message-input", test_message)

            # Click generate
            await page.click("#generate-btn")

            # Wait for output
            # We can wait for textContent of #link-output to be non-empty
            await page.wait_for_function("document.getElementById('link-output').textContent.length > 0")

            link_url = await page.eval_on_selector("#link-output", "el => el.textContent")
            print(f"Generated URL: {link_url}")

            if "#" not in link_url:
                print("FAIL: URL does not contain fragment")
                sys.exit(1)

            fragment = link_url.split("#")[1]
            parts = fragment.split("|")

            if len(parts) != 3:
                print(f"FAIL: Expected 3 parts in fragment, got {len(parts)}")
                sys.exit(1)

            ciphertext_b64, iv_b64, key_b64 = parts

            # Helper to decode base64url
            def decode_b64url(s):
                s = s.replace("-", "+").replace("_", "/")
                padding = len(s) % 4
                if padding:
                    s += "=" * (4 - padding)
                return base64.b64decode(s)

            try:
                iv = decode_b64url(iv_b64)
                key = decode_b64url(key_b64)
                ciphertext = decode_b64url(ciphertext_b64)

                print(f"IV length: {len(iv)}")
                print(f"Key length: {len(key)}")
                print(f"Ciphertext length: {len(ciphertext)}")

                if len(iv) != 12:
                     print("FAIL: IV length must be 12 bytes")
                     sys.exit(1)

                if len(key) != 32: # 256 bits
                     print("FAIL: Key length must be 32 bytes")
                     sys.exit(1)

                if len(ciphertext) == 0:
                     print("FAIL: Ciphertext is empty")
                     sys.exit(1)

            except Exception as e:
                print(f"FAIL: Base64 decoding error: {e}")
                sys.exit(1)

            print("PASS")
            await browser.close()

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        server.terminate()

if __name__ == "__main__":
    asyncio.run(run())

import asyncio
import sys
import subprocess
import time
from playwright.async_api import async_playwright

async def run():
    # Start HTTP server
    server = subprocess.Popen([sys.executable, "-m", "http.server", "8000", "--directory", "public"],
                              stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL)
    # Give it a moment to start
    time.sleep(2)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()

            print("Navigating to test page...")
            await page.goto("http://localhost:8000/test_harness.html")
            await page.wait_for_function("window.testReady === true")

            print("Generating key...")
            key_handle = await page.evaluate_handle("window.cryptoEngine.generateKey()")

            print("Encrypting text...")
            # We wrap the evaluation to handle the promise and return plain objects
            result = await page.evaluate("""async (key) => {
                const text = "Hello World";
                const result = await window.cryptoEngine.encrypt(text, key);
                return {
                    ciphertext: Array.from(new Uint8Array(result.ciphertext)),
                    iv: Array.from(result.iv)
                };
            }""", key_handle)

            print(f"Ciphertext length: {len(result['ciphertext'])}")
            print(f"IV length: {len(result['iv'])}")

            if len(result['iv']) != 12:
                print("FAIL: IV length incorrect (expected 12)")
                sys.exit(1)

            if len(result['ciphertext']) == 0:
                print("FAIL: Ciphertext is empty")
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

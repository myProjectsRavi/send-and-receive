import sys
from playwright.sync_api import sync_playwright
import os
import http.server
import socketserver
import threading
import time

def run():
    # Start a server in the background
    PORT = 8080
    Handler = http.server.SimpleHTTPRequestHandler

    # We need to serve the public directory
    # Current CWD is root of repo
    web_dir = os.path.join(os.getcwd(), 'public')
    os.chdir(web_dir)

    httpd = socketserver.TCPServer(("", PORT), Handler)
    server_thread = threading.Thread(target=httpd.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    print(f"Serving {web_dir} at port {PORT}")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()

            page.goto(f"http://localhost:{PORT}")

            # Input text
            test_message = "This is a secret message for verification."
            page.fill("#message-input", test_message)

            # Click generate
            page.click("#generate-btn")

            # Wait for result
            page.wait_for_selector("#result-area", state="visible")

            # Get the link
            # In my HTML, #share-link is an <a> tag, so I should get 'href' or 'innerText'
            # But the logic sets href and textContent.
            link_element = page.wait_for_selector("#share-link")
            link = link_element.get_attribute("href")

            print(f"Generated Link: {link}")

            if not link or "#" not in link:
                print("Error: Link does not contain hash fragment.")
                sys.exit(1)

            fragment = link.split("#")[1]
            parts = fragment.split("|")

            if len(parts) != 3:
                print(f"Error: Fragment does not have 3 parts (iv|ciphertext|key). Found {len(parts)} parts.")
                sys.exit(1)

            iv, ciphertext, key = parts

            print(f"IV: {iv}")
            print(f"Ciphertext: {ciphertext}")
            print(f"Key: {key}")

            # Basic validation of Base64URL
            import re
            base64url_pattern = re.compile(r'^[A-Za-z0-9\-_]+$')

            if not base64url_pattern.match(iv):
                print("Error: IV is not valid Base64URL")
                sys.exit(1)
            if not base64url_pattern.match(ciphertext):
                print("Error: Ciphertext is not valid Base64URL")
                sys.exit(1)
            if not base64url_pattern.match(key):
                print("Error: Key is not valid Base64URL")
                sys.exit(1)

            print("Verification Successful!")

    except Exception as e:
        print(f"Verification failed: {e}")
        sys.exit(1)
    finally:
        httpd.shutdown()
        server_thread.join()

if __name__ == "__main__":
    run()

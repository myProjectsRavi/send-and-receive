import sys
import os
import base64
import time
import threading
from http.server import SimpleHTTPRequestHandler, HTTPServer
from playwright.sync_api import sync_playwright, expect
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

# Helpers for Base64URL
def base64url_encode(data):
    return base64.urlsafe_b64encode(data).decode('utf-8').rstrip('=')

def generate_encrypted_url(port):
    key = os.urandom(32) # 256 bits
    iv = os.urandom(12)  # 96 bits for GCM

    encryptor = Cipher(
        algorithms.AES(key),
        modes.GCM(iv),
    ).encryptor()

    plaintext = b"Hello GhostLink Secret Message"
    ciphertext = encryptor.update(plaintext) + encryptor.finalize()
    tag = encryptor.tag

    # In WebCrypto AES-GCM, the tag is appended to the ciphertext
    full_ciphertext = ciphertext + tag

    iv_b64 = base64url_encode(iv)
    ciphertext_b64 = base64url_encode(full_ciphertext)
    key_b64 = base64url_encode(key)

    fragment = f"#{iv_b64}|{ciphertext_b64}|{key_b64}"
    return f"http://localhost:{port}/{fragment}"

class PartialHTTPRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory="public", **kwargs)

def run_server(port):
    httpd = HTTPServer(('localhost', port), PartialHTTPRequestHandler)
    print(f"Serving on port {port}")
    httpd.serve_forever()

def verify():
    port = 8089
    server_thread = threading.Thread(target=run_server, args=(port,), daemon=True)
    server_thread.start()
    time.sleep(1) # Wait for server

    url = generate_encrypted_url(port)
    print(f"Testing URL: {url}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Navigate
        page.goto(url)

        # Check message
        message_locator = page.locator("#message")
        try:
            expect(message_locator).to_have_text("Hello GhostLink Secret Message", timeout=5000)
        except Exception as e:
            print("Message not found or incorrect.")
            # Check for error status
            print("Status text:", page.locator("#status").text_content())
            page.screenshot(path="verification_failure.png")
            raise e

        # Check success status
        status_locator = page.locator("#status")
        expect(status_locator).to_have_text("Message decrypted successfully.")

        # Check URL hash cleared (Burn on Read)
        current_url = page.url
        print(f"Current URL: {current_url}")
        if '#' in current_url and len(current_url.split('#')[1]) > 0:
             print("FAILURE: Hash was not cleared!")
             sys.exit(1)

        # Screenshot
        page.screenshot(path="verification.png")
        print("Verification successful! Screenshot saved to verification.png")
        browser.close()

if __name__ == "__main__":
    verify()

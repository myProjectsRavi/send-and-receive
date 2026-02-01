import asyncio
from playwright.async_api import async_playwright
import sys

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        # User A (Initiator)
        page_a = await browser.new_page()
        await page_a.goto("http://localhost:8000/index.html")

        # User B (Receiver)
        page_b = await browser.new_page()
        await page_b.goto("http://localhost:8000/index.html")

        # Step 1: Alice initiates
        print("Alice selecting Initiator mode...")
        await page_a.click("#mode-initiator")
        print("Alice clicking Generate Offer...")
        await page_a.click("#start-btn")

        # Wait for offer to be generated
        print("Waiting for offer...")
        await page_a.wait_for_selector("#offer-area", state="visible")
        # Wait for value to populate. playwright doesn't have :not(:empty) for input value easily, so we poll or wait.
        # But wait_for_function is better
        await page_a.wait_for_function("document.getElementById('offer-area').value.length > 0")

        offer_text = await page_a.input_value("#offer-area")
        print(f"Alice generated offer (len={len(offer_text)})")

        # Step 2: Bob accepts offer
        print("Bob selecting Receiver mode...")
        await page_b.click("#mode-receiver")
        await page_b.fill("#offer-input", offer_text)
        print("Bob clicking Generate Answer...")
        await page_b.click("#join-btn")

        # Wait for answer to be generated
        print("Waiting for answer...")
        await page_b.wait_for_selector("#answer-area", state="visible")
        await page_b.wait_for_function("document.getElementById('answer-area').value.length > 0")

        answer_text = await page_b.input_value("#answer-area")
        print(f"Bob generated answer (len={len(answer_text)})")

        # Step 3: Alice finalizes
        print("Alice pasting answer...")
        await page_a.fill("#answer-input", answer_text)
        print("Alice clicking Connect...")
        await page_a.click("#connect-btn")

        # Wait for connection on both sides
        print("Waiting for connection...")
        try:
            await page_a.wait_for_selector("#chat-ui", state="visible", timeout=10000)
            print("Alice connected!")

            await page_b.wait_for_selector("#chat-ui", state="visible", timeout=10000)
            print("Bob connected!")
        except Exception as e:
            print(f"Connection timed out or failed: {e}")
            # print status from both
            status_a = await page_a.text_content("#status")
            status_b = await page_b.text_content("#status")
            print(f"Alice Status: {status_a}")
            print(f"Bob Status: {status_b}")
            sys.exit(1)

        # Step 4: Verify Message Passing
        print("Alice sending message...")
        await page_a.fill("#msg-input", "Hello Bob")
        await page_a.click("#send-btn")

        print("Waiting for Bob to receive...")
        await page_b.wait_for_selector("#messages div", state="visible")
        content = await page_b.text_content("#messages div")
        if "Peer: Hello Bob" in content:
            print("Bob received message!")
        else:
            print(f"Bob received unexpected content: {content}")
            sys.exit(1)

        await browser.close()
        print("Verification Successful")

if __name__ == "__main__":
    asyncio.run(run())

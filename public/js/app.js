import * as Crypto from './crypto.js';

// Store the encrypted fragment for potential future decryption (F2)
let encryptedFragment = null;

document.addEventListener('DOMContentLoaded', async () => {
    const messageInput = document.getElementById('message-input');
    const encryptBtn = document.getElementById('encrypt-btn');
    const resultArea = document.getElementById('result-area');
    const shareLink = document.getElementById('share-link');
    const copyBtn = document.getElementById('copy-btn');
    const senderUi = document.getElementById('sender-ui');
    const receiverUi = document.getElementById('receiver-ui');

    const checkHash = () => {
        // S5: Burn on read (Simulated)
        // Check if there is a hash that looks like our format (starts with # and has content)
        if (window.location.hash && window.location.hash.length > 1) {
            // Capture the hash content before burning
            encryptedFragment = window.location.hash.substring(1);

            console.log("GhostLink: Hash detected, initiating burn sequence.");

            // Hide sender UI to indicate we are in "Read Mode" (even if we don't display the message yet)
            senderUi.classList.add('hidden');
            receiverUi.classList.remove('hidden');

            // Burn it from history
            // This removes the hash from the browser's address bar and history entry
            history.replaceState(null, '', window.location.pathname);
            console.log("GhostLink: Message link burned from history.");
            return true;
        }
        return false;
    };

    // Check on load
    if (checkHash()) return;

    // Check on hash change (if user navigates within same page)
    window.addEventListener('hashchange', () => {
        checkHash();
    });

    // S1: Encrypt and generate link
    if (encryptBtn) {
        encryptBtn.addEventListener('click', async () => {
            const text = messageInput.value;
            if (!text) {
                alert("Please enter a message.");
                return;
            }

            if (text.length > 1000) {
                alert("Message too long (max 1000 characters).");
                return;
            }

            try {
                const key = await Crypto.generateKey();
                const { iv, ciphertext } = await Crypto.encryptMessage(text, key);
                const fragment = await Crypto.exportData(key, iv, ciphertext);

                const fullUrl = `${window.location.origin}${window.location.pathname}${fragment}`;

                shareLink.value = fullUrl;
                resultArea.classList.remove('hidden');

                // Automatically focus the input for easy copying
                shareLink.focus();
                shareLink.select();

                // Optional: Auto-copy
                try {
                    await navigator.clipboard.writeText(fullUrl);
                    const originalText = copyBtn.textContent;
                    copyBtn.textContent = "Copied!";
                    setTimeout(() => copyBtn.textContent = originalText, 2000);
                } catch (e) {
                    // Ignore auto-copy errors, user can click button
                }

            } catch (err) {
                console.error("Encryption failed:", err);
                alert("Failed to encrypt message.");
            }
        });
    }

    if (copyBtn) {
        copyBtn.addEventListener('click', () => {
            shareLink.select();
            navigator.clipboard.writeText(shareLink.value).then(() => {
                const originalText = copyBtn.textContent;
                copyBtn.textContent = "Copied!";
                setTimeout(() => copyBtn.textContent = originalText, 2000);
            }).catch(err => {
                console.error('Failed to copy: ', err);
                alert("Failed to copy to clipboard. Please copy manually.");
            });
        });
    }
});

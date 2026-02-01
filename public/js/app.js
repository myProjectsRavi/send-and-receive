import { cryptoService } from './crypto.js';

document.addEventListener('DOMContentLoaded', () => {
    const generateBtn = document.getElementById('generate-btn');
    const messageInput = document.getElementById('message-input');
    const resultArea = document.getElementById('result-area');
    const shareLink = document.getElementById('share-link');
    const copyBtn = document.getElementById('copy-btn');

    generateBtn.addEventListener('click', async () => {
        const text = messageInput.value;
        if (!text) {
            alert('Please enter a message.');
            return;
        }

        try {
            const key = await cryptoService.generateKey();
            const { iv, ciphertext } = await cryptoService.encrypt(text, key);
            const exportedKey = await cryptoService.exportKey(key);

            // Format: #iv|ciphertext|key
            const fragment = `${iv}|${ciphertext}|${exportedKey}`;
            const url = `${window.location.origin}${window.location.pathname}#${fragment}`;

            shareLink.href = url;
            shareLink.textContent = url;
            resultArea.style.display = 'block';
        } catch (error) {
            console.error('Encryption failed:', error);
            alert('Failed to generate link. See console for details.');
        }
    });

    copyBtn.addEventListener('click', () => {
        navigator.clipboard.writeText(shareLink.href).then(() => {
            const originalText = copyBtn.textContent;
            copyBtn.textContent = 'Copied!';
            setTimeout(() => {
                copyBtn.textContent = originalText;
            }, 2000);
        }).catch(err => {
            console.error('Failed to copy: ', err);
        });
    });
});

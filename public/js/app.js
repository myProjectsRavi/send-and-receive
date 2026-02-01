import { generateKey, encrypt, exportKey } from './crypto.js';
import { bufferToBase64Url } from './utils.js';

document.getElementById('generate-btn').addEventListener('click', async () => {
    const messageInput = document.getElementById('message-input');
    const linkOutput = document.getElementById('link-output');
    const message = messageInput.value;

    if (!message) {
        alert('Please enter a message.');
        return;
    }

    try {
        const key = await generateKey();
        const encryptedData = await encrypt(message, key);
        const rawKey = await exportKey(key);

        const ivStr = bufferToBase64Url(encryptedData.iv);
        const ctStr = bufferToBase64Url(encryptedData.ciphertext);
        const keyStr = bufferToBase64Url(rawKey);

        const hash = `${ctStr}|${ivStr}|${keyStr}`;
        const url = `${window.location.origin}${window.location.pathname}#${hash}`;

        linkOutput.textContent = url;
    } catch (error) {
        console.error('Encryption failed:', error);
        alert('An error occurred during encryption.');
    }
});

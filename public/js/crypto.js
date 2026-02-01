// Cryptographic functions using Web Crypto API

const crypto = globalThis.crypto;

// Helper to encode ArrayBuffer to Base64URL
function arrayBufferToBase64Url(buffer) {
    const bytes = new Uint8Array(buffer);
    let binary = '';
    for (let i = 0; i < bytes.byteLength; i++) {
        binary += String.fromCharCode(bytes[i]);
    }
    const base64 = btoa(binary);
    return base64.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

export async function generateKey() {
    return await crypto.subtle.generateKey(
        {
            name: "AES-GCM",
            length: 256
        },
        true,
        ["encrypt", "decrypt"]
    );
}

export async function encryptMessage(text, key) {
    const encoder = new TextEncoder();
    const data = encoder.encode(text);
    const iv = crypto.getRandomValues(new Uint8Array(12)); // 96-bit IV for AES-GCM

    const ciphertext = await crypto.subtle.encrypt(
        {
            name: "AES-GCM",
            iv: iv
        },
        key,
        data
    );

    return {
        iv: iv,
        ciphertext: ciphertext
    };
}

export async function exportData(key, iv, ciphertext) {
    // Export key to raw format
    const rawKey = await crypto.subtle.exportKey("raw", key);

    const ivStr = arrayBufferToBase64Url(iv);
    const keyStr = arrayBufferToBase64Url(rawKey);
    const cipherStr = arrayBufferToBase64Url(ciphertext);

    // Format: #iv|ciphertext|key
    return `#${ivStr}|${cipherStr}|${keyStr}`;
}

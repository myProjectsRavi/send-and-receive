import { generateKey, encryptMessage, exportData } from '../public/js/crypto.js';
import assert from 'assert';

const crypto = globalThis.crypto;

function base64UrlToArrayBuffer(base64Url) {
    let base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    while (base64.length % 4) {
        base64 += '=';
    }
    const binary = atob(base64);
    const len = binary.length;
    const bytes = new Uint8Array(len);
    for (let i = 0; i < len; i++) {
        bytes[i] = binary.charCodeAt(i);
    }
    return bytes.buffer;
}

async function runTest() {
    console.log("Starting Crypto Verification...");

    const plaintext = "Hello GhostLink!";
    console.log(`Original Text: ${plaintext}`);

    // 1. Generate Key
    const key = await generateKey();
    assert(key, "Key generation failed");
    console.log("Key generated.");

    // 2. Encrypt
    const { iv, ciphertext } = await encryptMessage(plaintext, key);
    assert(iv, "IV missing");
    assert(ciphertext, "Ciphertext missing");
    console.log("Encryption successful.");

    // 3. Export
    const fragment = await exportData(key, iv, ciphertext);
    console.log(`Fragment: ${fragment}`);
    assert(fragment.startsWith('#'), "Fragment should start with #");

    // 4. Parse & Verify
    const parts = fragment.substring(1).split('|');
    assert.strictEqual(parts.length, 3, "Fragment should have 3 parts");

    const [ivStr, cipherStr, keyStr] = parts;

    const importedIv = base64UrlToArrayBuffer(ivStr);
    const importedCipher = base64UrlToArrayBuffer(cipherStr);
    const importedKeyRaw = base64UrlToArrayBuffer(keyStr);

    // Import Key back
    const importedKey = await crypto.subtle.importKey(
        "raw",
        importedKeyRaw,
        "AES-GCM",
        true,
        ["encrypt", "decrypt"]
    );

    // Decrypt
    const decryptedBuffer = await crypto.subtle.decrypt(
        {
            name: "AES-GCM",
            iv: importedIv
        },
        importedKey,
        importedCipher
    );

    const decoder = new TextDecoder();
    const decryptedText = decoder.decode(decryptedBuffer);

    console.log(`Decrypted Text: ${decryptedText}`);
    assert.strictEqual(decryptedText, plaintext, "Decrypted text should match original");

    console.log("VERIFICATION PASSED!");
}

runTest().catch(err => {
    console.error("VERIFICATION FAILED:", err);
    process.exit(1);
});

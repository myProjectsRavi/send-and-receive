import { decrypt } from './crypto.js';
import { base64UrlDecode } from './utils.js';

document.addEventListener('DOMContentLoaded', async () => {
  const hash = window.location.hash.substring(1);

  if (!hash) {
    document.getElementById('status').textContent = "No message in URL.";
    return;
  }

  // Burn on Read: Clear hash immediately
  history.replaceState(null, '', window.location.pathname);

  try {
    const parts = hash.split('|');
    if (parts.length !== 3) {
      throw new Error("Invalid URL format");
    }

    const [ivB64, ciphertextB64, keyB64] = parts;

    const iv = base64UrlDecode(ivB64);
    const ciphertext = base64UrlDecode(ciphertextB64);
    const key = base64UrlDecode(keyB64);

    const message = await decrypt(iv, ciphertext, key);

    document.getElementById('message').textContent = message;
    document.getElementById('status').textContent = "Message decrypted successfully.";
    document.getElementById('status').className = "success";

  } catch (err) {
    console.error(err);
    document.getElementById('message').textContent = "";
    document.getElementById('status').textContent = "Failed to decrypt message. Integrity check failed or URL is invalid.";
    document.getElementById('status').className = "error";
  }
});

import * as Utils from './utils.js';
import * as Crypto from './crypto.js';

async function init() {
  const hash = window.location.hash.substring(1); // Remove #
  if (!hash) return;

  // Format: ciphertext|iv|key
  const parts = hash.split('|');
  if (parts.length !== 3) {
    console.error('Invalid hash format');
    return;
  }

  const [ciphertextB64, ivB64, keyB64] = parts;

  try {
    const ciphertext = Utils.base64UrlToBuffer(ciphertextB64);
    const iv = new Uint8Array(Utils.base64UrlToBuffer(ivB64));
    const keyBytes = Utils.base64UrlToBuffer(keyB64);

    const key = await Crypto.importKey(keyBytes);
    const decryptedBuffer = await Crypto.decrypt(ciphertext, key, iv);

    const decoder = new TextDecoder();
    const message = decoder.decode(decryptedBuffer);

    const messageEl = document.getElementById('message');
    if (messageEl) {
        messageEl.textContent = message;
    }

    // Clear history
    history.replaceState(null, '', window.location.pathname);

  } catch (e) {
    console.error('Decryption failed:', e);
    const messageEl = document.getElementById('message');
    if (messageEl) {
        messageEl.textContent = 'Error: Could not decrypt message.';
        messageEl.style.color = 'red';
    }
  }
}

document.addEventListener('DOMContentLoaded', init);

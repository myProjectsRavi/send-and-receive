export const ALGO_NAME = 'AES-GCM';
export const KEY_LENGTH = 256;
export const IV_LENGTH = 12;

export async function generateKey() {
  return window.crypto.subtle.generateKey(
    {
      name: ALGO_NAME,
      length: KEY_LENGTH
    },
    true, // extractable
    ['encrypt', 'decrypt']
  );
}

export async function encrypt(text, key) {
  const encoder = new TextEncoder();
  const encoded = encoder.encode(text);
  const iv = window.crypto.getRandomValues(new Uint8Array(IV_LENGTH));

  const ciphertext = await window.crypto.subtle.encrypt(
    {
      name: ALGO_NAME,
      iv: iv
    },
    key,
    encoded
  );

  return {
    ciphertext: ciphertext,
    iv: iv
  };
}

export async function decrypt(ciphertext, key, iv) {
  return window.crypto.subtle.decrypt(
    {
      name: ALGO_NAME,
      iv: iv
    },
    key,
    ciphertext
  );
}

export async function exportKey(key) {
  return window.crypto.subtle.exportKey(
    "raw",
    key
  );
}

export async function importKey(rawKey) {
  return window.crypto.subtle.importKey(
    "raw",
    rawKey,
    {
      name: ALGO_NAME,
      length: KEY_LENGTH
    },
    true,
    ['encrypt', 'decrypt']
  );
}

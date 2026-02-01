/**
 * CryptoService
 * Handles AES-GCM encryption and key management using Web Crypto API.
 */

// Helper to encode ArrayBuffer to Base64URL
function arrayBufferToBase64Url(buffer) {
  const bytes = new Uint8Array(buffer);
  let binary = '';
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary)
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');
}

export const CryptoService = {
  /**
   * Generates a new AES-GCM key.
   * @returns {Promise<CryptoKey>}
   */
  async generateKey() {
    return window.crypto.subtle.generateKey(
      {
        name: "AES-GCM",
        length: 256
      },
      true, // extractable
      ["encrypt", "decrypt"]
    );
  },

  /**
   * Encrypts text data using AES-GCM.
   * @param {string} text - The text to encrypt.
   * @returns {Promise<{ciphertext: string, iv: string, key: string}>} - Base64URL encoded strings.
   */
  async encryptData(text) {
    // Generate Key
    const key = await this.generateKey();

    // Generate IV (12 bytes recommended for AES-GCM)
    const iv = window.crypto.getRandomValues(new Uint8Array(12));

    // Encode text to UTF-8
    const encoder = new TextEncoder();
    const data = encoder.encode(text);

    // Encrypt
    const ciphertextBuffer = await window.crypto.subtle.encrypt(
      {
        name: "AES-GCM",
        iv: iv
      },
      key,
      data
    );

    // Export Key
    const keyBuffer = await window.crypto.subtle.exportKey("raw", key);

    // Convert to Base64URL
    return {
      ciphertext: arrayBufferToBase64Url(ciphertextBuffer),
      iv: arrayBufferToBase64Url(iv.buffer),
      key: arrayBufferToBase64Url(keyBuffer)
    };
  }
};

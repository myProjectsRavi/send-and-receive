import { utils } from './utils.js';

export const cryptoService = {
  generateKey: async () => {
    return await window.crypto.subtle.generateKey(
      {
        name: "AES-GCM",
        length: 256,
      },
      true, // extractable
      ["encrypt", "decrypt"]
    );
  },

  exportKey: async (key) => {
    const exported = await window.crypto.subtle.exportKey("raw", key);
    return utils.arrayBufferToBase64Url(exported);
  },

  importKey: async (base64Key) => {
      const buffer = utils.base64UrlToArrayBuffer(base64Key);
      return await window.crypto.subtle.importKey(
          "raw",
          buffer,
          "AES-GCM",
          true,
          ["encrypt", "decrypt"]
      );
  },

  encrypt: async (text, key) => {
    const iv = window.crypto.getRandomValues(new Uint8Array(12)); // 96-bit IV recommended for GCM
    const encodedText = utils.textToBuffer(text);

    const ciphertext = await window.crypto.subtle.encrypt(
      {
        name: "AES-GCM",
        iv: iv,
      },
      key,
      encodedText
    );

    return {
      iv: utils.arrayBufferToBase64Url(iv),
      ciphertext: utils.arrayBufferToBase64Url(ciphertext)
    };
  }
};

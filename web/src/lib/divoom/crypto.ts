import { ModeOfOperation } from 'aes-js';

function ensureAligned(payload: Uint8Array): void {
  if (payload.length % 16 !== 0) {
    throw new Error(`AES payload length must be multiple of 16 (got ${payload.length})`);
  }
}

export function decryptAesCbcSync(payload: Uint8Array, key: Uint8Array, iv: Uint8Array): Uint8Array {
  ensureAligned(payload);
  const aes = new ModeOfOperation.cbc(key, iv);
  const decrypted = aes.decrypt(payload);
  return new Uint8Array(decrypted);
}



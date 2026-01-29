type Decompressor = any;

let decompressorPromise: Promise<Decompressor> | null = null;
let decompressorInstance: Decompressor | null = null;

export async function ensureZstdReady(): Promise<void> {
  if (decompressorInstance) return;
  if (!decompressorPromise) {
    if (typeof window === 'undefined') {
      throw new Error('Zstd can only be initialized in the browser');
    }
    decompressorPromise = (async () => {
      const mod = await import('zstd-wasm/lib/index.mjs');
      const instance = new mod.Decompressor();
      return instance.init();
    })();
  }
  decompressorInstance = await decompressorPromise;
}

export function zstdDecompressSync(payload: Uint8Array): Uint8Array {
  if (!decompressorInstance) {
    throw new Error('Zstd module not initialized');
  }
  return decompressorInstance.decompress(payload);
}



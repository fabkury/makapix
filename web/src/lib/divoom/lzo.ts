type LzoModule = any;

// In Next.js, the wasm asset is emitted to a hashed URL under /_next/static/...
// `lzo-wasm` expects to fetch "lzo-wasm.wasm" relative to its JS, so we must
// provide a locateFile() override pointing at the emitted URL.
import lzoWasmUrl from 'lzo-wasm/lzo-wasm.wasm';

let modulePromise: Promise<LzoModule> | null = null;
let moduleInstance: LzoModule | null = null;
let decompressFn: ((inputPtr: number, inputLength: number, outputLength: number) => number) | null = null;

export async function ensureLzoReady(): Promise<void> {
  if (moduleInstance) return;
  if (!modulePromise) {
    if (typeof window === 'undefined') {
      throw new Error('LZO can only be initialized in the browser');
    }
    modulePromise = (async () => {
      const mod = await import('lzo-wasm/lzo-wasm.js');
      return mod.default({
        locateFile: (path: string) => {
          if (path.endsWith('.wasm')) return lzoWasmUrl;
          return path;
        },
      });
    })();
  }
  moduleInstance = await modulePromise;
  decompressFn = moduleInstance.cwrap('decompress', 'number', ['number', 'number', 'number']);
}

export function lzoDecompressSync(input: Uint8Array, expectedLength: number): Uint8Array {
  if (!moduleInstance || !decompressFn) {
    throw new Error('LZO module not initialized');
  }

  const inputLength = input.length;
  const inputPtr = moduleInstance._malloc(inputLength);
  moduleInstance.HEAPU8.set(input, inputPtr);

  try {
    const outputPtr = decompressFn(inputPtr, inputLength, expectedLength);
    const view = new Uint8Array(moduleInstance.HEAPU8.buffer, outputPtr, expectedLength);
    const copy = new Uint8Array(view);
    moduleInstance._free(outputPtr);
    return copy;
  } finally {
    moduleInstance._free(inputPtr);
  }
}



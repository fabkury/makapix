import { ensureLzoReady, lzoDecompressSync } from './lzo';
import { ensureZstdReady, zstdDecompressSync } from './zstd';
import { decryptAesCbcSync } from './crypto';
import logger from './logger';

type PyodideInterface = any;
type PyProxy = any;

export interface DecodedBean {
  totalFrames: number;
  speed: number;
  rowCount: number;
  columnCount: number;
  webp: Uint8Array;
}

const STUB_MODULES = `
import sys
import types
from js import Uint8Array
import servoom_codecs

class _LZOCompressor:
    def decompress(self, data, output_size):
        buf = Uint8Array.new(data)
        out = servoom_codecs.lzo_decompress(buf, int(output_size))
        return bytes(out.to_py())

lz_module = types.ModuleType("lzallright")
lz_module.LZOCompressor = _LZOCompressor
sys.modules["lzallright"] = lz_module

class _ZstdDecompressor:
    def decompress(self, data):
        buf = Uint8Array.new(data)
        out = servoom_codecs.zstd_decompress(buf)
        return bytes(out.to_py())

zstd_module = types.ModuleType("zstandard")
zstd_module.ZstdDecompressor = _ZstdDecompressor
sys.modules["zstandard"] = zstd_module

class _AESCipher:
    def __init__(self, key, iv):
        self.key = Uint8Array.new(key)
        self.iv = Uint8Array.new(iv)

    def decrypt(self, payload):
        buf = Uint8Array.new(payload)
        out = servoom_codecs.aes_decrypt(buf, self.key, self.iv)
        return bytes(out.to_py())

aescipher_module = types.ModuleType("AES")
aescipher_module.MODE_CBC = 1

def _aes_new(key, mode, iv):
    return _AESCipher(key, iv)

aescipher_module.new = staticmethod(_aes_new)

cipher_module = types.ModuleType("Cipher")
cipher_module.AES = aescipher_module

crypto_module = types.ModuleType("Crypto")
crypto_module.Cipher = cipher_module

sys.modules["Crypto"] = crypto_module
sys.modules["Crypto.Cipher"] = cipher_module
sys.modules["Crypto.Cipher.AES"] = aescipher_module
`;

const BRIDGE_MODULE = `
from io import BytesIO
from pixel_bean_decoder import PixelBeanDecoder

def decode_pixel_bean(raw_bytes: bytes):
    bean = PixelBeanDecoder.decode_stream(BytesIO(raw_bytes))
    webp_buffer = BytesIO()
    bean.save_to_webp(webp_buffer)
    webp_bytes = webp_buffer.getvalue()
    return {
        "total_frames": bean.total_frames,
        "speed": bean.speed,
        "row_count": bean.row_count,
        "column_count": bean.column_count,
        "webp": webp_bytes,
    }
`;

function copyBuffer(view: Uint8Array): Uint8Array {
  const cloned = new Uint8Array(view.length);
  cloned.set(view);
  return cloned;
}

function toPlainUint8Array(source: Uint8Array<ArrayBufferLike>): Uint8Array {
  const clone = new Uint8Array(source.length);
  clone.set(source);
  return clone;
}

function registerCodecBridge(pyodide: PyodideInterface): void {
  const bridge = {
    lzo_decompress(input: Uint8Array, expectedLength: number) {
      return lzoDecompressSync(copyBuffer(input), expectedLength);
    },
    zstd_decompress(input: Uint8Array) {
      return zstdDecompressSync(copyBuffer(input));
    },
    aes_decrypt(payload: Uint8Array, key: Uint8Array, iv: Uint8Array) {
      return decryptAesCbcSync(copyBuffer(payload), copyBuffer(key), copyBuffer(iv));
    },
  };
  pyodide.registerJsModule('servoom_codecs', bridge);
}

async function fetchText(path: string): Promise<string> {
  const resp = await fetch(path);
  if (!resp.ok) throw new Error(`Failed to load ${path} (${resp.status})`);
  return resp.text();
}

async function ensurePyodideLoaded(): Promise<(options: any) => Promise<PyodideInterface>> {
  if (typeof window === 'undefined') {
    throw new Error('Pyodide can only be loaded in the browser');
  }

  const w = window as any;
  if (typeof w.loadPyodide === 'function') {
    return w.loadPyodide.bind(w);
  }

  await new Promise<void>((resolve, reject) => {
    const script = document.createElement('script');
    script.src = 'https://cdn.jsdelivr.net/pyodide/v0.29.0/full/pyodide.js';
    script.async = true;
    // Needed for cross-origin isolation (COEP) compatibility.
    script.crossOrigin = 'anonymous';
    script.onload = () => resolve();
    script.onerror = () => reject(new Error('Failed to load pyodide.js from CDN'));
    document.head.appendChild(script);
  });

  if (typeof w.loadPyodide !== 'function') {
    throw new Error('Pyodide loader was not found after loading script');
  }
  return w.loadPyodide.bind(w);
}

export class PyodideDecoder {
  private pyodide: PyodideInterface | null = null;
  private readyPromise: Promise<void> | null = null;
  private decodeProxy: PyProxy | null = null;

  async ensureReady(): Promise<void> {
    if (!this.pyodide) {
      if (!this.readyPromise) {
        this.readyPromise = this.initialize();
      }
      await this.readyPromise;
    }
  }

  private async initialize(): Promise<void> {
    logger.info('PyodideDecoder: preparing native bridges');
    await Promise.all([ensureLzoReady(), ensureZstdReady()]);
    logger.info('PyodideDecoder: loading Pyodide');
    const loadPyodide = await ensurePyodideLoaded();
    this.pyodide = await loadPyodide({
      indexURL: 'https://cdn.jsdelivr.net/pyodide/v0.29.0/full/',
    });
    registerCodecBridge(this.pyodide);
    await this.pyodide.loadPackage(['numpy', 'pillow']);

    const [pixelBeanSource, pixelDecoderSource] = await Promise.all([
      fetchText('/divoom/python/pixel_bean.py'),
      fetchText('/divoom/python/pixel_bean_decoder.py'),
    ]);

    try {
      this.pyodide.FS.mkdir('/divoom');
    } catch {
      // already exists
    }
    this.pyodide.FS.writeFile('/divoom/pixel_bean.py', pixelBeanSource);
    this.pyodide.FS.writeFile('/divoom/pixel_bean_decoder.py', pixelDecoderSource);
    this.pyodide.FS.writeFile('/divoom/divoom_bridge.py', BRIDGE_MODULE);

    await this.pyodide.runPythonAsync(`
import sys
sys.path.append('/divoom')
`);
    await this.pyodide.runPythonAsync(STUB_MODULES);
    await this.pyodide.runPythonAsync('from divoom_bridge import decode_pixel_bean');
    this.decodeProxy = this.pyodide.globals.get('decode_pixel_bean');
    logger.info('PyodideDecoder: initialization complete');
  }

  async decodeToWebp(data: Uint8Array): Promise<DecodedBean> {
    await this.ensureReady();
    if (!this.pyodide || !this.decodeProxy) {
      throw new Error('Pyodide decoder unavailable');
    }
    logger.info('PyodideDecoder: decoding payload', data.length);
    const pyBytes = this.pyodide.toPy(data);
    try {
      const callable = this.decodeProxy as unknown as (arg: PyProxy) => PyProxy;
      const result = callable(pyBytes);
      const jsResult = result.toJs({ dict_converter: Object.fromEntries, create_pyproxies: false }) as {
        total_frames: number;
        speed: number;
        row_count: number;
        column_count: number;
        webp: Uint8Array<ArrayBufferLike>;
      };
      result.destroy();

      return {
        totalFrames: jsResult.total_frames,
        speed: jsResult.speed,
        rowCount: jsResult.row_count,
        columnCount: jsResult.column_count,
        webp: toPlainUint8Array(jsResult.webp),
      };
    } finally {
      pyBytes.destroy();
    }
  }
}



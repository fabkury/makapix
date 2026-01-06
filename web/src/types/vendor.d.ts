declare module 'spark-md5' {
  const SparkMD5: {
    hash: (value: string) => string;
  };
  export default SparkMD5;
}

declare module 'aes-js' {
  export const ModeOfOperation: any;
}

declare module 'lzo-wasm/lzo-wasm.js' {
  const createModule: (options?: any) => Promise<any>;
  export default createModule;
}

declare module '*.wasm' {
  const url: string;
  export default url;
}

// gifuct-js - GIF decoder
declare module 'gifuct-js' {
  export interface GifFrame {
    dims: {
      width: number;
      height: number;
      left: number;
      top: number;
    };
    patch: ArrayBuffer;
    delay: number;
    disposalType: number;
    transparentIndex?: number;
  }

  export interface ParsedGif {
    lsd: {
      width: number;
      height: number;
    };
    frames: GifFrame[];
  }

  export function parseGIF(buffer: ArrayBuffer): ParsedGif;
  export function decompressFrames(gif: ParsedGif, buildImagePatches: boolean): GifFrame[];
}

// upng-js - PNG decoder
declare module 'upng-js' {
  export interface Image {
    width: number;
    height: number;
    depth: number;
    ctype: number;
    frames: any[];
    tabs: Record<string, any>;
    data: ArrayBuffer;
  }

  export function decode(buffer: ArrayBuffer): Image;
  export function toRGBA8(img: Image): ArrayBuffer[];
  export function encode(
    imgs: ArrayBuffer[],
    w: number,
    h: number,
    cnum: number,
    dels?: number[]
  ): ArrayBuffer;
}

// pica - High quality image resizing
declare module 'pica' {
  export interface PicaOptions {
    quality?: number;
    alpha?: boolean;
    unsharpAmount?: number;
    unsharpRadius?: number;
    unsharpThreshold?: number;
    cancelToken?: any;
  }

  export interface ResizeResult {
    width: number;
    height: number;
  }

  class Pica {
    resize(
      from: HTMLCanvasElement | OffscreenCanvas | ImageBitmap,
      to: HTMLCanvasElement | OffscreenCanvas,
      options?: PicaOptions
    ): Promise<HTMLCanvasElement | OffscreenCanvas>;

    resizeBuffer(options: {
      src: Uint8Array;
      width: number;
      height: number;
      toWidth: number;
      toHeight: number;
      quality?: number;
      alpha?: boolean;
    }): Promise<Uint8Array>;

    toBlob(
      canvas: HTMLCanvasElement | OffscreenCanvas,
      mimeType: string,
      quality?: number
    ): Promise<Blob>;
  }

  export default Pica;
}

// @saschazar/wasm-webp
declare module '@saschazar/wasm-webp' {
  export interface WebPOptions {
    quality: number;
    target_size: number;
    target_PSNR: number;
    method: number;
    sns_strength: number;
    filter_strength: number;
    filter_sharpness: number;
    filter_type: number;
    partitions: number;
    segments: number;
    pass: number;
    show_compressed: number;
    preprocessing: number;
    autofilter: number;
    partition_limit: number;
    alpha_compression: number;
    alpha_filtering: number;
    alpha_quality: number;
    lossless: number;
    exact: number;
    image_hint: number;
    emulate_jpeg_size: number;
    thread_level: number;
    low_memory: number;
    near_lossless: number;
    use_delta_palette: number;
    use_sharp_yuv: number;
  }

  export interface WebPModule {
    encode(
      data: Uint8Array | Uint8ClampedArray,
      width: number,
      height: number,
      channels: number,
      options: WebPOptions
    ): Uint8Array;
    decode(data: Uint8Array, length: number, alpha?: boolean): Uint8Array;
    free(): void;
  }

  export interface ModuleOptions {
    locateFile?: (path: string) => string;
    onRuntimeInitialized?: () => void;
  }

  const createModule: (options?: ModuleOptions) => WebPModule;
  export default createModule;
}



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



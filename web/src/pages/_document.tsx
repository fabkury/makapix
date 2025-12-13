import { Html, Head, Main, NextScript } from 'next/document';

export default function Document() {
  return (
    <Html
      lang="en"
      style={{ backgroundColor: '#0a0a0f' }}
      // In development, some tooling can inject extra attributes into the SSR HTML
      // (e.g. "data-cursor-ref"), which can trigger noisy hydration warnings.
      // We don't want these to obscure real issues during local/dev work.
      suppressHydrationWarning
    >
      <Head>
        {/* Filter hydration warnings caused by dev tooling that injects `data-cursor-ref`
            attributes before React hydrates. This script runs before React/Next boot. */}
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){
  try {
    var origWarn = console.warn;
    var origError = console.error;
    function hasCursorRef(args){
      for (var i=0;i<args.length;i++){
        if (args[i] === 'data-cursor-ref') return true;
        if (typeof args[i] === 'string' && args[i].indexOf('data-cursor-ref') !== -1) return true;
      }
      return false;
    }
    console.warn = function(){
      if (hasCursorRef(arguments)) return;
      return origWarn.apply(console, arguments);
    };
    console.error = function(){
      if (hasCursorRef(arguments)) return;
      return origError.apply(console, arguments);
    };
  } catch (e) {}
})();`,
          }}
        />
        {/* Preconnect to Google Fonts for faster loading */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        {/* Load fonts via link tag instead of CSS @import for better performance */}
        <link
          href="https://fonts.googleapis.com/css2?family=Noto+Sans:ital,wght@0,400;0,500;0,600;0,700;1,400&family=Open+Sans:ital,wght@0,400;0,500;0,600;0,700;1,400&display=swap"
          rel="stylesheet"
        />
      </Head>
      <body style={{ backgroundColor: '#0a0a0f' }} suppressHydrationWarning>
        <Main />
        <NextScript />
      </body>
    </Html>
  );
}


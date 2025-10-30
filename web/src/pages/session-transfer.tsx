import type { GetServerSideProps } from "next";

const SessionTransferPage = () => null;

export default SessionTransferPage;

export const getServerSideProps: GetServerSideProps = async ({ res, query }) => {
  res.setHeader("Cache-Control", "no-store");
  res.setHeader("X-Frame-Options", "SAMEORIGIN");
  res.setHeader(
    "Content-Security-Policy",
    [
      "default-src 'self'",
      "script-src 'self' 'unsafe-inline'",
      "style-src 'self' 'unsafe-inline'",
    ].join("; "),
  );
  res.setHeader("Content-Type", "text/html; charset=utf-8");

  const script = `(() => {
    const STORAGE_KEYS = ['access_token','refresh_token','user_id','user_handle','user_display_name'];
    const params = new URLSearchParams(window.location.search);
    const returnParam = params.get('return');
    const reasonParam = params.get('reason') || '';
    if (!returnParam) {
      const statusEl = document.getElementById('status');
      if (statusEl) statusEl.textContent = 'Missing return URL.';
      return;
    }
    let target;
    try {
      target = new URL(returnParam);
    } catch (urlError) {
      console.error('Makapix session-transfer: invalid return URL', urlError);
      const statusEl = document.getElementById('status');
      if (statusEl) statusEl.textContent = 'Invalid return location.';
      return;
    }
    try {
      const hashParams = new URLSearchParams(target.hash ? target.hash.substring(1) : '');
      if (reasonParam) {
        hashParams.set('makapix_reason', reasonParam);
      }
      const tokens = {};
      STORAGE_KEYS.forEach((key) => {
        const value = window.localStorage.getItem(key);
        if (value) {
          tokens[key] = value;
        }
      });
      if (Object.keys(tokens).length > 0) {
        const json = JSON.stringify(tokens);
        const payload = btoa(encodeURIComponent(json));
        hashParams.set('makapix_session', payload);
        hashParams.delete('makapix_session_error');
      } else {
        hashParams.set('makapix_session_error', 'missing_tokens');
        hashParams.delete('makapix_session');
      }
      const newHash = hashParams.toString();
      target.hash = newHash ? ('#' + newHash) : '';
      window.location.replace(target.toString());
    } catch (error) {
      console.error('Makapix session-transfer failed', error);
      try {
        const fallback = new URL(returnParam);
        const fallbackParams = new URLSearchParams(fallback.hash ? fallback.hash.substring(1) : '');
        fallbackParams.set('makapix_session_error', 'transfer_failed');
        fallbackParams.delete('makapix_session');
        fallback.hash = fallbackParams.toString() ? ('#' + fallbackParams.toString()) : '';
        window.location.replace(fallback.toString());
      } catch (secondaryError) {
        console.error('Makapix session-transfer fallback failed', secondaryError);
        const statusEl = document.getElementById('status');
        if (statusEl) statusEl.textContent = 'Unable to sync session. You can close this tab.';
      }
    }
  })();`;

  const html = `<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charSet="utf-8" />
    <title>Makapix Session Transfer</title>
    <style>
      body { font-family: system-ui, sans-serif; text-align: center; padding: 2rem; color: #4b5563; }
    </style>
  </head>
  <body>
    <div id="status">Syncing your Makapix session…</div>
    <script>${script.replace(/<\//g, '<\\/')}</script>
  </body>
</html>`;

  res.write(html);
  res.end();

  return { props: {} };
};


"""Branded, self-contained HTML pages for the GitHub OAuth popup flow.

Served by the auth router on the web-flow paths of /auth/github/login and
/auth/github/callback. Everything is inline — styles, script, SVG branding —
because the API's CSP (the SecurityHeadersMiddleware header and the meta tag
below) blocks external resource fetches.

Dynamic markup text goes through html.escape(); values embedded in the
inline <script> go through _js() (json.dumps + ``</`` escaping).
"""

import html
import json

# Inline script and style are the only capabilities these pages need.
_META_CSP = "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'"


def _js(value) -> str:
    """JSON-encode a value for safe embedding inside an inline <script>."""
    return json.dumps(value).replace("</", "<\\/")


# Palette and component styles mirror web/src/styles/globals.css and the
# auth card in web/src/components/AuthPanel.tsx.
_STYLE = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: 'Noto Sans', 'Open Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: #000000;
  color: #e8e8f0;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 24px;
  text-align: center;
}
.card {
  width: 100%;
  max-width: 380px;
  background: #12121a;
  border-radius: 16px;
  padding: 32px;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.pixel-mark { margin-bottom: 12px; }
.wordmark {
  font-size: 1.25rem;
  font-weight: 700;
  text-shadow: 0 0 12px rgba(255, 110, 180, 0.6);
  margin-bottom: 28px;
}
.wordmark span { color: #ff6eb4; }
.state {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid #1a1a24;
  border-top-color: #00d4ff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin-bottom: 16px;
}
@keyframes spin { to { transform: rotate(360deg); } }
.headline { font-size: 1.05rem; font-weight: 600; }
.sub { color: #a0a0b8; font-size: 0.9rem; margin-top: 8px; }
.button {
  display: inline-block;
  margin-top: 24px;
  padding: 14px 28px;
  background: linear-gradient(135deg, #ff6eb4, #b44eff);
  color: white;
  font-size: 1rem;
  font-weight: 600;
  border-radius: 10px;
  text-decoration: none;
  transition: all 0.15s ease;
}
.button:hover {
  box-shadow: 0 0 20px rgba(255, 110, 180, 0.4);
  transform: translateY(-1px);
}
[hidden] { display: none !important; }
"""

# Pixel-art heart in the site's accent ramp (pink → purple → blue → cyan).
_BRAND_HTML = """
<svg class="pixel-mark" width="56" height="48" viewBox="0 0 7 6" shape-rendering="crispEdges" role="img" aria-label="Makapix Club">
  <rect x="1" y="0" width="2" height="1" fill="#ff6eb4"/>
  <rect x="4" y="0" width="2" height="1" fill="#ff6eb4"/>
  <rect x="0" y="1" width="7" height="1" fill="#ff6eb4"/>
  <rect x="0" y="2" width="7" height="1" fill="#b44eff"/>
  <rect x="1" y="3" width="5" height="1" fill="#4e9fff"/>
  <rect x="2" y="4" width="3" height="1" fill="#00d4ff"/>
  <rect x="3" y="5" width="1" height="1" fill="#00d4ff"/>
</svg>
<div class="wordmark">Makapix <span>Club</span></div>
"""

# Expects AUTH, REDIRECT_URL and SITE_ORIGIN consts to be defined above it.
# The refresh token travels in an HttpOnly cookie, never through this script.
_SUCCESS_SCRIPT = """
try {
  localStorage.setItem('access_token', AUTH.access_token);
  localStorage.setItem('user_id', AUTH.user_id);
  localStorage.setItem('user_handle', AUTH.user_handle);
} catch (error) {
  console.error('Error storing tokens:', error);
}

function showSuccessFallback() {
  document.getElementById('state-signing').hidden = true;
  document.getElementById('state-success').hidden = false;
}

try {
  if (window.opener) {
    window.opener.postMessage(
      { type: 'OAUTH_SUCCESS', tokens: AUTH, redirectUrl: REDIRECT_URL },
      SITE_ORIGIN
    );
    window.close();
    // If a popup blocker refused the close, offer a manual way forward.
    setTimeout(showSuccessFallback, 1800);
  } else {
    // Not a popup — redirect this window.
    window.location.href = REDIRECT_URL;
  }
} catch (error) {
  console.error('Error finalizing OAuth flow:', error);
  if (window.opener) {
    try {
      window.close();
      setTimeout(showSuccessFallback, 1800);
    } catch (closeError) {
      window.location.href = REDIRECT_URL;
    }
  } else {
    window.location.href = REDIRECT_URL;
  }
}
"""


def _page_shell(title: str, body: str, script: str = "") -> str:
    script_tag = f"<script>{script}</script>" if script else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{_META_CSP}">
<title>{html.escape(title)}</title>
<style>{_STYLE}</style>
</head>
<body>
<div class="card">
{_BRAND_HTML}
{body}
</div>
{script_tag}
</body>
</html>
"""


def oauth_success_page(
    *,
    access_token: str,
    user_id: str,
    user_handle: str,
    needs_welcome: bool,
    site_origin: str,
    redirect_url: str,
) -> str:
    """Popup landing page: transient "Signing you in…" that hands tokens to
    the opener and closes itself; a manual success state appears only if the
    window survives (popup blocker, or opened as a plain tab)."""
    body = f"""<div id="state-signing" class="state">
  <div class="spinner"></div>
  <p class="headline">Signing you in&hellip;</p>
</div>
<div id="state-success" class="state" hidden>
  <p class="headline">You're signed in!</p>
  <p class="sub">This window can be closed.</p>
  <a class="button" href="{html.escape(redirect_url)}">Go to Makapix</a>
</div>"""
    auth_data = {
        "access_token": access_token,
        "user_id": user_id,
        "user_handle": user_handle,
        "needs_welcome": needs_welcome,
    }
    script = (
        f"const AUTH = {_js(auth_data)};\n"
        f"const REDIRECT_URL = {_js(redirect_url)};\n"
        f"const SITE_ORIGIN = {_js(site_origin)};\n"
        f"{_SUCCESS_SCRIPT}"
    )
    return _page_shell("Makapix Club - Signing you in", body, script)


def oauth_error_page(detail: str) -> str:
    """Branded error page for web-flow OAuth failures (no script, no state)."""
    body = f"""<div class="state">
  <p class="headline">Sign-in didn't work</p>
  <p class="sub">{html.escape(detail)}</p>
  <p class="sub">Please close this window and try signing in again.</p>
</div>"""
    return _page_shell("Makapix Club - Sign-in error", body)

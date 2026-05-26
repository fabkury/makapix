#!/usr/bin/env python3
"""
Reference example for the Makapix HTTPS player API — end to end.

This is the worked example linked from the player developer guide
(docs/player/https-connection.md): a minimal, runnable demonstration of how a
device connects to MPX over HTTPS. Read it alongside that doc when porting the
protocol to your own player.

What it does:
  1. Provisions a player (with your help: you enter the shown code in the
     Makapix web app), then polls for credentials and captures the device
     bearer token.
  2. Stores the token (and player_key) locally so later runs skip provisioning.
  3. Queries posts over the HTTPS player API (POST /player/rpc).
  4. Downloads a few of the returned artworks to a local folder.

No third-party packages required — standard library only. Run with:

    python3 test_https_player_api.py
    python3 test_https_player_api.py --channel all --limit 20 --download 5
    python3 test_https_player_api.py --reset        # forget creds, provision anew

The bearer token is a credential — the creds file is written with 0600
permissions. Treat it like a password.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_BASE_URL = "https://makapix.club/api"
DEFAULT_CREDS_FILE = Path.home() / ".mpx_player_creds.json"

DEVICE_MODEL = "https-test-script"
FIRMWARE_VERSION = "0.1.0"

POLL_INTERVAL_S = 5
POLL_TIMEOUT_S = 15 * 60  # registration code is valid for 15 minutes


# ---------------------------------------------------------------------------
# Tiny HTTP helpers (stdlib only)
# ---------------------------------------------------------------------------


def request_json(
    method: str,
    url: str,
    *,
    body: dict | None = None,
    token: str | None = None,
    timeout: int = 20,
) -> tuple[int, dict]:
    """Make a JSON request. Returns (status_code, parsed_body).

    Never raises on HTTP error statuses — the status is returned so the caller
    can branch on it. Raises only on network-level failures.
    """
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8") or "{}"
            return resp.status, json.loads(raw)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {"raw": raw}
        return e.code, parsed


def download(url: str, dest: Path, timeout: int = 30) -> int:
    """Download a URL to a file. Returns the number of bytes written."""
    req = urllib.request.Request(url, headers={"User-Agent": "mpx-test-script"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = resp.read()
    dest.write_bytes(payload)
    return len(payload)


# ---------------------------------------------------------------------------
# Credential storage
# ---------------------------------------------------------------------------


def load_creds(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def save_creds(path: Path, creds: dict) -> None:
    path.write_text(json.dumps(creds, indent=2))
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    print(f"  saved credentials to {path} (mode 600)")


# ---------------------------------------------------------------------------
# Provisioning
# ---------------------------------------------------------------------------


def provision(base_url: str) -> dict:
    """Provision a new player and walk the user through linking it."""
    print("\n== Provisioning a new player ==")
    status, body = request_json(
        "POST",
        f"{base_url}/player/provision",
        body={"device_model": DEVICE_MODEL, "firmware_version": FIRMWARE_VERSION},
    )
    if status != 201:
        sys.exit(f"Provision failed (HTTP {status}): {body}")

    player_key = body["player_key"]
    code = body["registration_code"]
    expires = body.get("registration_code_expires_at", "soon")
    https_api = body.get("https_api") or {}
    api_base = https_api.get("base_url", base_url)

    print(f"  player_key: {player_key}")
    print("\n  ┌──────────────────────────────────────────────┐")
    print(f"  │  Registration code:   {code:<24}│")
    print("  └──────────────────────────────────────────────┘")
    web = urlparse(base_url)
    site = f"{web.scheme}://{web.netloc}"
    print(f"\n  In the Makapix web app ({site}):")
    print("    1. Log in")
    print("    2. Go to Settings → Players → Add Device")
    print(f"    3. Enter the code above ({code}) and name the device")
    print(f"\n  The code expires at {expires} (~15 minutes).")
    print("\n  Waiting for you to link the device", end="", flush=True)

    deadline = time.time() + POLL_TIMEOUT_S
    api_token = None
    while time.time() < deadline:
        time.sleep(POLL_INTERVAL_S)
        print(".", end="", flush=True)
        st, cred = request_json("GET", f"{base_url}/player/{player_key}/credentials")
        if st == 200:
            api_token = cred.get("api_token")
            api_base = (cred.get("https_api") or {}).get("base_url", api_base)
            print("  linked!")
            break
        if st == 429:
            time.sleep(POLL_INTERVAL_S * 2)  # rate limited; back off
        # 404 = not registered yet; keep polling
    else:
        sys.exit("\nTimed out waiting for registration. Re-run to try again.")

    # The token is minted once, on the first credentials fetch. If for any
    # reason it wasn't returned, rotate to obtain one.
    if not api_token:
        print("  no token in credentials response; rotating one...")
        api_token = rotate_token(base_url, player_key)

    print(f"  device token: {api_token[:16]}… (stored)")
    return {"base_url": api_base, "player_key": player_key, "api_token": api_token}


def rotate_token(base_url: str, player_key: str) -> str:
    """Get a fresh device token using the player_key (revokes the old one)."""
    st, body = request_json("POST", f"{base_url}/player/{player_key}/token/rotate")
    if st != 200 or not body.get("api_token"):
        sys.exit(
            f"Token rotation failed (HTTP {st}): {body}\n"
            "The player may have been removed — re-run with --reset to provision anew."
        )
    return body["api_token"]


# ---------------------------------------------------------------------------
# Player RPC: query + download
# ---------------------------------------------------------------------------

INCLUDE_FIELDS = ["owner_handle", "width", "height", "frame_count"]


def query_posts(creds: dict, channel: str, limit: int, extra: dict) -> dict:
    """Call POST /player/rpc with request_type=query_posts.

    Auto-rotates the token once on 401, then retries.
    """
    base_url = creds["base_url"]
    body = {
        "request_type": "query_posts",
        "channel": channel,
        "limit": limit,
        "include_fields": INCLUDE_FIELDS,
        **extra,
    }

    st, resp = request_json(
        "POST", f"{base_url}/player/rpc", body=body, token=creds["api_token"]
    )
    if st == 401:
        print("  token rejected (401) — rotating a fresh one and retrying...")
        creds["api_token"] = rotate_token(base_url, creds["player_key"])
        save_creds(Path(creds["_path"]), {k: v for k, v in creds.items() if k != "_path"})
        st, resp = request_json(
            "POST", f"{base_url}/player/rpc", body=body, token=creds["api_token"]
        )

    if st != 200 or not resp.get("success"):
        sys.exit(f"query_posts failed (HTTP {st}): {resp}")
    return resp


def download_artworks(base_url: str, posts: list[dict], count: int, out_dir: Path):
    """Download up to `count` artwork posts (playlists have no image)."""
    artworks = [p for p in posts if p.get("kind") == "artwork"][:count]
    if not artworks:
        print("  (no artworks to download in this result)")
        return

    out_dir.mkdir(parents=True, exist_ok=True)
    root = "{u.scheme}://{u.netloc}".format(u=urlparse(base_url))

    print(f"\n== Downloading {len(artworks)} artwork(s) to {out_dir} ==")
    for p in artworks:
        art_url = p.get("art_url") or ""
        if not art_url:
            continue
        # art_url may be absolute or root-relative (e.g. /api/vault/...).
        full = art_url if art_url.startswith("http") else root + art_url
        ext = (p.get("native_format") or full.rsplit(".", 1)[-1] or "bin").lower()
        dest = out_dir / f"{p['post_id']}_{p['storage_key']}.{ext}"
        try:
            n = download(full, dest)
            print(f"  post {p['post_id']:>8}  {n:>8} bytes  -> {dest.name}")
        except (urllib.error.URLError, OSError) as e:
            print(f"  post {p['post_id']:>8}  FAILED: {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def print_posts(posts: list[dict]) -> None:
    print(f"\n== Query returned {len(posts)} post(s) ==")
    for p in posts:
        if p.get("kind") == "artwork":
            dims = f"{p.get('width', '?')}x{p.get('height', '?')}"
            frames = p.get("frame_count")
            anim = f" {frames}f" if frames and frames > 1 else ""
            owner = p.get("owner_handle", "?")
            print(
                f"  #{p['post_id']:<8} artwork  {dims:<9}{anim:<4} "
                f"{p.get('native_format', '?'):<5} @{owner}"
            )
        else:
            print(f"  #{p['post_id']:<8} {p.get('kind', '?')}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="API base URL")
    parser.add_argument(
        "--creds-file", default=str(DEFAULT_CREDS_FILE), help="where to store the token"
    )
    parser.add_argument(
        "--channel",
        default="all",
        help="all | promoted | user | by_user | hashtag | reactions",
    )
    parser.add_argument("--user-handle", help="for --channel by_user/reactions")
    parser.add_argument("--hashtag", help="for --channel hashtag (no '#')")
    parser.add_argument("--limit", type=int, default=10, help="posts to query (1-50)")
    parser.add_argument("--download", type=int, default=3, help="artworks to download")
    parser.add_argument("--out", default="./mpx_downloads", help="download folder")
    parser.add_argument("--reset", action="store_true", help="forget stored creds")
    args = parser.parse_args()

    creds_path = Path(args.creds_file).expanduser()
    if args.reset and creds_path.exists():
        creds_path.unlink()
        print(f"Removed {creds_path}")

    creds = load_creds(creds_path)
    if creds and creds.get("api_token"):
        print(f"Using stored player {creds['player_key']} ({creds_path})")
    else:
        creds = provision(args.base_url)
        save_creds(creds_path, creds)

    # Pass the creds-file path through so query_posts can persist a rotated token.
    creds["_path"] = str(creds_path)

    extra = {}
    if args.user_handle:
        extra["user_handle"] = args.user_handle
    if args.hashtag:
        extra["hashtag"] = args.hashtag

    print(f"\n== Querying posts (channel={args.channel}, limit={args.limit}) ==")
    result = query_posts(creds, args.channel, args.limit, extra)
    posts = result.get("posts", [])
    print_posts(posts)
    if result.get("has_more"):
        print(f"  (more available; next_cursor={result.get('next_cursor')})")

    download_artworks(creds["base_url"], posts, args.download, Path(args.out).expanduser())
    print("\nDone.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\nAborted.")

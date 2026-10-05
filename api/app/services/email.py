"""Email service using Resend for sending transactional emails."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from html import escape
from typing import Any

import resend

from .email_copy import copy_for

logger = logging.getLogger(__name__)

# Resend configuration from environment
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "noreply@notification.makapix.club")
BASE_URL = os.getenv("BASE_URL", "http://localhost")


def _init_resend() -> bool:
    """Initialize Resend API key. Returns True if configured."""
    if not RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not configured - email sending disabled")
        return False
    resend.api_key = RESEND_API_KEY
    return True


def _greeting(strings: dict[str, str], handle: str | None) -> str:
    if handle:
        return strings["greeting_named"].format(handle=handle)
    return strings["greeting_anonymous"]


def _layout_html(lang: str, paragraphs_html: str, footer: str) -> str:
    """The shared shell: single cyan accent on gray (site palette), no images."""
    return f"""<!DOCTYPE html>
<html lang="{escape(lang)}">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:24px;background:#f2f2f2;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;line-height:1.6;color:#222;">
  <div style="max-width:560px;margin:0 auto;background:#fff;border-top:4px solid #00d4ff;border-radius:8px;padding:28px;">
{paragraphs_html}
  </div>
  <p style="max-width:560px;margin:16px auto 0;text-align:center;color:#888;font-size:12px;">{escape(footer)}</p>
</body>
</html>
"""


def _otp_message(
    locale: str | None, handle: str | None, code: str, kind: str
) -> tuple[str, str, str]:
    """(subject, html, text) for a verification ("verify") or reset ("reset") code."""
    strings = copy_for(locale)
    greeting = _greeting(strings, handle)
    intro = strings[f"{kind}_intro"]
    expiry = strings["code_expiry"]
    ignore = strings[f"{kind}_ignore"]
    html = _layout_html(
        locale or "en",
        f"""    <p>{escape(greeting)}</p>
    <p>{escape(intro)}</p>
    <p style="font-family:monospace;font-size:32px;font-weight:bold;letter-spacing:6px;margin:20px 0;">{escape(code)}</p>
    <p>{escape(expiry)}</p>
    <p style="color:#666;font-size:14px;">{escape(ignore)}</p>""",
        strings["footer"],
    )
    text = f"{greeting}\n\n{intro}\n\n{code}\n\n{expiry}\n\n{ignore}\n\n-- \n{strings['footer']}\n"
    return strings[f"{kind}_subject"], html, text


def send_verification_otp_email(
    to_email: str, code: str, handle: str | None = None, locale: str | None = None
) -> dict[str, Any] | None:
    """Send a short numeric email-verification OTP (native client flow, §3.4)."""
    if not _init_resend():
        logger.info(
            f"Email sending disabled - would send verification OTP to {to_email}"
        )
        return None
    subject, html, text = _otp_message(locale, handle, code, "verify")
    try:
        return resend.Emails.send(
            {
                "from": RESEND_FROM_EMAIL,
                "to": [to_email],
                "subject": subject,
                "html": html,
                "text": text,
            }
        )
    except Exception as e:  # pragma: no cover - network
        logger.error(f"Failed to send verification OTP email: {e}")
        return None


def send_password_reset_otp_email(
    to_email: str, code: str, handle: str | None = None, locale: str | None = None
) -> dict[str, Any] | None:
    """Send a short numeric password-reset OTP (native client flow, §3.4)."""
    if not _init_resend():
        logger.info(
            f"Email sending disabled - would send password reset OTP to {to_email}"
        )
        return None
    subject, html, text = _otp_message(locale, handle, code, "reset")
    try:
        return resend.Emails.send(
            {
                "from": RESEND_FROM_EMAIL,
                "to": [to_email],
                "subject": subject,
                "html": html,
                "text": text,
            }
        )
    except Exception as e:  # pragma: no cover - network
        logger.error(f"Failed to send password reset OTP email: {e}")
        return None


def send_verification_email(
    to_email: str,
    token: str,
    handle: str | None = None,
    password: str | None = None,
) -> dict[str, Any] | None:
    """
    Send email verification email to a user.

    Args:
        to_email: The recipient's email address
        token: The verification token (plain, not hashed)
        handle: User's handle for personalization
        password: Optional generated password to include in the email

    Returns:
        Resend API response if successful, None if email sending is disabled or fails
    """
    if not _init_resend():
        logger.info(f"Email sending disabled - would send verification to {to_email}")
        return None

    verification_url = f"{BASE_URL}/verify-email?token={token}"
    greeting = f"Hi {handle}!" if handle else "Hi there!"

    # Build credentials section if password is provided
    credentials_html = ""
    credentials_text = ""
    if password:
        credentials_html = f"""
        <div style="background: #fff; border: 2px solid #667eea; border-radius: 8px; padding: 20px; margin: 20px 0;">
            <h3 style="margin: 0 0 15px 0; color: #667eea;">Your Login Credentials</h3>
            <p style="margin: 5px 0;"><strong>Email:</strong> {to_email}</p>
            <p style="margin: 5px 0;"><strong>Password:</strong> <code style="background: #f0f0f0; padding: 3px 8px; border-radius: 4px; font-family: monospace;">{password}</code></p>
            <p style="margin: 15px 0 0 0; color: #666; font-size: 13px;">
                💡 You can change your password and handle after verifying your email.
            </p>
        </div>
        """
        credentials_text = f"""
Your Login Credentials:
- Email: {to_email}
- Password: {password}

You can change your password and handle after verifying your email.
"""

    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Verify your Makapix Club email</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 10px 10px 0 0; text-align: center;">
        <h1 style="color: white; margin: 0; font-size: 24px;">🎨 Makapix Club</h1>
    </div>
    
    <div style="background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px;">
        <p style="margin-top: 0; font-size: 18px;">{greeting}</p>
        
        <p>Welcome to Makapix Club! Please verify your email address to complete your registration.</p>
        
        {credentials_html}
        
        <div style="text-align: center; margin: 30px 0;">
            <a href="{verification_url}" 
               style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                      color: white; 
                      text-decoration: none; 
                      padding: 15px 30px; 
                      border-radius: 5px; 
                      font-weight: bold;
                      display: inline-block;">
                Verify Email Address
            </a>
        </div>
        
        <p style="color: #666; font-size: 14px;">
            If the button doesn't work, copy and paste this link into your browser:
        </p>
        <p style="color: #666; font-size: 12px; word-break: break-all;">
            <a href="{verification_url}" style="color: #667eea;">{verification_url}</a>
        </p>
        
        <hr style="border: none; border-top: 1px solid #ddd; margin: 25px 0;">
        
        <p style="color: #999; font-size: 12px; margin-bottom: 0;">
            This verification link will expire in 24 hours.<br>
            If you didn't create an account on Makapix Club, you can safely ignore this email.
        </p>
    </div>
    
    <div style="text-align: center; padding: 20px; color: #999; font-size: 12px;">
        <p>© 2025 Makapix Club. Share your pixel art with the world.</p>
    </div>
</body>
</html>
"""

    text_content = f"""{greeting}

Welcome to Makapix Club! Please verify your email address to complete your registration.

{credentials_text}

Click the link below to verify your email:
{verification_url}

This verification link will expire in 24 hours.

If you didn't create an account on Makapix Club, you can safely ignore this email.

---
© 2025 Makapix Club. Share your pixel art with the world.
"""

    try:
        params: resend.Emails.SendParams = {
            "from": RESEND_FROM_EMAIL,
            "to": [to_email],
            "subject": "Verify your Makapix Club email",
            "html": html_content,
            "text": text_content,
        }

        response = resend.Emails.send(params)
        logger.info(
            f"Verification email sent to {to_email}, id: {response.get('id', 'unknown')}"
        )
        return response
    except Exception as e:
        logger.error(f"Failed to send verification email to {to_email}: {e}")
        return None


def send_password_reset_email(
    to_email: str, token: str, handle: str | None = None
) -> dict[str, Any] | None:
    """
    Send password reset email to a user.

    Args:
        to_email: The recipient's email address
        token: The reset token (plain, not hashed)
        handle: Optional handle for personalization

    Returns:
        Resend API response if successful, None if email sending is disabled or fails
    """
    if not _init_resend():
        logger.info(f"Email sending disabled - would send password reset to {to_email}")
        return None

    reset_url = f"{BASE_URL}/reset-password?token={token}"
    greeting = f"Hi {handle}!" if handle else "Hi there!"

    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reset your Makapix Club password</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 10px 10px 0 0; text-align: center;">
        <h1 style="color: white; margin: 0; font-size: 24px;">🎨 Makapix Club</h1>
    </div>
    
    <div style="background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px;">
        <p style="margin-top: 0;">{greeting}</p>
        
        <p>We received a request to reset your password for your Makapix Club account.</p>
        
        <div style="text-align: center; margin: 30px 0;">
            <a href="{reset_url}" 
               style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                      color: white; 
                      text-decoration: none; 
                      padding: 15px 30px; 
                      border-radius: 5px; 
                      font-weight: bold;
                      display: inline-block;">
                Reset Password
            </a>
        </div>
        
        <p style="color: #666; font-size: 14px;">
            If the button doesn't work, copy and paste this link into your browser:
        </p>
        <p style="color: #666; font-size: 12px; word-break: break-all;">
            <a href="{reset_url}" style="color: #667eea;">{reset_url}</a>
        </p>
        
        <hr style="border: none; border-top: 1px solid #ddd; margin: 25px 0;">
        
        <p style="color: #999; font-size: 12px; margin-bottom: 0;">
            This reset link will expire in 1 hour.<br>
            If you didn't request a password reset, you can safely ignore this email.
        </p>
    </div>
    
    <div style="text-align: center; padding: 20px; color: #999; font-size: 12px;">
        <p>© 2025 Makapix Club. Share your pixel art with the world.</p>
    </div>
</body>
</html>
"""

    text_content = f"""{greeting}

We received a request to reset your password for your Makapix Club account.

Click the link below to reset your password:
{reset_url}

This reset link will expire in 1 hour.

If you didn't request a password reset, you can safely ignore this email.

---
© 2025 Makapix Club. Share your pixel art with the world.
"""

    try:
        params: resend.Emails.SendParams = {
            "from": RESEND_FROM_EMAIL,
            "to": [to_email],
            "subject": "Reset your Makapix Club password",
            "html": html_content,
            "text": text_content,
        }

        response = resend.Emails.send(params)
        logger.info(
            f"Password reset email sent to {to_email}, id: {response.get('id', 'unknown')}"
        )
        return response
    except Exception as e:
        logger.error(f"Failed to send password reset email to {to_email}: {e}")
        return None


def send_bdr_ready_email(
    to_email: str,
    handle: str | None,
    artwork_count: int,
    download_url: str,
    expires_at: datetime,
    locale: str | None = None,
) -> dict[str, Any] | None:
    """
    Send email notification when a Batch Download Request is ready.

    Args:
        to_email: Recipient's email address
        handle: User's handle for personalization
        artwork_count: Number of artworks in the download
        download_url: Full URL to access the download
        expires_at: When the download link expires
        locale: The user's stored locale (None = English)

    Returns:
        Resend API response if successful, None if email sending is disabled or fails
    """
    if not _init_resend():
        logger.info(f"Email sending disabled - would send BDR ready to {to_email}")
        return None

    strings = copy_for(locale)
    greeting = _greeting(strings, handle)
    ready = strings["bdr_ready"]
    count = strings["bdr_count"].format(count=artwork_count)
    # Numeric on purpose: nothing for translators to inflect (D7).
    expiry = strings["bdr_expiry"].format(
        expires=expires_at.strftime("%Y-%m-%d %H:%M UTC")
    )
    fallback = strings["bdr_fallback_link"]
    why = strings["bdr_why"]
    url = escape(download_url)

    html_content = _layout_html(
        locale or "en",
        f"""    <p>{escape(greeting)}</p>
    <p>{escape(ready)}<br>{escape(count)}</p>
    <p style="text-align:center;margin:28px 0;">
      <a href="{url}" style="background:#00d4ff;color:#111;text-decoration:none;padding:12px 28px;border-radius:6px;font-weight:bold;display:inline-block;">{escape(strings["bdr_button"])}</a>
    </p>
    <p>{escape(expiry)}</p>
    <p style="color:#666;font-size:14px;">{escape(fallback)}<br><a href="{url}" style="color:#0090b0;word-break:break-all;">{url}</a></p>
    <hr style="border:none;border-top:1px solid #ddd;margin:24px 0;">
    <p style="color:#888;font-size:12px;margin-bottom:0;">{escape(why)}</p>""",
        strings["footer"],
    )
    text_content = (
        f"{greeting}\n\n{ready}\n{count}\n\n{download_url}\n\n{expiry}\n\n"
        f"-- \n{why}\n{strings['footer']}\n"
    )

    try:
        params: resend.Emails.SendParams = {
            "from": RESEND_FROM_EMAIL,
            "to": [to_email],
            "subject": strings["bdr_subject"],
            "html": html_content,
            "text": text_content,
        }

        response = resend.Emails.send(params)
        logger.info(
            f"BDR ready email sent to {to_email}, id: {response.get('id', 'unknown')}"
        )
        return response
    except Exception as e:
        logger.error(f"Failed to send BDR ready email to {to_email}: {e}")
        return None


def send_report_alert_email(
    target_type: str,
    target_id: str,
    reason_code: str,
    notes: str | None,
    reporter_handle: str | None,
    post_public_sqid: str | None = None,
) -> dict[str, Any] | None:
    """
    Alert the moderation inbox about a new content report (docs/ugc-safety/ D4).

    `post_public_sqid` is the reported post (or a reported comment's parent
    post) so the link is the canonical /p/ URL.

    Throttled by the caller (one email per target per 6 h, D18). Failures are
    logged and swallowed — reporting must never fail because email did.
    """
    if not _init_resend():
        logger.info("Email sending disabled - would send report alert")
        return None

    import html as html_lib

    to_email = os.getenv("MODERATION_ALERT_EMAIL", "acme@makapix.club")
    # Reporter handle, notes, and target_id are user-controlled — escape them
    # before interpolating into the HTML body.
    reporter = html_lib.escape(reporter_handle or "anonymous")
    notes_str = (notes or "").strip()
    if len(notes_str) > 500:
        notes_str = notes_str[:500] + "…"
    notes_str = html_lib.escape(notes_str)
    target_id = html_lib.escape(target_id)

    if post_public_sqid:
        target_url = f"{BASE_URL}/p/{html_lib.escape(post_public_sqid)}"
    elif target_type == "post":
        target_url = f"{BASE_URL}/post/{target_id}"
    elif target_type == "user":
        target_url = f"{BASE_URL}/u/{target_id}"
    else:
        target_url = f"{BASE_URL}/mod-dashboard"

    text_content = f"""New content report on Makapix Club

Target:   {target_type} {target_id}
          {target_url}
Reason:   {reason_code}
Reporter: {reporter}
Notes:    {notes_str or "(none)"}

Review it in the moderation queue: {BASE_URL}/mod-dashboard
(Further reports on this target are muted for 6 hours.)
"""

    html_content = (
        f"<p><strong>New content report on Makapix Club</strong></p>"
        f"<ul>"
        f"<li>Target: {target_type} <a href='{target_url}'>{target_id}</a></li>"
        f"<li>Reason: <code>{reason_code}</code></li>"
        f"<li>Reporter: {reporter}</li>"
        f"</ul>"
        f"<p>Notes: {notes_str or '(none)'}</p>"
        f"<p><a href='{BASE_URL}/mod-dashboard'>Open the moderation queue</a></p>"
        f"<p style='color:#666'>Further reports on this target are muted for 6 hours.</p>"
    )

    try:
        params: resend.Emails.SendParams = {
            "from": RESEND_FROM_EMAIL,
            "to": [to_email],
            "subject": f"[MPX report] {target_type} {target_id}: {reason_code}",
            "html": html_content,
            "text": text_content,
        }
        response = resend.Emails.send(params)
        logger.info(
            f"Report alert email sent to {to_email}, id: {response.get('id', 'unknown')}"
        )
        return response
    except Exception as e:
        logger.error(f"Failed to send report alert email: {e}")
        return None

"""Email service using Resend for sending transactional emails."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any

import resend

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
        logger.info(f"Verification email sent to {to_email}, id: {response.get('id', 'unknown')}")
        return response
    except Exception as e:
        logger.error(f"Failed to send verification email to {to_email}: {e}")
        return None


def send_password_reset_email(to_email: str, token: str, handle: str | None = None) -> dict[str, Any] | None:
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
        logger.info(f"Password reset email sent to {to_email}, id: {response.get('id', 'unknown')}")
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
) -> dict[str, Any] | None:
    """
    Send email notification when a Batch Download Request is ready.

    Args:
        to_email: Recipient's email address
        handle: User's handle for personalization
        artwork_count: Number of artworks in the download
        download_url: Full URL to access the download
        expires_at: When the download link expires

    Returns:
        Resend API response if successful, None if email sending is disabled or fails
    """
    if not _init_resend():
        logger.info(f"Email sending disabled - would send BDR ready to {to_email}")
        return None

    greeting = f"Hi {handle}!" if handle else "Hi there!"

    # Format expiration date nicely
    expires_str = expires_at.strftime("%B %d, %Y at %I:%M %p UTC")

    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Your Makapix download is ready!</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 10px 10px 0 0; text-align: center;">
        <h1 style="color: white; margin: 0; font-size: 24px;">🎨 Your Download is Ready!</h1>
    </div>

    <div style="background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px;">
        <p style="margin-top: 0; font-size: 18px;">{greeting}</p>

        <p>Great news! Your batch download containing <strong>{artwork_count} artwork{"s" if artwork_count != 1 else ""}</strong> is ready.</p>

        <div style="text-align: center; margin: 30px 0;">
            <a href="{download_url}"
               style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                      color: white;
                      text-decoration: none;
                      padding: 15px 30px;
                      border-radius: 5px;
                      font-weight: bold;
                      display: inline-block;">
                📦 Download Your Artworks
            </a>
        </div>

        <div style="background: #fff3cd; border: 1px solid #ffc107; border-radius: 8px; padding: 15px; margin: 20px 0;">
            <p style="margin: 0; color: #856404;">
                <strong>⏰ Important:</strong> This download link will expire on <strong>{expires_str}</strong>.
                Make sure to download your artworks before then!
            </p>
        </div>

        <p style="color: #666; font-size: 14px;">
            If the button doesn't work, copy and paste this link into your browser:
        </p>
        <p style="color: #666; font-size: 12px; word-break: break-all;">
            <a href="{download_url}" style="color: #667eea;">{download_url}</a>
        </p>

        <hr style="border: none; border-top: 1px solid #ddd; margin: 25px 0;">

        <p style="color: #999; font-size: 12px; margin-bottom: 0;">
            You're receiving this email because you requested a batch download on Makapix Club.<br>
            If you didn't request this download, you can safely ignore this email.
        </p>
    </div>

    <div style="text-align: center; padding: 20px; color: #999; font-size: 12px;">
        <p>© 2025 Makapix Club. Share your pixel art with the world.</p>
    </div>
</body>
</html>
"""

    text_content = f"""{greeting}

Great news! Your batch download containing {artwork_count} artwork{"s" if artwork_count != 1 else ""} is ready.

Download your artworks here:
{download_url}

⏰ Important: This download link will expire on {expires_str}. Make sure to download your artworks before then!

---
You're receiving this email because you requested a batch download on Makapix Club.
If you didn't request this download, you can safely ignore this email.

© 2025 Makapix Club. Share your pixel art with the world.
"""

    try:
        params: resend.Emails.SendParams = {
            "from": RESEND_FROM_EMAIL,
            "to": [to_email],
            "subject": f"🎨 Your Makapix download is ready! ({artwork_count} artworks)",
            "html": html_content,
            "text": text_content,
        }

        response = resend.Emails.send(params)
        logger.info(f"BDR ready email sent to {to_email}, id: {response.get('id', 'unknown')}")
        return response
    except Exception as e:
        logger.error(f"Failed to send BDR ready email to {to_email}: {e}")
        return None


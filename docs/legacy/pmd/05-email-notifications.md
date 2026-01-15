# BDR Email Notifications

## Overview

When a user requests a batch download with `send_email=true`, they receive an email notification when the download is ready.

The email service already exists at `api/app/services/email.py` using Resend. Add a new function for BDR notifications.

---

## Implementation

Add to `api/app/services/email.py`:

```python
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


def send_bdr_failed_email(
    to_email: str,
    handle: str | None,
    artwork_count: int,
    error_message: str | None,
) -> dict[str, Any] | None:
    """
    Send email notification when a Batch Download Request fails.
    
    This is optional - only sent if the user had send_email=true.
    Helps users know they need to retry.
    
    Args:
        to_email: Recipient's email address
        handle: User's handle for personalization
        artwork_count: Number of artworks that were requested
        error_message: Error details (sanitized)
        
    Returns:
        Resend API response if successful, None if email sending is disabled or fails
    """
    if not _init_resend():
        logger.info(f"Email sending disabled - would send BDR failed to {to_email}")
        return None
    
    greeting = f"Hi {handle}!" if handle else "Hi there!"
    
    # Sanitize error message for email (don't expose internal details)
    safe_error = "An unexpected error occurred" if not error_message else (
        error_message if len(error_message) < 200 else error_message[:200] + "..."
    )
    
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Download request failed</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: #dc3545; padding: 30px; border-radius: 10px 10px 0 0; text-align: center;">
        <h1 style="color: white; margin: 0; font-size: 24px;">😔 Download Request Failed</h1>
    </div>
    
    <div style="background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px;">
        <p style="margin-top: 0; font-size: 18px;">{greeting}</p>
        
        <p>Unfortunately, we weren't able to complete your batch download request for <strong>{artwork_count} artwork{"s" if artwork_count != 1 else ""}</strong>.</p>
        
        <div style="background: #f8d7da; border: 1px solid #f5c6cb; border-radius: 8px; padding: 15px; margin: 20px 0;">
            <p style="margin: 0; color: #721c24;">
                <strong>Error:</strong> {safe_error}
            </p>
        </div>
        
        <p>You can try again by visiting your Post Management Dashboard and requesting a new download.</p>
        
        <div style="text-align: center; margin: 30px 0;">
            <a href="{os.getenv('BASE_URL', 'https://makapix.club')}" 
               style="background: #667eea; 
                      color: white; 
                      text-decoration: none; 
                      padding: 15px 30px; 
                      border-radius: 5px; 
                      font-weight: bold;
                      display: inline-block;">
                Visit Makapix Club
            </a>
        </div>
        
        <hr style="border: none; border-top: 1px solid #ddd; margin: 25px 0;">
        
        <p style="color: #999; font-size: 12px; margin-bottom: 0;">
            If this keeps happening, please contact us for support.
        </p>
    </div>
    
    <div style="text-align: center; padding: 20px; color: #999; font-size: 12px;">
        <p>© 2025 Makapix Club. Share your pixel art with the world.</p>
    </div>
</body>
</html>
"""

    text_content = f"""{greeting}

Unfortunately, we weren't able to complete your batch download request for {artwork_count} artwork{"s" if artwork_count != 1 else ""}.

Error: {safe_error}

You can try again by visiting your Post Management Dashboard and requesting a new download.

Visit Makapix Club: {os.getenv('BASE_URL', 'https://makapix.club')}

---
If this keeps happening, please contact us for support.

© 2025 Makapix Club. Share your pixel art with the world.
"""

    try:
        params: resend.Emails.SendParams = {
            "from": RESEND_FROM_EMAIL,
            "to": [to_email],
            "subject": "😔 Your Makapix download request failed",
            "html": html_content,
            "text": text_content,
        }
        
        response = resend.Emails.send(params)
        logger.info(f"BDR failed email sent to {to_email}, id: {response.get('id', 'unknown')}")
        return response
    except Exception as e:
        logger.error(f"Failed to send BDR failed email to {to_email}: {e}")
        return None
```

---

## Integration with Worker Task

In `process_bdr_job` task, after successful completion:

```python
# Send email notification if requested
if bdr.send_email and user.email:
    try:
        send_bdr_ready_email(
            to_email=user.email,
            handle=user.handle,
            artwork_count=len(posts),
            download_url=f"{os.getenv('BASE_URL', 'https://makapix.club')}/u/{user_sqid}/posts?bdr={bdr_id}",
            expires_at=bdr.expires_at,
        )
    except Exception as e:
        logger.error(f"Failed to send BDR email: {e}")
        # Don't fail the task if email fails
```

On failure (optional - uncomment if you want failure notifications):

```python
# Optionally notify on failure
# if bdr.send_email and user.email:
#     try:
#         send_bdr_failed_email(
#             to_email=user.email,
#             handle=user.handle,
#             artwork_count=bdr.artwork_count,
#             error_message=str(e)[:200],
#         )
#     except Exception as email_error:
#         logger.error(f"Failed to send BDR failure email: {email_error}")
```

---

## Testing

### Development Testing

When `RESEND_API_KEY` is not set:
- Emails are logged but not sent
- Log message: `"Email sending disabled - would send BDR ready to {email}"`

### Production Testing

1. Create a BDR with `send_email=true`
2. Wait for processing to complete
3. Check inbox for email
4. Verify:
   - Subject line shows artwork count
   - Download button links correctly
   - Expiration date is shown
   - Plain text fallback is readable

---

## Email Styling Notes

The email design follows the existing Makapix email template style:
- Purple gradient header
- Clean white/gray body
- Purple accent buttons
- Warning box for expiration
- Footer with copyright

This ensures brand consistency across all Makapix emails.

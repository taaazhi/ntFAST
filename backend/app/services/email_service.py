import smtplib
import httpx
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models.email_verification import EmailVerification
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails via Brevo, Resend API, or SMTP fallback"""

    # Configuration from settings
    SMTP_SERVER = settings.SMTP_SERVER
    SMTP_PORT = settings.SMTP_PORT
    SMTP_USERNAME = settings.SMTP_USERNAME
    SMTP_PASSWORD = settings.SMTP_PASSWORD
    USE_REAL_EMAIL = settings.USE_REAL_EMAIL
    RESEND_API_KEY = settings.RESEND_API_KEY
    EMAIL_PROVIDER = settings.EMAIL_PROVIDER
    BREVO_API_KEY = settings.BREVO_API_KEY
    MAILJET_API_KEY = settings.MAILJET_API_KEY
    MAILJET_SECRET_KEY = settings.MAILJET_SECRET_KEY
    MAILTRAP_API_TOKEN = settings.MAILTRAP_API_TOKEN
    COURIER_API_KEY = settings.COURIER_API_KEY

    # ──────────────────────────────────────────────
    # HTML templates
    # ──────────────────────────────────────────────

    @staticmethod
    def _verification_html(display_name: str, code: str) -> str:
        return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #ffffff; margin: 0; padding: 0; color: #1d1d1f;">
<div style="max-width: 440px; margin: 0 auto; padding: 60px 24px;">
    <div style="font-size: 26px; font-weight: 600; letter-spacing: -0.022em; margin-bottom: 32px;">Email Verification</div>
    <div style="font-size: 16px; font-weight: 600; margin-bottom: 8px;">Hi {display_name},</div>
    <div style="font-size: 16px; line-height: 1.5; color: #1d1d1f; margin-bottom: 32px;">
        Enter the verification code below to complete your registration.
    </div>
    <div style="margin-bottom: 40px;">
        <div style="font-size: 42px; font-weight: 700; letter-spacing: 4px; color: #000000;">{code}</div>
        <span style="font-size: 13px; color: #86868b; display: block; margin-top: 8px;">This code expires in 10 minutes.</span>
    </div>
    <div style="font-size: 13px; line-height: 1.5; color: #86868b; border-top: 1px solid #d2d2d7; padding-top: 24px;">
        If you did not request this code, you can safely ignore this email.<br><br>ntFAST
    </div>
</div></body></html>"""

    @staticmethod
    def _password_reset_html(display_name: str, code: str, device: str, location: str, current_time: str) -> str:
        return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #ffffff; margin: 0; padding: 0; color: #1d1d1f;">
<div style="max-width: 440px; margin: 0 auto; padding: 60px 24px;">
    <div style="font-size: 26px; font-weight: 600; letter-spacing: -0.022em; margin-bottom: 32px;">Password Reset Verification</div>
    <div style="font-size: 16px; font-weight: 600; margin-bottom: 8px;">Hi {display_name},</div>
    <div style="font-size: 16px; line-height: 1.5; color: #1d1d1f; margin-bottom: 32px;">
        Enter the verification code below to complete the password reset process for your account.
    </div>
    <div style="margin-bottom: 40px;">
        <div style="font-size: 42px; font-weight: 700; letter-spacing: 4px; color: #000000;">{code}</div>
        <span style="font-size: 13px; color: #86868b; display: block; margin-top: 8px;">This code expires in 10 minutes.</span>
    </div>
    <div style="border-top: 1px solid #d2d2d7; padding-top: 24px; margin-bottom: 40px;">
        <div style="font-size: 12px; font-weight: 600; color: #86868b; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 16px;">Request Details</div>
        <table style="width: 100%; border-collapse: collapse;">
            <tr><td style="font-size: 14px; color: #86868b; padding: 3px 0; width: 100px;">Device</td><td style="font-size: 14px; font-weight: 500; padding: 3px 0;">{device}</td></tr>
            <tr><td style="font-size: 14px; color: #86868b; padding: 3px 0;">Location</td><td style="font-size: 14px; font-weight: 500; padding: 3px 0;">{location}</td></tr>
            <tr><td style="font-size: 14px; color: #86868b; padding: 3px 0;">Time</td><td style="font-size: 14px; font-weight: 500; padding: 3px 0;">{current_time}</td></tr>
        </table>
    </div>
    <div style="font-size: 13px; line-height: 1.5; color: #86868b; border-top: 1px solid #d2d2d7; padding-top: 24px;">
        If you did not request this code, you can safely ignore this email.<br><br>ntFAST
    </div>
</div></body></html>"""

    # ──────────────────────────────────────────────
    # Sending methods
    # ──────────────────────────────────────────────

    @staticmethod
    def _send_via_resend(to_email: str, subject: str, html_body: str) -> bool:
        """Send email via Resend.com HTTP API — fast & reliable from cloud servers."""
        try:
            response = httpx.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {EmailService.RESEND_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": "ntFAST <onboarding@resend.dev>",
                    "to": [to_email],
                    "subject": subject,
                    "html": html_body,
                },
                timeout=10,
            )
            if response.status_code == 200:
                data = response.json()
                logger.info(f"[RESEND] Email sent to {to_email}, id={data.get('id')}")
                return True
            else:
                logger.error(f"[RESEND] Failed to send to {to_email}: {response.status_code} {response.text}")
                return False
        except Exception as e:
            logger.error(f"[RESEND] Exception sending to {to_email}: {e}")
            return False

    @staticmethod
    def _send_via_brevo(to_email: str, subject: str, html_body: str) -> bool:
        """Send email via Brevo (Sendinblue) HTTP API — 300 emails/day free, no domain needed."""
        try:
            sender_email = EmailService.SMTP_USERNAME or "noreply@ntfast.app"
            response = httpx.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={
                    "api-key": EmailService.BREVO_API_KEY,
                    "Content-Type": "application/json",
                    "accept": "application/json",
                },
                json={
                    "sender": {"name": "ntFAST", "email": sender_email},
                    "to": [{"email": to_email}],
                    "subject": subject,
                    "htmlContent": html_body,
                },
                timeout=10,
            )
            if response.status_code in (200, 201):
                data = response.json()
                logger.info(f"[BREVO] Email sent to {to_email}, messageId={data.get('messageId')}")
                return True
            else:
                logger.error(f"[BREVO] Failed to send to {to_email}: {response.status_code} {response.text}")
                return False
        except Exception as e:
            logger.error(f"[BREVO] Exception sending to {to_email}: {e}")
            return False

    @staticmethod
    def _send_via_mailjet(to_email: str, subject: str, html_body: str) -> bool:
        """Send email via Mailjet HTTP API — 200 emails/day free, no phone verification."""
        try:
            sender_email = EmailService.SMTP_USERNAME or "noreply@ntfast.app"
            response = httpx.post(
                "https://api.mailjet.com/v3.1/send",
                auth=(EmailService.MAILJET_API_KEY, EmailService.MAILJET_SECRET_KEY),
                headers={"Content-Type": "application/json"},
                json={
                    "Messages": [{
                        "From": {"Email": sender_email, "Name": "ntFAST"},
                        "To": [{"Email": to_email}],
                        "Subject": subject,
                        "HTMLPart": html_body,
                    }]
                },
                timeout=10,
            )
            if response.status_code == 200:
                data = response.json()
                messages = data.get("Messages", [])
                if messages and messages[0].get("Status") == "success":
                    logger.info(f"[MAILJET] Email sent to {to_email}")
                    return True
                else:
                    logger.error(f"[MAILJET] Unexpected response for {to_email}: {data}")
                    return False
            else:
                logger.error(f"[MAILJET] Failed to send to {to_email}: {response.status_code} {response.text}")
                return False
        except Exception as e:
            logger.error(f"[MAILJET] Exception sending to {to_email}: {e}")
            return False

    @staticmethod
    def _strip_html(html: str) -> str:
        """Convert HTML to plain text for providers that don't support HTML."""
        import re
        text = re.sub(r'<br\s*/?>', '\n', html)
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\n\s*\n', '\n\n', text).strip()
        return text

    @staticmethod
    def _is_same_domain_email(to_email: str) -> bool:
        """Check if recipient is on the same domain as SMTP sender (e.g. both @mail.ru)."""
        if not EmailService.SMTP_USERNAME:
            return False
        try:
            sender_domain = EmailService.SMTP_USERNAME.split('@')[1].lower()
            recipient_domain = to_email.split('@')[1].lower()
            return sender_domain == recipient_domain
        except (IndexError, AttributeError):
            return False

    @staticmethod
    def _send_via_courier(to_email: str, subject: str, html_body: str) -> bool:
        """Send email via Courier API — 10,000 emails/month free, GitHub signup."""
        try:
            # Courier content.body expects text/markdown, not HTML
            plain_text = EmailService._strip_html(html_body)
            response = httpx.post(
                "https://api.courier.com/send",
                headers={
                    "Authorization": f"Bearer {EmailService.COURIER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "message": {
                        "to": {"email": to_email},
                        "content": {
                            "title": subject,
                            "body": plain_text,
                        },
                        "routing": {
                            "method": "single",
                            "channels": ["email"],
                        },
                    }
                },
                timeout=15,
            )
            if response.status_code in (200, 202):
                data = response.json()
                logger.info(f"[COURIER] Email sent to {to_email}, requestId={data.get('requestId')}")
                return True
            else:
                logger.error(f"[COURIER] Failed to send to {to_email}: {response.status_code} {response.text}")
                return False
        except Exception as e:
            logger.error(f"[COURIER] Exception sending to {to_email}: {e}")
            return False

    @staticmethod
    def _send_via_mailtrap(to_email: str, subject: str, html_body: str) -> bool:
        """Send email via Mailtrap API — 1000 emails/month free, GitHub signup."""
        try:
            sender_email = EmailService.SMTP_USERNAME or "noreply@ntfast.app"
            response = httpx.post(
                "https://send.api.mailtrap.io/api/send",
                headers={
                    "Authorization": f"Bearer {EmailService.MAILTRAP_API_TOKEN}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": {"email": sender_email, "name": "ntFAST"},
                    "to": [{"email": to_email}],
                    "subject": subject,
                    "html": html_body,
                },
                timeout=10,
            )
            if response.status_code == 200:
                data = response.json()
                logger.info(f"[MAILTRAP] Email sent to {to_email}, success={data.get('success')}")
                return True
            else:
                logger.error(f"[MAILTRAP] Failed to send to {to_email}: {response.status_code} {response.text}")
                return False
        except Exception as e:
            logger.error(f"[MAILTRAP] Exception sending to {to_email}: {e}")
            return False

    @staticmethod
    def _send_via_smtp(to_email: str, subject: str, html_body: str, text_body: str = "") -> bool:
        """Send email via SMTP (mail.ru, gmail, etc.)."""
        try:
            message = MIMEMultipart('alternative')
            message['From'] = f"ntFAST <{EmailService.SMTP_USERNAME}>"
            message['To'] = to_email
            message['Subject'] = subject

            if text_body:
                message.attach(MIMEText(text_body, 'plain', 'utf-8'))
            message.attach(MIMEText(html_body, 'html', 'utf-8'))

            # SECURITY/RELIABILITY: 10-second timeout prevents the request handler
            # from blocking indefinitely if the SMTP server stops responding mid-handshake.
            smtp_timeout = 10
            if EmailService.SMTP_PORT == 465:
                with smtplib.SMTP_SSL(
                    EmailService.SMTP_SERVER, EmailService.SMTP_PORT, timeout=smtp_timeout
                ) as server:
                    server.login(EmailService.SMTP_USERNAME, EmailService.SMTP_PASSWORD)
                    server.send_message(message)
            else:
                with smtplib.SMTP(
                    EmailService.SMTP_SERVER, EmailService.SMTP_PORT, timeout=smtp_timeout
                ) as server:
                    server.starttls()
                    server.login(EmailService.SMTP_USERNAME, EmailService.SMTP_PASSWORD)
                    server.send_message(message)

            logger.info(f"[SMTP] Email sent to {to_email}")
            return True
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"[SMTP] Authentication failed for {to_email}: {e}")
            return False
        except (smtplib.SMTPException, OSError, TimeoutError) as e:
            logger.error(f"[SMTP] Failed to send to {to_email}: {e}")
            return False
        except Exception as e:
            logger.error(f"[SMTP] Unexpected failure for {to_email}: {e}", exc_info=True)
            return False

    @staticmethod
    def _send_email(to_email: str, subject: str, html_body: str, text_body: str = "") -> bool:
        """Send email with smart routing.

        Strategy:
        - Same-domain emails (e.g. mail.ru → mail.ru): SMTP first (internal delivery is reliable)
        - Other emails: Courier first, then other API providers, SMTP last
        """
        has_smtp = EmailService.USE_REAL_EMAIL and EmailService.SMTP_USERNAME and EmailService.SMTP_PASSWORD
        has_courier = bool(EmailService.COURIER_API_KEY)

        # Build ordered list of send methods
        send_methods = []

        # SMTP first — Gmail/Mail.ru direct delivery is most reliable
        if has_smtp:
            logger.info(f"[EMAIL] Using SMTP first for {to_email}")
            send_methods.append(("smtp", lambda: EmailService._send_via_smtp(to_email, subject, html_body, text_body)))

        # API providers as fallback only
        if has_courier:
            send_methods.append(("courier", lambda: EmailService._send_via_courier(to_email, subject, html_body)))
        if EmailService.BREVO_API_KEY:
            send_methods.append(("brevo", lambda: EmailService._send_via_brevo(to_email, subject, html_body)))
        if EmailService.RESEND_API_KEY:
            send_methods.append(("resend", lambda: EmailService._send_via_resend(to_email, subject, html_body)))
        if EmailService.MAILTRAP_API_TOKEN:
            send_methods.append(("mailtrap", lambda: EmailService._send_via_mailtrap(to_email, subject, html_body)))
        if EmailService.MAILJET_API_KEY:
            send_methods.append(("mailjet", lambda: EmailService._send_via_mailjet(to_email, subject, html_body)))

        # Try each method in order
        for name, method in send_methods:
            try:
                if method():
                    if "fallback" in name:
                        logger.info(f"[EMAIL] Sent via {name} (primary provider failed)")
                    return True
                else:
                    logger.warning(f"[EMAIL] {name} returned False for {to_email}, trying next...")
            except Exception as e:
                logger.warning(f"[EMAIL] {name} failed for {to_email}: {e}, trying next...")

        # No provider worked
        if not send_methods:
            logger.info(f"[DEMO] Email to {to_email}: subject='{subject}' (no provider configured)")
            return True
        else:
            logger.error(f"[EMAIL] All providers failed for {to_email}")
            return False

    # ──────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────

    @staticmethod
    def send_verification_code(email: str, code: str) -> bool:
        """Send verification code to email."""
        display_name = email.split('@')[0].replace('.', ' ').replace('_', ' ').title()
        html_body = EmailService._verification_html(display_name, code)

        result = EmailService._send_email(email, "Email Verification", html_body)

        if not result:
            # Log code for debugging if email fails
            logger.warning(f"[FALLBACK] Verification code for {email}: {code}")

        return result

    @staticmethod
    def send_password_reset_code(email: str, code: str, user_name: str = None,
                                  device_info: str = None, location: str = None,
                                  time_info: str = None) -> bool:
        """Send password reset code to email."""
        display_name = user_name or email.split('@')[0].replace('.', ' ').replace('_', ' ').title()
        device = device_info or "Unknown Device"
        user_location = location or "Unknown Location"

        if time_info:
            current_time = time_info
        else:
            try:
                import pytz
                tz = pytz.timezone('Asia/Almaty')
                now = datetime.now(tz)
                current_time = now.strftime("%B %d, %Y at %H:%M (GMT+5)")
            except (ImportError, KeyError):
                current_time = datetime.now().strftime("%B %d, %Y at %H:%M")

        html_body = EmailService._password_reset_html(display_name, code, device, user_location, current_time)

        result = EmailService._send_email(email, "Password Reset Verification", html_body)

        if not result:
            logger.warning(f"[FALLBACK] Password reset code for {email}: {code}")

        return result

    # ──────────────────────────────────────────────
    # Verification code management (DB)
    # ──────────────────────────────────────────────

    @staticmethod
    def create_verification_code(db: Session, email: str) -> str:
        """Create and store a new verification code"""
        code = EmailVerification.generate_code()

        # Delete old codes for this email
        db.query(EmailVerification).filter(
            EmailVerification.email == email
        ).delete()

        # Create new verification record
        verification = EmailVerification(
            email=email,
            code=code,
            is_verified=False,
            expires_at=datetime.utcnow() + timedelta(minutes=10)
        )

        db.add(verification)
        db.commit()

        return code

    @staticmethod
    def verify_code(db: Session, email: str, code: str) -> bool:
        """Verify the code for an email"""
        verification = db.query(EmailVerification).filter(
            EmailVerification.email == email,
            EmailVerification.code == code,
            EmailVerification.is_verified == False,
            EmailVerification.expires_at > datetime.utcnow()
        ).first()

        if not verification:
            return False

        verification.is_verified = True
        db.commit()

        return True

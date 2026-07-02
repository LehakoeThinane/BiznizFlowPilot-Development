"""Email delivery service.

Priority order:
  1. Resend  — when RESEND_API_KEY is set in .env
  2. SMTP    — when smtp_host/smtp_username are configured
  3. Dev log — when neither is configured (logs to console)
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

_USE_RESEND = bool(settings.resend_api_key)
_DEV_MODE = (
    not _USE_RESEND
    and settings.smtp_host in ("localhost", "127.0.0.1", "")
    and not settings.smtp_username
)


def _send(to: str, subject: str, html: str, plain: str) -> None:
    if _DEV_MODE:
        logger.info("DEV EMAIL — To: %s | Subject: %s\n%s", to, subject, plain)
        return

    if _USE_RESEND:
        _send_via_resend(to, subject, html, plain)
    else:
        _send_via_smtp(to, subject, html, plain)


def _send_via_resend(to: str, subject: str, html: str, plain: str) -> None:
    import resend as resend_sdk

    resend_sdk.api_key = settings.resend_api_key
    params: resend_sdk.Emails.SendParams = {
        "from": f"{settings.smtp_from_name} <{settings.smtp_from_email}>",
        "to": [to],
        "subject": subject,
        "html": html,
        "text": plain,
    }
    try:
        result = resend_sdk.Emails.send(params)
        logger.info("Email sent via Resend — id: %s to: %s", result.get("id"), to)
    except Exception:
        logger.exception("Resend failed to deliver email to %s", to)
        raise


def _send_via_smtp(to: str, subject: str, html: str, plain: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    msg["To"] = to
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))

    try:
        if settings.smtp_use_ssl:
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_seconds) as smtp:
                if settings.smtp_username:
                    smtp.login(settings.smtp_username, settings.smtp_password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_seconds) as smtp:
                if settings.smtp_use_tls:
                    smtp.starttls()
                if settings.smtp_username:
                    smtp.login(settings.smtp_username, settings.smtp_password)
                smtp.send_message(msg)
    except Exception:
        logger.exception("SMTP failed to deliver email to %s", to)
        raise


def send_invoice_email(
    to_email: str,
    customer_name: str,
    invoice_number: str,
    issue_date: str,
    due_date: str | None,
    total_amount: float,
    rows_html: str,
    notes: str | None,
) -> None:
    subject = f"Invoice {invoice_number} from {settings.smtp_from_name}"
    due_str = f"Due: {due_date}" if due_date else ""

    plain = (
        f"Dear {customer_name},\n\n"
        f"Please find your invoice below.\n\n"
        f"Invoice: {invoice_number}\n"
        f"Issued: {issue_date}\n"
        f"{due_str}\n"
        f"Total: R {total_amount:,.2f}\n\n"
        f"{('Notes: ' + notes) if notes else ''}\n\n"
        f"Thank you for your business.\n— {settings.smtp_from_name}"
    )

    html = f"""
<!DOCTYPE html>
<html>
<body style="font-family:sans-serif;background:#f8fafc;color:#1a1a1a;padding:32px">
  <div style="max-width:560px;margin:0 auto;background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:32px">
    <h2 style="margin:0 0 4px;color:#1e3a8a">Invoice {invoice_number}</h2>
    <p style="color:#64748b;font-size:14px;margin:0 0 24px">Issued: {issue_date}{(' · Due: ' + due_date) if due_date else ''}</p>
    <table style="width:100%;border-collapse:collapse;font-size:14px">
      <thead>
        <tr style="background:#f1f5f9">
          <th style="padding:8px;text-align:left">Description</th>
          <th style="padding:8px;text-align:right">Qty</th>
          <th style="padding:8px;text-align:right">Unit Price</th>
          <th style="padding:8px;text-align:right">Amount</th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>
    <div style="text-align:right;margin-top:16px;font-size:18px;font-weight:700;color:#1e3a8a">
      Total: R {total_amount:,.2f}
    </div>
    {f'<p style="margin-top:16px;padding:12px;background:#f8fafc;border-left:3px solid #1e3a8a;font-size:13px">{notes}</p>' if notes else ''}
    <p style="margin-top:24px;color:#94a3b8;font-size:12px">
      Thank you for your business. — {settings.smtp_from_name}
    </p>
  </div>
</body>
</html>"""
    _send(to_email, subject, html, plain)


def send_invite_email(
    to_email: str,
    organization_name: str,
    business_name: str,
    invited_by_name: str,
    raw_token: str,
) -> None:
    accept_link = f"{settings.frontend_url}/accept-invite?token={raw_token}"
    subject = f"You've been invited to join {organization_name} on {settings.smtp_from_name}"

    plain = (
        f"Hi,\n\n"
        f"{invited_by_name} has invited you to join {business_name} ({organization_name}) "
        f"on {settings.smtp_from_name}.\n\n"
        f"Accept your invite: {accept_link}\n\n"
        f"This invite expires in {settings.invite_token_expiration_days} days.\n\n"
        f"If you weren't expecting this, you can ignore this email.\n\n"
        f"— {settings.smtp_from_name}"
    )

    html = f"""
<!DOCTYPE html>
<html>
<body style="font-family:sans-serif;background:#0a0a0a;color:#e5e5e5;padding:32px">
  <div style="max-width:480px;margin:0 auto;background:#141414;border:1px solid #222;border-radius:12px;padding:32px">
    <h2 style="color:#fff;margin:0 0 8px">You're invited to {business_name}</h2>
    <p style="color:#888;font-size:14px;margin:0 0 24px">
      {invited_by_name} has invited you to join {organization_name} on {settings.smtp_from_name}.
    </p>
    <a href="{accept_link}"
       style="display:inline-block;background:#059669;color:#fff;font-weight:600;font-size:14px;
              padding:10px 24px;border-radius:6px;text-decoration:none;margin-bottom:24px">
      Accept invite
    </a>
    <p style="color:#555;font-size:12px;margin:16px 0 0">
      This invite expires in {settings.invite_token_expiration_days} days.
      If you weren't expecting this, ignore this email.
    </p>
  </div>
</body>
</html>
"""
    _send(to_email, subject, html, plain)


def send_password_reset_email(to_email: str, reset_token: str) -> None:
    reset_link = f"{settings.frontend_url}/login?reset_token={reset_token}"
    subject = "Reset your BiznizFlowPilot password"

    plain = (
        f"Hi,\n\n"
        f"We received a request to reset your password.\n\n"
        f"Reset link: {reset_link}\n\n"
        f"Or paste this token on the reset form: {reset_token}\n\n"
        f"This link expires in {settings.password_reset_token_expiration_minutes} minutes.\n\n"
        f"If you didn't request this, you can safely ignore this email.\n\n"
        f"— {settings.smtp_from_name}"
    )

    html = f"""
<!DOCTYPE html>
<html>
<body style="font-family:sans-serif;background:#0a0a0a;color:#e5e5e5;padding:32px">
  <div style="max-width:480px;margin:0 auto;background:#141414;border:1px solid #222;border-radius:12px;padding:32px">
    <div style="margin-bottom:24px">
      <span style="display:inline-block;background:#059669;color:#fff;font-weight:700;font-size:18px;
                   width:40px;height:40px;line-height:40px;text-align:center;border-radius:10px">B</span>
    </div>
    <h2 style="color:#fff;margin:0 0 8px">Reset your password</h2>
    <p style="color:#888;font-size:14px;margin:0 0 24px">
      We received a request to reset your BiznizFlowPilot password.
    </p>
    <a href="{reset_link}"
       style="display:inline-block;background:#059669;color:#fff;font-weight:600;font-size:14px;
              padding:10px 24px;border-radius:6px;text-decoration:none;margin-bottom:24px">
      Reset password
    </a>
    <p style="color:#555;font-size:12px;margin:0 0 8px">
      Or copy this token and paste it on the reset form:
    </p>
    <code style="display:block;background:#0f0f0f;border:1px solid #333;border-radius:6px;
                 padding:10px;font-size:12px;word-break:break-all;color:#10b981">{reset_token}</code>
    <p style="color:#555;font-size:12px;margin:16px 0 0">
      This link expires in {settings.password_reset_token_expiration_minutes} minutes.
      If you didn't request this, ignore this email.
    </p>
  </div>
</body>
</html>
"""
    _send(to_email, subject, html, plain)

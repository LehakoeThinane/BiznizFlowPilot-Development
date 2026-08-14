"""Email delivery service.

Priority order:
  1. Resend  — when RESEND_API_KEY is set in .env
  2. SMTP    — when smtp_host/smtp_username are configured
  3. Dev log — when neither is configured (logs to console)

Every send_* function optionally accepts (db, organization_id): when that
Organization has a custom SMTP sender configured (app/api/platform_admin.py's
email-config routes), its credentials are used instead of the platform
default, so tenant-facing emails (starting with meeting invites) can come
from the business's own domain. An org with custom SMTP bypasses Resend
entirely - the whole point of custom SMTP is sending as *their* domain,
which Resend (sending from the platform's verified domain) can't do.
"""

import base64
import html
import smtplib
from dataclasses import dataclass
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import NamedTuple
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

_USE_RESEND = bool(settings.resend_api_key)
_DEV_MODE = (
    not _USE_RESEND
    and settings.smtp_host in ("localhost", "127.0.0.1", "")
    and not settings.smtp_username
)


class EmailAttachment(NamedTuple):
    filename: str
    content: bytes
    mime_type: str


@dataclass
class _EmailConfig:
    use_resend: bool
    resend_api_key: str
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    smtp_use_ssl: bool
    smtp_use_tls: bool
    smtp_from_email: str
    smtp_from_name: str
    smtp_timeout_seconds: int
    dev_mode: bool


def _platform_default_config() -> _EmailConfig:
    return _EmailConfig(
        use_resend=_USE_RESEND,
        resend_api_key=settings.resend_api_key,
        smtp_host=settings.smtp_host,
        smtp_port=settings.smtp_port,
        smtp_username=settings.smtp_username,
        smtp_password=settings.smtp_password,
        smtp_use_ssl=settings.smtp_use_ssl,
        smtp_use_tls=settings.smtp_use_tls,
        smtp_from_email=settings.smtp_from_email,
        smtp_from_name=settings.smtp_from_name,
        smtp_timeout_seconds=settings.smtp_timeout_seconds,
        dev_mode=_DEV_MODE,
    )


def _resolve_email_config(db: Session | None, organization_id: UUID | None) -> _EmailConfig:
    """Use an org's own SMTP sender when fully configured, else the platform default."""
    if db is not None and organization_id is not None:
        from app.repositories.organization import OrganizationRepository

        org = OrganizationRepository(db).get_by_id(organization_id)
        if org and org.smtp_host and org.smtp_username and org.smtp_password_encrypted and org.smtp_from_email:
            from app.core.crypto import decrypt_secret

            port = org.smtp_port or 587
            return _EmailConfig(
                use_resend=False,
                resend_api_key="",
                smtp_host=org.smtp_host,
                smtp_port=port,
                smtp_username=org.smtp_username,
                smtp_password=decrypt_secret(org.smtp_password_encrypted),
                smtp_use_ssl=(port == 465),
                smtp_use_tls=(port != 465),
                smtp_from_email=org.smtp_from_email,
                smtp_from_name=org.smtp_from_name or org.name,
                smtp_timeout_seconds=settings.smtp_timeout_seconds,
                dev_mode=False,
            )
    return _platform_default_config()


def _send(
    to: str,
    subject: str,
    html: str,
    plain: str,
    db: Session | None = None,
    organization_id: UUID | None = None,
    attachments: list[EmailAttachment] | None = None,
) -> None:
    cfg = _resolve_email_config(db, organization_id)
    if cfg.dev_mode:
        logger.info("DEV EMAIL — To: %s | Subject: %s\n%s", to, subject, plain)
        if attachments:
            logger.info("DEV EMAIL attachments: %s", [a.filename for a in attachments])
        return

    if cfg.use_resend:
        _send_via_resend(to, subject, html, plain, cfg, attachments)
    else:
        _send_via_smtp(to, subject, html, plain, cfg, attachments)


def _send_via_resend(
    to: str, subject: str, html: str, plain: str, cfg: _EmailConfig, attachments: list[EmailAttachment] | None
) -> None:
    import resend as resend_sdk

    resend_sdk.api_key = cfg.resend_api_key
    params: resend_sdk.Emails.SendParams = {
        "from": f"{cfg.smtp_from_name} <{cfg.smtp_from_email}>",
        "to": [to],
        "subject": subject,
        "html": html,
        "text": plain,
    }
    if attachments:
        params["attachments"] = [
            {"filename": a.filename, "content": base64.b64encode(a.content).decode()} for a in attachments
        ]
    try:
        result = resend_sdk.Emails.send(params)
        logger.info("Email sent via Resend — id: %s to: %s", result.get("id"), to)
    except Exception:
        logger.exception("Resend failed to deliver email to %s", to)
        raise


def _send_via_smtp(
    to: str, subject: str, html: str, plain: str, cfg: _EmailConfig, attachments: list[EmailAttachment] | None
) -> None:
    body = MIMEMultipart("alternative")
    body.attach(MIMEText(plain, "plain"))
    body.attach(MIMEText(html, "html"))

    if attachments:
        msg = MIMEMultipart("mixed")
        msg.attach(body)
        for a in attachments:
            maintype, _, subtype = a.mime_type.partition("/")
            part = MIMEApplication(a.content, _subtype=subtype or "octet-stream")
            part.add_header("Content-Disposition", "attachment", filename=a.filename)
            msg.attach(part)
    else:
        msg = body

    msg["Subject"] = subject
    msg["From"] = f"{cfg.smtp_from_name} <{cfg.smtp_from_email}>"
    msg["To"] = to

    try:
        if cfg.smtp_use_ssl:
            with smtplib.SMTP_SSL(cfg.smtp_host, cfg.smtp_port, timeout=cfg.smtp_timeout_seconds) as smtp:
                if cfg.smtp_username:
                    smtp.login(cfg.smtp_username, cfg.smtp_password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=cfg.smtp_timeout_seconds) as smtp:
                if cfg.smtp_use_tls:
                    smtp.starttls()
                if cfg.smtp_username:
                    smtp.login(cfg.smtp_username, cfg.smtp_password)
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


def send_trial_reminder_email(to_email: str, org_name: str, days_remaining: int) -> None:
    pricing_link = "https://mmnexus.co.za/biznizflowpilot#pricing"
    subject = f"Your BiznizFlowPilot trial ends in {days_remaining} days"

    plain = (
        f"Hi,\n\n"
        f"{org_name}'s BiznizFlowPilot trial ends in {days_remaining} days. After that, your team "
        f"loses access until you upgrade to a paid plan - CRM, tasks, inventory, everything.\n\n"
        f"Pick a plan: {pricing_link}\n\n"
        f"— BiznizFlowPilot"
    )

    html = f"""
<!DOCTYPE html>
<html>
<body style="font-family:sans-serif;background:#070d1a;color:#e8f0ff;padding:32px">
  <div style="max-width:480px;margin:0 auto;background:#101a2c;border:1px solid #25344f;border-radius:12px;padding:32px">
    <div style="margin-bottom:24px">
      <span style="display:inline-block;background:#2a7fff;color:#fff;font-weight:700;font-size:18px;
                   width:40px;height:40px;line-height:40px;text-align:center;border-radius:10px">B</span>
    </div>
    <h2 style="color:#e8f0ff;margin:0 0 8px">Your trial ends in {days_remaining} days</h2>
    <p style="color:#8ea1c1;font-size:14px;margin:0 0 24px">
      {org_name}'s BiznizFlowPilot trial ends soon. After that, your team loses access until you
      upgrade - CRM, tasks, inventory, everything.
    </p>
    <a href="{pricing_link}"
       style="display:inline-block;background:#2a7fff;color:#fff;font-weight:600;font-size:14px;
              padding:10px 24px;border-radius:8px;text-decoration:none;margin-bottom:8px">
      Pick a plan
    </a>
  </div>
</body>
</html>
"""
    _send(to_email, subject, html, plain)


def _meeting_email(
    to_email: str,
    subject: str,
    heading: str,
    body_lines_plain: str,
    body_html: str,
    accept_url: str | None,
    decline_url: str | None,
    ics_bytes: bytes,
    ics_method: str,
    db: Session | None,
    organization_id: UUID | None,
) -> None:
    plain = f"{heading}\n\n{body_lines_plain}\n"
    if accept_url and decline_url:
        plain += f"\nAccept: {accept_url}\nDecline: {decline_url}\n"
    plain += "\n— BiznizFlowPilot"

    rsvp_buttons_html = ""
    if accept_url and decline_url:
        rsvp_buttons_html = f"""
    <div style="margin-top:16px">
      <a href="{accept_url}"
         style="display:inline-block;background:#059669;color:#fff;font-weight:600;font-size:14px;
                padding:10px 20px;border-radius:6px;text-decoration:none;margin-right:12px">
        Accept
      </a>
      <a href="{decline_url}"
         style="display:inline-block;background:#374151;color:#fff;font-weight:600;font-size:14px;
                padding:10px 20px;border-radius:6px;text-decoration:none">
        Decline
      </a>
    </div>"""

    html = f"""
<!DOCTYPE html>
<html>
<body style="font-family:sans-serif;background:#0a0a0a;color:#e5e5e5;padding:32px">
  <div style="max-width:480px;margin:0 auto;background:#141414;border:1px solid #222;border-radius:12px;padding:32px">
    <h2 style="color:#fff;margin:0 0 8px">{heading}</h2>
    <p style="color:#888;font-size:14px;margin:0 0 8px;white-space:pre-line">{body_html}</p>
    {rsvp_buttons_html}
    <p style="color:#555;font-size:12px;margin:16px 0 0">
      A calendar invite is attached - add it to Google Calendar, Outlook, or Apple Calendar.
    </p>
  </div>
</body>
</html>
"""
    attachment = EmailAttachment(
        filename="invite.ics", content=ics_bytes, mime_type=f"text/calendar; method={ics_method}"
    )
    _send(to_email, subject, html, plain, db=db, organization_id=organization_id, attachments=[attachment])


def send_meeting_invite_email(
    to_email: str,
    meeting_title: str,
    start_time_str: str,
    organizer_name: str,
    accept_url: str,
    decline_url: str,
    ics_bytes: bytes,
    db: Session | None = None,
    organization_id: UUID | None = None,
) -> None:
    subject = f"Meeting invite: {meeting_title}"
    body_plain = f"{organizer_name} has invited you to a meeting.\n\nWhen: {start_time_str}"
    body_html = f"{organizer_name} has invited you to a meeting.<br>When: {start_time_str}"
    _meeting_email(
        to_email, subject, f"You're invited: {meeting_title}", body_plain, body_html,
        accept_url, decline_url, ics_bytes, "REQUEST", db, organization_id,
    )


def send_meeting_update_email(
    to_email: str,
    meeting_title: str,
    start_time_str: str,
    organizer_name: str,
    accept_url: str,
    decline_url: str,
    ics_bytes: bytes,
    db: Session | None = None,
    organization_id: UUID | None = None,
) -> None:
    subject = f"Meeting updated: {meeting_title}"
    body_plain = f"{organizer_name} has updated this meeting.\n\nNew time: {start_time_str}"
    body_html = f"{organizer_name} has updated this meeting.<br>New time: {start_time_str}"
    _meeting_email(
        to_email, subject, f"Meeting updated: {meeting_title}", body_plain, body_html,
        accept_url, decline_url, ics_bytes, "REQUEST", db, organization_id,
    )


def send_meeting_cancelled_email(
    to_email: str,
    meeting_title: str,
    start_time_str: str,
    organizer_name: str,
    ics_bytes: bytes,
    db: Session | None = None,
    organization_id: UUID | None = None,
) -> None:
    subject = f"Meeting cancelled: {meeting_title}"
    body_plain = f"{organizer_name} has cancelled this meeting.\n\nWas scheduled: {start_time_str}"
    body_html = f"{organizer_name} has cancelled this meeting.<br>Was scheduled: {start_time_str}"
    _meeting_email(
        to_email, subject, f"Meeting cancelled: {meeting_title}", body_plain, body_html,
        None, None, ics_bytes, "CANCEL", db, organization_id,
    )


def _notify_staff(subject: str, html: str, plain: str) -> None:
    """Shared sender for internal staff notifications (marketing leads,
    onboarding help requests). No-ops (log only) if staff_notification_email
    isn't configured, same "empty means disabled" convention as
    sentry_dsn/google_places_api_key in app/core/config.py. Never passes
    organization_id - these notifications go to MM Nexus staff, not a
    tenant's own custom SMTP sender."""
    if not settings.staff_notification_email:
        logger.info("email.staff_notification.skipped_not_configured", extra={"subject": subject})
        return
    _send(settings.staff_notification_email, subject, html, plain)


def send_lead_followup_email(
    to_email: str,
    subject: str,
    plain_body: str,
    business_name: str,
    db: Session | None = None,
    organization_id: UUID | None = None,
) -> None:
    """Automated first-touch outreach to a lead-gen-sourced prospect (see
    app/services/lead_followup.py). Passes organization_id through so it
    sends using that business's own configured sender identity/domain when
    one is set, not the platform default - this has to look like it's from
    business_name, not from BiznizFlowPilot. Deliberately plain (no branded
    button/box chrome like the other templates here) - it's meant to read
    as a real, personal email, not a marketing blast."""
    paragraphs = [p.strip() for p in plain_body.split("\n\n") if p.strip()]
    html_body = "".join(
        f'<p style="margin:0 0 14px;font-family:sans-serif;font-size:14px;'
        f'line-height:1.6;color:#1a1a1a">{html.escape(p)}</p>'
        for p in paragraphs
    )
    _send(to_email, subject, html_body, plain_body, db=db, organization_id=organization_id)


def send_marketing_guide_lead_email(
    first_name: str, last_name: str, email: str, company: str, guide_slug: str
) -> None:
    subject = f"New guide download lead: {first_name} {last_name} ({company})"
    plain = (
        f"A marketing-site visitor downloaded the '{guide_slug}' guide.\n\n"
        f"Name: {first_name} {last_name}\nEmail: {email}\nCompany: {company}\nGuide: {guide_slug}"
    )
    html = (
        f"<p>A marketing-site visitor downloaded the <strong>{guide_slug}</strong> guide.</p>"
        f"<p>Name: {first_name} {last_name}<br>Email: {email}<br>Company: {company}</p>"
    )
    _notify_staff(subject, html, plain)


def send_blog_autopublish_notice(outcome: str, detail: str, post_id: str | None = None) -> None:
    """Daily FYI/alert from the blog autopublish task (see
    app/services/marketing_blog_autopublish.py) - fires on every run,
    success or skip, so the automation is never silent. outcome is a short
    label ("published", "skipped", "needs review", "failed"); detail is the
    human-readable reason/title."""
    subject = f"Blog autopublish: {outcome}"
    review_url = f"{settings.marketing_site_admin_url}?id={post_id}" if settings.marketing_site_admin_url and post_id else None
    plain = f"{detail}"
    html = f"<p>{detail}</p>"
    if review_url:
        plain += f"\n\n{review_url}"
        html += f'<p><a href="{review_url}">{review_url}</a></p>'
    _notify_staff(subject, html, plain)


def send_linkedin_lead_email(
    first_name: str,
    last_name: str,
    email: str,
    company: str | None,
    job_title: str | None,
    campaign_name: str | None,
) -> None:
    company_part = company or "unknown company"
    title_part = f", {job_title}" if job_title else ""
    campaign_part = campaign_name or "unknown campaign"
    subject = f"New LinkedIn lead: {first_name} {last_name} ({company_part}{title_part}) - {campaign_part}"
    plain = (
        f"A LinkedIn ad lead came in.\n\n"
        f"Name: {first_name} {last_name}\nTitle: {job_title or '(none)'}\n"
        f"Company: {company_part}\nEmail: {email}\nCampaign: {campaign_part}"
    )
    html = (
        f"<p>A LinkedIn ad lead came in.</p>"
        f"<p>Name: {first_name} {last_name}<br>Title: {job_title or '(none)'}<br>"
        f"Company: {company_part}<br>Email: {email}<br>Campaign: {campaign_part}</p>"
    )
    _notify_staff(subject, html, plain)


def send_onboarding_help_request_email(
    user_name: str, user_email: str, business_name: str, note: str | None
) -> None:
    subject = f"Onboarding help requested: {business_name}"
    note_line = note or "(no note added)"
    plain = (
        f"{user_name} ({user_email}) at {business_name} requested help getting set up.\n\n"
        f"Note: {note_line}"
    )
    html = (
        f"<p>{user_name} ({user_email}) at <strong>{business_name}</strong> requested help getting set up.</p>"
        f"<p>Note: {note_line}</p>"
    )
    _notify_staff(subject, html, plain)

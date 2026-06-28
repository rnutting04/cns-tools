import logging

from app.config.settings import settings

logger = logging.getLogger(__name__)


def send_email(to: str, subject: str, html: str) -> None:
    if not settings.RESEND_API_KEY:
        logger.info(
            "Email suppressed (RESEND_API_KEY not set): to=%s subject=%r\n%s", to, subject, html
        )
        return

    import resend

    resend.api_key = settings.RESEND_API_KEY
    resend.Emails.send(
        {
            "from": settings.EMAIL_FROM,
            "to": to,
            "subject": subject,
            "html": html,
        }
    )

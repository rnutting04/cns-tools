import logging

from app.config.environment import Environment
from app.config.settings import settings

logger = logging.getLogger(__name__)


def send_email(to: str, subject: str, html: str) -> None:
    env = Environment.current()

    # Non-production environments (local, staging) redirect all outgoing mail to
    # LOCAL_EMAIL_TO so we never email real users while testing. The subject is
    # tagged with the environment and the original recipient so redirected mail
    # is unambiguous when it all lands in one inbox.
    if env.redirects_email:
        if not settings.LOCAL_EMAIL_TO:
            logger.info(
                "Email suppressed (%s env, LOCAL_EMAIL_TO not set): to=%s subject=%r",
                env.value,
                to,
                subject,
            )
            return
        recipient = settings.LOCAL_EMAIL_TO
        subject = f"[{env.value.upper()} → {to}] {subject}"
    else:
        recipient = to

    if not settings.RESEND_API_KEY:
        logger.info(
            "Email suppressed (RESEND_API_KEY not set): to=%s subject=%r\n%s",
            recipient,
            subject,
            html,
        )
        return

    import resend

    resend.api_key = settings.RESEND_API_KEY
    params = {
        "from": settings.EMAIL_FROM,
        "to": recipient,
        "subject": subject,
        "html": html,
    }
    if settings.EMAIL_REPLY_TO:
        params["reply_to"] = settings.EMAIL_REPLY_TO
    resend.Emails.send(params)

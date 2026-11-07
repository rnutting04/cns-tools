from html import escape

from app.celery_app import celery_app
from app.config.settings import settings
from app.services.email import layout
from app.services.email.sender import send_email


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def send_email_task(self, to: str, subject: str, html: str) -> None:
    send_email(to, subject, html)


def _login_steps(to: str) -> str:
    return layout.steps(
        [
            "Open C&amp;S Tools using the button above.",
            f"Sign in with <b>{escape(to)}</b> and the temporary password above.",
            "Choose your own password when prompted — that's the one you'll use from then on.",
        ]
    )


def welcome_email(to: str, fname: str, temp_password: str) -> None:
    """Sent when an account is created, and when an admin re-invites an existing
    user (see POST /users/{id}/send-welcome). It is deliberately framed as an
    invitation rather than a password reset: for the wider rollout, most
    recipients have had an account provisioned for them but have never signed
    in, so "your password was reset" would be confusing and look like a
    security alert.
    """
    html = layout.render(
        preheader="Your C&S Tools account is ready — here's how to sign in.",
        title="Welcome to C&S Tools",
        blocks=[
            layout.heading(f"Welcome, {fname}"),
            layout.paragraph(
                "Your <b>C&amp;S Tools</b> account is ready. C&amp;S Tools is where we "
                "generate association budgets, produce owner letters and manage "
                "association records in one place."
            ),
            layout.paragraph("Use the temporary credentials below for your first sign-in:"),
            layout.credentials(to, temp_password),
            layout.button("Sign in to C&S Tools", settings.FRONTEND_URL),
            _login_steps(to),
            layout.callout(
                "This temporary password is single-use — you'll be asked to set your "
                "own password as soon as you sign in. If you'd rather not keep it in "
                "your inbox, delete this email once you're in."
            ),
        ],
        footer_note="You're receiving this because an administrator set up a C&S Tools account for you.",
    )
    send_email_task.delay(to, "Welcome to C&S Tools — your account is ready", html)


def reset_password_email(to: str, fname: str, temp_password: str) -> None:
    html = layout.render(
        preheader="An administrator reset your C&S Tools password.",
        title="Your C&S Tools password was reset",
        blocks=[
            layout.heading("Your password was reset"),
            layout.paragraph(
                f"Hi {escape(fname)}, an administrator has reset your <b>C&amp;S Tools</b> "
                "password. Your previous password no longer works."
            ),
            layout.credentials(to, temp_password),
            layout.button("Sign in and set a new password", settings.FRONTEND_URL),
            layout.callout(
                "You'll be required to choose a new password when you sign in. "
                "If you didn't expect this reset, contact your administrator before "
                "using the password above."
            ),
        ],
    )
    send_email_task.delay(to, "Your C&S Tools password has been reset", html)


def password_changed_email(to: str, fname: str) -> None:
    html = layout.render(
        preheader="Your C&S Tools password was changed successfully.",
        title="Your C&S Tools password was changed",
        blocks=[
            layout.heading("Password changed"),
            layout.paragraph(
                f"Hi {escape(fname)}, your <b>C&amp;S Tools</b> password was changed "
                "successfully. No further action is needed."
            ),
            layout.callout(
                "<b>Didn't make this change?</b> Contact your administrator "
                "immediately — someone else may have access to your account."
            ),
            layout.paragraph(f"Account: {escape(to)}", muted=True),
        ],
    )
    send_email_task.delay(to, "Your C&S Tools password has been changed", html)


def budget_complete_email(to: str, fname: str, association_name: str, budget_year: int) -> None:
    assoc = escape(association_name)
    html = layout.render(
        preheader=f"The {budget_year} budget for {association_name} is ready to download.",
        title=f"Budget ready: {association_name} {budget_year}",
        blocks=[
            layout.heading("Your budget is ready"),
            layout.paragraph(
                f"Hi {escape(fname)}, the budget for <b>{assoc}</b> "
                f"(<b>{budget_year}</b>) has finished generating and is ready to "
                "download."
            ),
            layout.button("Download the budget", settings.FRONTEND_URL),
            layout.paragraph(
                "Review the generated figures before distributing them to the board.",
                muted=True,
            ),
        ],
    )
    send_email_task.delay(to, f"Budget ready: {association_name} {budget_year}", html)

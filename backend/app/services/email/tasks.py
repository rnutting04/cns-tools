from app.celery_app import celery_app
from app.config.settings import settings
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


def welcome_email(to: str, fname: str, temp_password: str) -> None:
    html = f"""
    <p>Hi {fname},</p>
    <p>Your CNS Tools account has been created. Use the credentials below to log in and set a new password.</p>
    <p><b>Email:</b> {to}<br><b>Temporary password:</b> {temp_password}</p>
    <p><a href="{settings.FRONTEND_URL}">Log in to CNS Tools</a></p>
    <p>You will be prompted to change your password on first login.</p>
    """
    send_email_task.delay(to, "Welcome to CNS Tools", html)


def reset_password_email(to: str, fname: str, temp_password: str) -> None:
    html = f"""
    <p>Hi {fname},</p>
    <p>An administrator has reset your CNS Tools password. Use the credentials below to log in and set a new password.</p>
    <p><b>Email:</b> {to}<br><b>Temporary password:</b> {temp_password}</p>
    <p><a href="{settings.FRONTEND_URL}">Log in to CNS Tools</a></p>
    <p>You will be prompted to change your password on first login.</p>
    """
    send_email_task.delay(to, "Your CNS Tools password has been reset", html)


def password_changed_email(to: str, fname: str) -> None:
    html = f"""
    <p>Hi {fname},</p>
    <p>Your CNS Tools password was successfully changed.</p>
    <p>If you did not make this change, contact your administrator immediately.</p>
    """
    send_email_task.delay(to, "Your CNS Tools password has been changed", html)


def budget_complete_email(to: str, fname: str, association_name: str, budget_year: int) -> None:
    html = f"""
    <p>Hi {fname},</p>
    <p>The budget for <b>{association_name} ({budget_year})</b> has finished generating and is ready to download.</p>
    <p><a href="{settings.FRONTEND_URL}">Log in to CNS Tools to download</a></p>
    """
    send_email_task.delay(to, f"Budget ready: {association_name} {budget_year}", html)

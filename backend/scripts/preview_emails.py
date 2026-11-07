"""Render every email template to HTML files so the design can be reviewed.

Email HTML can't be checked in the app — it only looks right in a mail client —
and sending real mail to review a wording tweak is slow. This writes each
template to disk with sample data so they can be opened in a browser (close
enough for layout and colour) or pasted into a mail-client previewer.

Usage:

    cd backend && venv/bin/python scripts/preview_emails.py
    cd backend && venv/bin/python scripts/preview_emails.py --out /tmp/mail

Nothing is sent and no database is touched.
"""

import argparse
import sys
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config.settings import settings  # noqa: E402
from app.services.email import tasks  # noqa: E402

SAMPLE_PASSWORD = "Hq7-pLm2Zx4Tv9aQ"
SAMPLE_EMAIL = "dana.reyes@example.com"
SAMPLE_NAME = "Dana"

CASES = {
    "welcome": lambda: tasks.welcome_email(SAMPLE_EMAIL, SAMPLE_NAME, SAMPLE_PASSWORD),
    "reset-password": lambda: tasks.reset_password_email(
        SAMPLE_EMAIL, SAMPLE_NAME, SAMPLE_PASSWORD
    ),
    "password-changed": lambda: tasks.password_changed_email(SAMPLE_EMAIL, SAMPLE_NAME),
    "budget-complete": lambda: tasks.budget_complete_email(
        SAMPLE_EMAIL, SAMPLE_NAME, "Harbor Point Homeowners Association", 2027
    ),
}


class _Capture:
    """Stands in for the Celery task so nothing is queued or sent."""

    def __init__(self):
        self.last: tuple[str, str, str] | None = None

    def delay(self, to: str, subject: str, html: str) -> None:
        self.last = (to, subject, html)


def _index(entries: list[tuple[str, str]]) -> str:
    links = "".join(
        f'<li><a href="{name}.html">{name}</a> '
        f'<span style="color:#5A6A7E">— {subject}</span></li>'
        for name, subject in entries
    )
    return (
        "<!doctype html><meta charset='utf-8'><title>C&amp;S Tools email previews</title>"
        '<body style="font:15px/1.6 system-ui,sans-serif;max-width:720px;'
        'margin:40px auto;padding:0 20px;color:#1A2332">'
        "<h1 style='font-size:22px'>C&amp;S Tools email previews</h1>"
        "<p style='color:#5A6A7E'>Sample data only — nothing was sent.</p>"
        f"<ul>{links}</ul></body>"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "test_data" / "email_previews",
        help="directory to write the HTML files into",
    )
    parser.add_argument("--open", action="store_true", help="open the index in a browser")
    args = parser.parse_args()

    # The templates read FRONTEND_URL / EMAIL_REPLY_TO at render time; stand in
    # for them so a preview doesn't depend on a configured .env.
    settings.FRONTEND_URL = settings.FRONTEND_URL or "https://tools.example.com"
    settings.EMAIL_REPLY_TO = settings.EMAIL_REPLY_TO or "support@example.com"

    capture = _Capture()
    tasks.send_email_task = capture  # type: ignore[assignment]

    args.out.mkdir(parents=True, exist_ok=True)
    entries: list[tuple[str, str]] = []

    for name, build in CASES.items():
        build()
        assert capture.last, f"{name} queued no email"
        _, subject, html = capture.last
        (args.out / f"{name}.html").write_text(html, encoding="utf-8")
        entries.append((name, subject))
        print(f"{name:<18} {subject}")

    index = args.out / "index.html"
    index.write_text(_index(entries), encoding="utf-8")
    print(f"\nWrote {len(entries)} previews to {args.out}")

    if args.open:
        webbrowser.open(index.resolve().as_uri())


if __name__ == "__main__":
    main()

"""Unit tests for the branded email layout and the message bodies built on it.

These assert the properties that break silently in a real inbox — unescaped
user data, an unbalanced table that collapses the layout in Outlook, a missing
temporary password — rather than exact markup, which is expected to change
whenever the design is tweaked.
"""

from html.parser import HTMLParser

import pytest

from app.services.email import layout, tasks

pytestmark = pytest.mark.unit


# ─── Helpers ─────────────────────────────────────────────────────────────────


class _TagBalance(HTMLParser):
    """Collects unbalanced / mismatched tags.

    Email clients are far less forgiving than browsers: an unclosed <table> in
    Outlook swallows everything after it, so balance is worth asserting.
    """

    VOID = {"meta", "br", "img", "hr", "input", "link"}

    def __init__(self):
        super().__init__()
        self.stack: list[str] = []
        self.errors: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in self.VOID:
            return
        if not self.stack:
            self.errors.append(f"stray </{tag}>")
        elif self.stack[-1] != tag:
            self.errors.append(f"</{tag}> closes <{self.stack[-1]}>")
            self.stack.pop()
        else:
            self.stack.pop()


def assert_well_formed(html: str) -> None:
    parser = _TagBalance()
    parser.feed(html)
    assert not parser.errors, parser.errors
    assert not parser.stack, f"unclosed tags: {parser.stack}"


@pytest.fixture
def sent(monkeypatch):
    """Capture the (to, subject, html) a template would queue."""
    captured: list[dict] = []

    class _Capture:
        def delay(self, to, subject, html):
            captured.append({"to": to, "subject": subject, "html": html})

    monkeypatch.setattr(tasks, "send_email_task", _Capture())
    return captured


# ─── Layout ──────────────────────────────────────────────────────────────────


class TestLayout:
    def test_render_produces_a_full_document(self):
        html = layout.render(
            preheader="preview",
            title="Title",
            blocks=[layout.paragraph("Body")],
        )
        assert html.startswith("<!DOCTYPE")
        assert "<title>Title</title>" in html
        assert "Body" in html
        assert_well_formed(html)

    def test_uses_brand_colours_from_the_app_theme(self):
        html = layout.render(preheader="p", title="t", blocks=[layout.button("Go", "https://x")])
        assert layout.NAVY in html
        assert layout.PAGE_BG in html

    def test_styles_are_inline_not_only_in_a_style_block(self):
        """Gmail drops most <style> rules, so layout must survive without it."""
        html = layout.render(preheader="p", title="t", blocks=[layout.paragraph("hi")])
        body = html.split("</head>", 1)[1]
        assert 'style="' in body

    def test_logo_is_a_hosted_image_with_a_usable_fallback(self):
        """Outlook blocks remote images from external senders by default, so
        the header has to survive the image never loading."""
        html = layout.render(preheader="p", title="t", blocks=[])
        assert "email-logo.png" in html
        # Alt text is the fallback, and it must name the company.
        assert 'alt="C&amp;S Community Management Services, Inc."' in html
        # Explicit dimensions so Outlook reserves the right box.
        assert 'width="140"' in html and 'height="92"' in html

    def test_blocked_logo_falls_back_to_styled_alt_text(self):
        """With images off the alt text is all that is left, so it has to read
        as the company name rather than as a broken box."""
        html = layout.render(preheader="p", title="t", blocks=[])
        img = html[html.index("<img") : html.index("/>", html.index("<img"))]
        assert "C&amp;S Community Management Services" in img
        assert layout.NAVY in img
        assert "Georgia" in img

    def test_logo_url_follows_the_configured_frontend(self, monkeypatch):
        monkeypatch.setattr(layout.settings, "FRONTEND_URL", "https://tools.example.com/")
        html = layout.render(preheader="p", title="t", blocks=[])
        # Trailing slash on the setting must not produce a doubled slash.
        assert "https://tools.example.com/email-logo.png" in html

    def test_preheader_is_hidden(self):
        html = layout.render(preheader="secret preview", title="t", blocks=[])
        assert "secret preview" in html
        assert "display:none" in html

    def test_heading_escapes_its_text(self):
        assert "<b>x</b>" not in layout.heading("<b>x</b>")
        assert "&lt;b&gt;" in layout.heading("<b>x</b>")

    def test_credentials_escapes_email_and_password(self):
        html = layout.credentials("a<b>@x.com", "pw&<pw")
        assert "<b>" not in html.replace("<b style", "")
        assert "&lt;b&gt;" in html
        assert "pw&amp;&lt;pw" in html

    def test_button_escapes_the_url(self):
        html = layout.button("Go", 'https://x/?a="b')
        assert '?a="b' not in html
        assert "&quot;" in html

    def test_steps_numbers_sequentially(self):
        html = layout.steps(["one", "two", "three"])
        for n in ("1", "2", "3"):
            assert f">{n}</td>" in html
        assert_well_formed(f"<table>{html}</table>")


# ─── Messages ────────────────────────────────────────────────────────────────


class TestWelcomeEmail:
    def test_includes_credentials_and_a_login_link(self, sent):
        tasks.welcome_email("dana@example.com", "Dana", "Tempor4ry-Pass")
        (mail,) = sent
        assert mail["to"] == "dana@example.com"
        assert "Tempor4ry-Pass" in mail["html"]
        assert "dana@example.com" in mail["html"]
        assert_well_formed(mail["html"])

    def test_reads_as_an_invitation_not_a_reset(self, sent):
        """The whole point of this template: an existing user being onboarded
        must not be told their password was reset."""
        tasks.welcome_email("dana@example.com", "Dana", "pw123456789")
        (mail,) = sent
        assert "Welcome" in mail["subject"]
        assert "reset" not in mail["subject"].lower()
        assert "Welcome, Dana" in mail["html"]

    def test_escapes_the_recipient_name(self, sent):
        tasks.welcome_email("a@b.com", "<script>alert(1)</script>", "pw123456789")
        (mail,) = sent
        assert "<script>" not in mail["html"]
        assert "&lt;script&gt;" in mail["html"]

    def test_escapes_a_password_containing_markup_characters(self, sent):
        tasks.welcome_email("a@b.com", "Dana", "a&b<c>d")
        (mail,) = sent
        assert "a&amp;b&lt;c&gt;d" in mail["html"]
        assert_well_formed(mail["html"])


class TestResetPasswordEmail:
    def test_states_the_previous_password_no_longer_works(self, sent):
        tasks.reset_password_email("dana@example.com", "Dana", "Nuevo-Pass123")
        (mail,) = sent
        assert "reset" in mail["subject"].lower()
        assert "Nuevo-Pass123" in mail["html"]
        assert "no longer works" in mail["html"]
        assert_well_formed(mail["html"])

    def test_escapes_the_recipient_name(self, sent):
        tasks.reset_password_email("a@b.com", "<i>Dana</i>", "pw123456789")
        (mail,) = sent
        assert "<i>Dana</i>" not in mail["html"]


class TestOtherEmails:
    def test_password_changed_has_no_credentials(self, sent):
        tasks.password_changed_email("dana@example.com", "Dana")
        (mail,) = sent
        assert "Temporary password" not in mail["html"]
        assert_well_formed(mail["html"])

    def test_budget_complete_names_the_association_and_year(self, sent):
        tasks.budget_complete_email("dana@example.com", "Dana", "Harbor Point", 2027)
        (mail,) = sent
        assert "Harbor Point" in mail["subject"]
        assert "2027" in mail["html"]
        assert_well_formed(mail["html"])

    def test_budget_complete_escapes_the_association_name(self, sent):
        tasks.budget_complete_email("a@b.com", "Dana", "Smith & Jones <HOA>", 2027)
        (mail,) = sent
        assert "<HOA>" not in mail["html"]
        assert "Smith &amp; Jones &lt;HOA&gt;" in mail["html"]
        assert_well_formed(mail["html"])

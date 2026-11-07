"""Branded HTML layout for outgoing email.

Email clients are not browsers: Gmail strips most <style> rules, Outlook renders
through Word, and SVG/flexbox/grid are unavailable. So everything here is nested
tables with inline styles, which is the only thing that renders consistently.
The <style> block carries progressive enhancement only (mobile stacking) — the
layout must still be correct without it.

Brand colours mirror frontend/src/theme.ts so mail matches the app.
"""

from html import escape

from app.config.settings import settings

# ─── Brand tokens (keep in sync with frontend/src/theme.ts) ──────────────────

NAVY = "#13294B"
NAVY_DARK = "#0B1A33"
GOLD = "#C9A227"
GOLD_DARK = "#9A7B16"
PAGE_BG = "#F5F7FA"
CARD_BG = "#FFFFFF"
BORDER = "#E3E7EE"
TEXT = "#16202E"
TEXT_MUTED = "#5A6A7E"
WARN_BG = "#FDF6E3"
WARN_BORDER = GOLD

FONT = (
    "-apple-system,BlinkMacSystemFont,'Segoe UI',Inter,Roboto," "'Helvetica Neue',Arial,sans-serif"
)
# Matches the logo's letterforms, used for the mark and the headline only.
SERIF = "Georgia,'Times New Roman',serif"
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"

PRODUCT_NAME = "C&S Tools"
COMPANY_NAME = "C&S Community Management Services, Inc."


# ─── Body blocks ─────────────────────────────────────────────────────────────


def paragraph(html: str, muted: bool = False) -> str:
    """A body paragraph. `html` is inserted as-is — escape caller data first."""
    color = TEXT_MUTED if muted else TEXT
    size = "14px" if muted else "15px"
    return (
        f'<p style="margin:0 0 16px;font-family:{FONT};font-size:{size};'
        f'line-height:1.6;color:{color};">{html}</p>'
    )


def heading(text: str) -> str:
    return (
        f'<h1 style="margin:0 0 16px;font-family:{SERIF};font-size:24px;'
        f"line-height:1.3;font-weight:700;letter-spacing:-0.2px;"
        f'color:{NAVY};">{escape(text)}</h1>'
    )


def credentials(email: str, temp_password: str) -> str:
    """Email + temporary password in a bordered panel.

    The password is monospaced so look-alike characters in the generated token
    (l/1/I, O/0) stay distinguishable when someone retypes it.
    """
    rows = [
        ("Email", f'<span style="color:{TEXT};">{escape(email)}</span>'),
        (
            "Temporary password",
            f'<span style="font-family:{MONO};font-size:15px;font-weight:600;'
            f'color:{NAVY};letter-spacing:0.3px;word-break:break-all;">'
            f"{escape(temp_password)}</span>",
        ),
    ]
    cells = ""
    for i, (label, value) in enumerate(rows):
        pad = "0 0 10px" if i == 0 else "0"
        cells += (
            f'<tr><td width="40%" valign="top" style="padding:{pad};'
            f"font-family:{FONT};font-size:12px;font-weight:600;"
            f"text-transform:uppercase;letter-spacing:0.6px;"
            f'color:{TEXT_MUTED};">{label}</td>'
            f'<td valign="top" style="padding:{pad};font-family:{FONT};'
            f'font-size:14px;line-height:1.5;">{value}</td></tr>'
        )
    return (
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
        f'width="100%" style="margin:0 0 20px;background:{PAGE_BG};'
        f'border:1px solid {BORDER};border-radius:8px;">'
        f'<tr><td style="padding:18px 20px;">'
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
        f'width="100%">{cells}</table>'
        f"</td></tr></table>"
    )


def button(label: str, url: str) -> str:
    """A CTA button. The padded, coloured table cell is what Outlook honours."""
    return (
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
        f'style="margin:0 0 20px;"><tr>'
        f'<td align="center" bgcolor="{NAVY}" style="border-radius:8px;">'
        f'<a href="{escape(url, quote=True)}" '
        f'style="display:inline-block;padding:13px 28px;font-family:{FONT};'
        f"font-size:15px;font-weight:600;line-height:1;color:#ffffff;"
        f'text-decoration:none;border-radius:8px;">{escape(label)}</a>'
        f"</td></tr></table>"
    )


def callout(html: str) -> str:
    """An amber-ruled note for the one thing the reader must not miss."""
    return (
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
        f'width="100%" style="margin:0 0 20px;background:{WARN_BG};'
        f'border-left:3px solid {WARN_BORDER};border-radius:4px;">'
        f'<tr><td style="padding:14px 16px;font-family:{FONT};font-size:14px;'
        f'line-height:1.55;color:{TEXT};">{html}</td></tr></table>'
    )


def steps(items: list[str]) -> str:
    """A numbered list, as a table — <ol> indentation is unreliable in Outlook."""
    rows = ""
    for i, item in enumerate(items, start=1):
        rows += (
            f'<tr><td width="28" valign="top" style="padding:0 0 12px;">'
            f'<table role="presentation" cellpadding="0" cellspacing="0" '
            f'border="0"><tr><td width="20" height="20" align="center" '
            f'bgcolor="{GOLD}" style="border-radius:10px;font-family:{FONT};'
            f'font-size:11px;font-weight:700;color:{NAVY_DARK};line-height:20px;">'
            f"{i}</td></tr></table></td>"
            f'<td valign="top" style="padding:0 0 12px;font-family:{FONT};'
            f'font-size:14px;line-height:1.5;color:{TEXT};">{item}</td></tr>'
        )
    return (
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
        f'width="100%" style="margin:0 0 20px;">{rows}</table>'
    )


# ─── Shell ───────────────────────────────────────────────────────────────────


def _logo_mark() -> str:
    """The C&S lockup rebuilt as styled text.

    The app renders the real PNG, but email can't: Gmail strips data: URIs on
    images and every client lets the recipient block remote ones, so a hosted
    logo is a logo that is often simply absent. Three table cells of serif
    text reproduce the mark's structure — navy letterforms, gold ampersand —
    with nothing left to fetch.
    """
    # The three letters live in their own nested table so they stay tight.
    # Put them in sibling cells of the wordmark's row and the wider wordmark
    # stretches the row, pushing C, & and S apart.
    letters = (
        f'<td valign="bottom" style="font-family:{SERIF};font-size:36px;'
        f'font-weight:700;color:{NAVY};line-height:1;">C</td>'
        f'<td valign="bottom" style="font-family:{SERIF};font-size:34px;'
        f'font-style:italic;font-weight:700;color:{GOLD};line-height:1;">&amp;</td>'
        f'<td valign="bottom" style="font-family:{SERIF};font-size:36px;'
        f'font-weight:700;color:{NAVY};line-height:1;">S</td>'
    )
    mark = (
        f'<table role="presentation" cellpadding="0" cellspacing="0" '
        f'border="0"><tr>{letters}</tr></table>'
    )
    return (
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0">'
        f'<tr><td align="center" style="padding:0 0 2px;">{mark}</td></tr>'
        f'<tr><td align="center" style="font-family:{SERIF};font-size:8px;'
        f"font-weight:600;letter-spacing:1.1px;color:{NAVY};"
        f'white-space:nowrap;">COMMUNITY MANAGEMENT SERVICES</td></tr>'
        f'<tr><td style="padding:5px 0 0;font-size:0;line-height:0;">'
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
        f'width="100%"><tr><td height="2" bgcolor="{GOLD}" '
        f'style="font-size:0;line-height:0;">&nbsp;</td></tr></table></td></tr>'
        f"</table>"
    )


def _preheader(text: str) -> str:
    """Inbox preview text, hidden in the body.

    The trailing invisible characters stop clients from padding the preview with
    whatever markup happens to follow.
    """
    filler = "&nbsp;&zwnj;" * 30
    return (
        f'<div style="display:none;font-size:1px;line-height:1px;max-height:0;'
        f'max-width:0;opacity:0;overflow:hidden;mso-hide:all;">'
        f"{escape(text)}{filler}</div>"
    )


def _footer_contact() -> str:
    if settings.EMAIL_REPLY_TO:
        addr = settings.EMAIL_REPLY_TO
        return (
            f"Questions? Reply to this email or contact "
            f'<a href="mailto:{escape(addr, quote=True)}" '
            f'style="color:{NAVY};text-decoration:underline;">'
            f"{escape(addr)}</a>."
        )
    return "Questions? Reply to this email and we'll help."


def render(
    *,
    preheader: str,
    title: str,
    blocks: list[str],
    footer_note: str | None = None,
) -> str:
    """Wrap body `blocks` in the branded shell and return a full HTML document."""
    body = "".join(blocks)
    note = (
        f'<p style="margin:0 0 10px;font-family:{FONT};font-size:12px;'
        f'line-height:1.5;color:{TEXT_MUTED};">{footer_note}</p>'
        if footer_note
        else ""
    )

    return f"""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<meta name="x-apple-disable-message-reformatting" />
<meta name="color-scheme" content="light" />
<meta name="supported-color-schemes" content="light" />
<title>{escape(title)}</title>
<style type="text/css">
  /* Progressive enhancement only - inline styles carry the layout. */
  body {{ margin:0; padding:0; width:100% !important; -webkit-text-size-adjust:100%; }}
  table {{ border-collapse:collapse !important; }}
  a {{ color:{NAVY}; }}
  @media only screen and (max-width:620px) {{
    .wrap {{ width:100% !important; }}
    .pad {{ padding-left:22px !important; padding-right:22px !important; }}
  }}
</style>
</head>
<body style="margin:0;padding:0;background:{PAGE_BG};">
{_preheader(preheader)}
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background:{PAGE_BG};">
  <tr>
    <td align="center" style="padding:28px 12px;">
      <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="600" class="wrap" style="width:600px;max-width:600px;">

        <tr>
          <td align="left" style="padding:0 0 18px;">{_logo_mark()}</td>
        </tr>

        <tr>
          <td style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;">
            <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
              <tr>
                <td height="4" bgcolor="{NAVY}" style="font-size:0;line-height:0;border-radius:10px 10px 0 0;">&nbsp;</td>
              </tr>
              <tr>
                <td class="pad" style="padding:32px 36px 14px;">{body}</td>
              </tr>
            </table>
          </td>
        </tr>

        <tr>
          <td class="pad" style="padding:22px 36px 0;">
            {note}
            <p style="margin:0 0 10px;font-family:{FONT};font-size:12px;line-height:1.5;color:{TEXT_MUTED};">
              {_footer_contact()}
            </p>
            <p style="margin:0;font-family:{FONT};font-size:12px;line-height:1.5;color:{TEXT_MUTED};">
              {escape(PRODUCT_NAME)} &middot; {escape(COMPANY_NAME)}
            </p>
          </td>
        </tr>

      </table>
    </td>
  </tr>
</table>
</body>
</html>"""

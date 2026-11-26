"""OCR for PDF pages that have no text layer.

Some reports arrive as "Microsoft Print to PDF" output, where every letter
is drawn as vector shapes, or as scans that were never OCR'd. Those pages
have nothing for pdfplumber to read, so they're rendered to an image and
read with Tesseract (a local OCR engine — no network, no LLM). Its word
boxes are converted to PDF points so the rest of the pipeline treats the
page exactly like one with a text layer.

Tesseract is a system binary (``apt-get install tesseract-ocr``, see the
Dockerfile). If it isn't installed, pages without text stay empty and
callers report "no readable text" instead of failing.
"""

from __future__ import annotations

import csv
import io
import logging
import os
import re
import shutil
import subprocess

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c
from PIL import ImageDraw

from .pdf import BBox, Word

logger = logging.getLogger(__name__)

# 300 dpi is Tesseract's sweet spot for ~9pt report text.
OCR_DPI = 300
_SCALE = 72 / OCR_DPI
# Words Tesseract is less sure of than this are dropped (0-100).
MIN_CONFIDENCE = 30
# ...except a well-formed money amount, kept down to this. Bold report
# totals ("-1,385.84" under its underline) often score in the 20s, and the
# reports' own arithmetic checks any figure that's misread.
MIN_AMOUNT_CONFIDENCE = 10
_AMOUNT_TOKEN = re.compile(r"[=\-(“\"$]*\d{1,3}(?:,\d{3})*[.,]\d{2}\)?")
TIMEOUT_S = 45

# Horizontal rules (column-header underlines, total underlines) are painted
# out before OCR: Tesseract tends to drop a line of text that sits right on
# one (the AR report's "Count:" line under its header rule).
_RULE_MIN_WIDTH = 20  # points
_RULE_MAX_HEIGHT = 3


def ocr_available() -> bool:
    return shutil.which("tesseract") is not None


def _erase_rules(page: pdfium.PdfPage, img) -> None:
    """Paint over the page's drawn horizontal lines. Only vector pages
    (printed to PDF) have these; a scan's lines are pixels and stay."""
    scale = OCR_DPI / 72
    height = page.get_size()[1]
    draw = ImageDraw.Draw(img)
    for obj in page.get_objects(filter=(pdfium_c.FPDF_PAGEOBJ_PATH,)):
        left, bottom, right, top = obj.get_bounds()  # PDF space: y grows upwards
        if right - left < _RULE_MIN_WIDTH or top - bottom > _RULE_MAX_HEIGHT:
            continue
        draw.rectangle(
            [
                left * scale - 2,
                (height - top) * scale - 2,
                right * scale + 2,
                (height - bottom) * scale + 2,
            ],
            fill=255,
        )


def render_for_ocr(page: pdfium.PdfPage) -> bytes:
    """The page as a greyscale PNG ready for Tesseract, rules painted out.
    pdfium isn't thread-safe: call this from the thread that owns the PDF."""
    img = page.render(scale=OCR_DPI / 72, grayscale=True).to_pil().convert("L")
    _erase_rules(page, img)
    buf = io.BytesIO()
    img.save(buf, format="PNG", compress_level=1)
    return buf.getvalue()


def read_image(png: bytes, page_number: int = 0, single_thread: bool = False) -> list[Word] | None:
    """Run Tesseract on a rendered page. Safe to call from worker threads
    (it's a subprocess); ``single_thread`` stops each Tesseract spreading
    over every core when several pages are read at once."""
    env = {**os.environ, "OMP_THREAD_LIMIT": "1"} if single_thread else None
    try:
        # psm 6: one uniform block of text — keeps a report's rows together.
        proc = subprocess.run(
            ["tesseract", "stdin", "stdout", "--psm", "6", "tsv"],
            input=png,
            capture_output=True,
            timeout=TIMEOUT_S,
            check=True,
            env=env,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        logger.warning("OCR failed on page %s: %s", page_number, exc)
        return None

    words: list[Word] = []
    reader = csv.DictReader(
        io.StringIO(proc.stdout.decode("utf-8", "replace")),
        delimiter="\t",
        quoting=csv.QUOTE_NONE,
    )
    for row in reader:
        text = (row.get("text") or "").strip()
        try:
            conf = float(row.get("conf") or -1)
            left, top = int(row["left"]), int(row["top"])
            width, height = int(row["width"]), int(row["height"])
        except (KeyError, ValueError):
            continue
        if not text or conf < MIN_AMOUNT_CONFIDENCE:
            continue
        if conf < MIN_CONFIDENCE and not _AMOUNT_TOKEN.fullmatch(text):
            continue
        words.append(
            Word(
                text,
                BBox(
                    left * _SCALE,
                    top * _SCALE,
                    (left + width) * _SCALE,
                    (top + height) * _SCALE,
                ),
            )
        )
    return words

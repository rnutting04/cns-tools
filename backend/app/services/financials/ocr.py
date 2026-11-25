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
import shutil
import subprocess

from .pdf import BBox, Word

logger = logging.getLogger(__name__)

# 300 dpi is Tesseract's sweet spot for ~9pt report text.
OCR_DPI = 300
_SCALE = 72 / OCR_DPI
# Words Tesseract is less sure of than this are dropped (0-100).
MIN_CONFIDENCE = 30
TIMEOUT_S = 45


def ocr_available() -> bool:
    return shutil.which("tesseract") is not None


def ocr_page(pdfplumber_page) -> list[Word] | None:
    """Words on the page with boxes in PDF points, or None if OCR is unavailable."""
    if not ocr_available():
        return None
    img = pdfplumber_page.to_image(resolution=OCR_DPI).original.convert("L")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    try:
        # psm 6: one uniform block of text — keeps a report's rows together.
        proc = subprocess.run(
            ["tesseract", "stdin", "stdout", "--psm", "6", "tsv"],
            input=buf.getvalue(),
            capture_output=True,
            timeout=TIMEOUT_S,
            check=True,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        logger.warning("OCR failed on page %s: %s", pdfplumber_page.page_number, exc)
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
        if not text or conf < MIN_CONFIDENCE:
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

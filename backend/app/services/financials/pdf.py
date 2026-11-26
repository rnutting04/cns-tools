"""PDF text geometry for scanned-and-OCR'd monthly financial packets.

The packets are scans with an OCR text layer, so the text is *mostly* right
but the layout is not trustworthy: amounts drift a few points above or below
their label row, adjacent numbers fuse (``7,855.597,499.70``), and words get
glued together (``G/LBalance``). Everything here works from word bounding
boxes rather than from the OCR's own line order, and every value keeps the
box it came from so a human can be shown exactly where it was read.
"""

from __future__ import annotations

import io
import re
from collections import deque
from collections.abc import Iterator
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import BinaryIO

import pdfplumber
import pypdfium2 as pdfium
from pdfminer.pdfparser import PDFSyntaxError
from pdfplumber.utils.exceptions import PdfminerException

# Raised for a file that isn't a readable PDF (by pdfium or pdfplumber).
PDF_ERRORS = (pdfium.PdfiumError, PdfminerException, PDFSyntaxError, ValueError)

# A money amount with exactly two decimals. The lookahead rejects
# percentages and longer decimals ("2.95%", "1.00000").
_AMOUNT_RE = re.compile(r"\d{1,3}(?:,\d{3})*\.\d{2}(?![\d%])")
# OCR sometimes fuses neighbouring columns into one token: "7,855.597,499.70"
# is 7,855.59 + 7,499.70. Exactly-two-decimals makes the split unambiguous.
_ONE = r"\d{1,3}(?:,\d{3})*\.\d{2}"
_FUSED_RE = re.compile(rf"(?:{_ONE}){{2,}}")
# Whole-dollar amounts (insurance schedule). Requires a thousands separator
# or a bare 1-3 digit number so GL codes / years are not picked up.
_WHOLE_RE = re.compile(r"(?<![\d.,/])\d{1,3}(?:,\d{3})*(?![\d.,/%])")


@dataclass(frozen=True)
class BBox:
    x0: float
    top: float
    x1: float
    bottom: float

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def cy(self) -> float:
        return (self.top + self.bottom) / 2

    def union(self, other: BBox) -> BBox:
        return BBox(
            min(self.x0, other.x0),
            min(self.top, other.top),
            max(self.x1, other.x1),
            max(self.bottom, other.bottom),
        )

    @staticmethod
    def union_all(boxes: list[BBox]) -> BBox:
        out = boxes[0]
        for b in boxes[1:]:
            out = out.union(b)
        return out


@dataclass
class Word:
    text: str
    bbox: BBox


@dataclass
class Line:
    words: list[Word]

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)

    @property
    def bbox(self) -> BBox:
        return BBox.union_all([w.bbox for w in self.words])

    @property
    def key(self) -> str:
        """Letters-only lowercase form, immune to OCR spacing ("TOTALREVENUES")."""
        return squash(self.text)


@dataclass
class Page:
    number: int  # 1-based
    width: float
    height: float
    words: list[Word]
    lines: list[Line] = field(default_factory=list)
    # Scan tilt as dy/dx (negative = rows rise to the right). Word boxes keep
    # their true page position (so highlights land on the scan); only row
    # matching uses the levelled position from ``level``.
    skew: float = 0.0
    # Words came from our own OCR (the PDF had no text layer on this page).
    ocr: bool = False

    def level(self, b: BBox) -> float:
        """Vertical centre of ``b`` with the scan's tilt taken out."""
        return b.cy - self.skew * b.cx

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines)

    def header_key(self, n_lines: int = 6) -> str:
        return squash(" ".join(line.text for line in self.lines[:n_lines]))

    def header_words(self, n_lines: int = 6) -> set[str]:
        return {squash(w.text) for line in self.lines[:n_lines] for w in line.words} - {""}


def squash(s: str) -> str:
    return re.sub(r"[^a-z]", "", s.lower())


# OCR look-alikes inside a number: "§2,511.92" is 52,511.92, "1O0.00" is 100.00.
_LOOKALIKE = str.maketrans({"§": "5", "O": "0", "o": "0", "l": "1", "I": "1", "|": "1"})
_LOOKALIKE_CHARS = set("§OolI|")
_AMOUNT_FULL = re.compile(r"\d{1,3}(?:,\d{3})*\.\d{2}")
# OCR read the decimal point as a comma: "268,27", "0,00".
_COMMA_DECIMAL = re.compile(r"\d{1,3}(?:,\d{3})*,\d{2}")


def _repair_amount_token(token: str) -> str:
    """Fix OCR character slips in a token that is otherwise a money amount.
    Only applied when the repaired text is a valid amount, so words and
    codes are left alone."""
    # "=" and quote marks are OCR's reading of a minus sign.
    lead = len(token) - len(token.lstrip('(-$=“"'))
    trail = len(token) - len(token.rstrip(")"))
    core = token[lead : len(token) - trail]
    if not core:
        return token
    fixed = core
    # A stray comma before the decimal point: "61,905,.32".
    if ",." in fixed and _AMOUNT_FULL.fullmatch(fixed.replace(",.", ".")):
        fixed = fixed.replace(",.", ".")
    if _LOOKALIKE_CHARS & set(fixed) and sum(c.isdigit() for c in fixed) >= 3:
        candidate = fixed.translate(_LOOKALIKE)
        if _AMOUNT_FULL.fullmatch(candidate) or _COMMA_DECIMAL.fullmatch(candidate):
            fixed = candidate
    if _COMMA_DECIMAL.fullmatch(fixed):
        fixed = fixed[:-3] + "." + fixed[-2:]
    return token[:lead] + fixed + token[len(token) - trail :]


def parse_amounts(text: str) -> list[Decimal]:
    """Every two-decimal amount in ``text``, signed. ``(1.00)`` and ``-1.00`` are negative."""
    out: list[Decimal] = []
    for token in text.split():
        token = _repair_amount_token(token)
        core = token.strip("()-$|")
        if _FUSED_RE.fullmatch(core):
            matches = list(re.finditer(_ONE, token))
        else:
            matches = list(_AMOUNT_RE.finditer(token))
        for m in matches:
            value = Decimal(m.group().replace(",", ""))
            before = token[max(0, m.start() - 2) : m.start()]
            if "(" in before or before.endswith("-"):
                value = -value
            out.append(value)
    return out


def parse_whole_amounts(text: str) -> list[Decimal]:
    return [Decimal(m.group().replace(",", "")) for m in _WHOLE_RE.finditer(text)]


def group_lines(words: list[Word], tolerance: float = 3.5, skew: float = 0.0) -> list[Line]:
    """Cluster words into visual lines by vertical center, levelled for ``skew``."""

    def y(w: Word) -> float:
        return w.bbox.cy - skew * w.bbox.cx

    lines: list[list[Word]] = []
    centers: list[float] = []
    for w in sorted(words, key=lambda w: (y(w), w.bbox.x0)):
        if lines and abs(y(w) - centers[-1]) <= tolerance:
            lines[-1].append(w)
            n = len(lines[-1])
            centers[-1] += (y(w) - centers[-1]) / n
        else:
            lines.append([w])
            centers.append(y(w))
    return [Line(sorted(ws, key=lambda w: w.bbox.x0)) for ws in lines]


# Below this the tilt moves a word under ~1pt across the page: leave it alone.
MIN_SKEW = 0.002


def estimate_skew(lines: list[Line]) -> float:
    """Page tilt (dy/dx) from the rows of figures that already grouped.

    Each line with 4+ amounts spread across the page gives a least-squares
    slope; the median ignores the odd row OCR mangled. Even on a tilted
    page the short runs of figures still group, so there are enough samples.
    """
    slopes: list[float] = []
    for ln in lines:
        ws = [w for w in ln.words if _AMOUNT_RE.search(w.text)]
        if len(ws) < 4 or ws[-1].bbox.cx - ws[0].bbox.cx < 200:
            continue
        xs = [w.bbox.cx for w in ws]
        ys = [w.bbox.cy for w in ws]
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        slopes.append(
            sum((x - mx) * (yy - my) for x, yy in zip(xs, ys, strict=True))
            / sum((x - mx) ** 2 for x in xs)
        )
    if len(slopes) < 3:
        return 0.0
    slopes.sort()
    return slopes[len(slopes) // 2]


# OCR takes ~0.7-2.5s a page; this keeps a web request well inside
# gunicorn's 60s timeout even for a document that is entirely image/vector
# pages. Background jobs pass no limit.
MAX_OCR_PAGES = 12

# A number OCR split at its thousands separator: "388," + "748.91",
# "28" + "843.36", "(1" + "234.56)".
_SPLIT_HEAD = re.compile(r"^\(?-?\$?\d{1,3}(?:,\d{3})*,?$")
_SPLIT_TAIL = re.compile(r"^\d{3}(?:,\d{3})*\.\d{2}\)?$")
_SPLIT_GAP = 6.0  # points; real columns are 20+ apart


def merge_split_numbers(words: list[Word]) -> list[Word]:
    """Rejoin amounts OCR broke at a thousands separator into one word."""
    out = sorted(words, key=lambda w: (round(w.bbox.cy), w.bbox.x0))
    merged = True
    while merged:
        merged = False
        for i, head in enumerate(out):
            if not _SPLIT_HEAD.match(head.text):
                continue
            for j, tail in enumerate(out):
                if (
                    j != i
                    and _SPLIT_TAIL.match(tail.text)
                    and abs(tail.bbox.cy - head.bbox.cy) < 3
                    and 0 <= tail.bbox.x0 - head.bbox.x1 <= _SPLIT_GAP
                ):
                    text = head.text.rstrip(",") + "," + tail.text
                    out[i] = Word(text, head.bbox.union(tail.bbox))
                    del out[j]
                    merged = True
                    break
            if merged:
                break
    return out


def build_page(
    number: int, width: float, height: float, words: list[Word], ocr: bool = False
) -> Page:
    """A Page from words: repair split numbers, group lines, take out tilt."""
    words = merge_split_numbers(words)
    page = Page(number=number, width=width, height=height, words=words)
    page.ocr = ocr
    page.lines = group_lines(words)
    skew = estimate_skew(page.lines)
    if abs(skew) >= MIN_SKEW:
        # A tilted scan: figures on the right of a row drift onto the row
        # above/below. Regroup with the tilt taken out.
        page.skew = skew
        page.lines = group_lines(words, skew=skew)
    return page


def iter_pages(
    source: str | Path | BinaryIO,
    max_ocr_pages: int | None = MAX_OCR_PAGES,
    ocr_workers: int = 1,
) -> Iterator[Page]:
    """Pages one at a time, in order. A page with no text layer (printed-to-
    PDF vector text, or an un-OCR'd scan) is read with Tesseract when it's
    installed, up to ``max_ocr_pages`` (None = no limit); ``Page.ocr`` marks
    those. ``ocr_workers`` > 1 reads that many pages with Tesseract at once
    (background jobs: a combined file is hundreds of OCR pages)."""
    # Local import: ocr imports this module.
    from .ocr import ocr_available, read_image, render_for_ocr

    can_ocr = ocr_available()
    budget = max_ocr_pages
    parallel = ocr_workers > 1
    # (number, width, height, words, OCR future or None), oldest first
    pending: deque[tuple[int, float, float, list[Word], Future | None]] = deque()

    def finish(item) -> Page:
        number, width, height, words, fut = item
        if fut is None:
            return build_page(number, width, height, words)
        ocr_words = fut.result() or []
        return build_page(number, width, height, ocr_words, bool(ocr_words))

    # pdfplumber and pdfium each get their own copy of a stream, so their
    # reads can't move each other's file position.
    if not isinstance(source, str | Path):
        source = source.read()
    doc = pdfium.PdfDocument(source)
    try:
        with (
            pdfplumber.open(io.BytesIO(source) if isinstance(source, bytes) else source) as pdf,
            ThreadPoolExecutor(max_workers=max(ocr_workers, 1)) as pool,
        ):
            for i, pg in enumerate(pdf.pages, start=1):
                fpage = doc[i - 1]
                # pdfium answers "is there any text?" in microseconds; pdfplumber
                # would parse every glyph outline of a printed-to-PDF page
                # (up to a second) to find none.
                textpage = fpage.get_textpage()
                has_text = textpage.count_chars() > 0
                textpage.close()
                words = (
                    [
                        Word(w["text"], BBox(w["x0"], w["top"], w["x1"], w["bottom"]))
                        for w in pg.extract_words(keep_blank_chars=False, use_text_flow=False)
                    ]
                    if has_text
                    else []
                )
                fut: Future | None = None
                if not words and can_ocr and (budget is None or budget > 0):
                    if budget is not None:
                        budget -= 1
                    # Rendering stays on this thread (pdfium isn't thread-
                    # safe); only Tesseract itself runs in the pool.
                    fut = pool.submit(read_image, render_for_ocr(fpage), i, parallel)
                fpage.close()
                width, height = float(pg.width), float(pg.height)
                # Free pdfplumber's per-page cache: a combined file is 500+ pages.
                pg.close()
                pending.append((i, width, height, words, fut))
                # Keep up to ``ocr_workers`` pages in flight; hand back the rest.
                while pending and (
                    pending[0][4] is None or pending[0][4].done() or len(pending) > ocr_workers
                ):
                    yield finish(pending.popleft())
            while pending:
                yield finish(pending.popleft())
    finally:
        doc.close()


def page_count(source: str | Path | BinaryIO) -> int:
    with pdfplumber.open(source) as pdf:
        return len(pdf.pages)


def load_pages(source: str | Path | BinaryIO, ocr: bool = True) -> list[Page]:
    """All pages (see ``iter_pages``); ``ocr=False`` skips OCR entirely."""
    return list(iter_pages(source, MAX_OCR_PAGES if ocr else 0))

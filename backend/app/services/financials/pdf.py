"""PDF text geometry for scanned-and-OCR'd monthly financial packets.

The packets are scans with an OCR text layer, so the text is *mostly* right
but the layout is not trustworthy: amounts drift a few points above or below
their label row, adjacent numbers fuse (``7,855.597,499.70``), and words get
glued together (``G/LBalance``). Everything here works from word bounding
boxes rather than from the OCR's own line order, and every value keeps the
box it came from so a human can be shown exactly where it was read.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import BinaryIO

import pdfplumber

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


def parse_amounts(text: str) -> list[Decimal]:
    """Every two-decimal amount in ``text``, signed. ``(1.00)`` and ``-1.00`` are negative."""
    out: list[Decimal] = []
    for token in text.split():
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


def load_pages(source: str | Path | BinaryIO) -> list[Page]:
    pages: list[Page] = []
    with pdfplumber.open(source) as pdf:
        for i, pg in enumerate(pdf.pages, start=1):
            words = [
                Word(w["text"], BBox(w["x0"], w["top"], w["x1"], w["bottom"]))
                for w in pg.extract_words(keep_blank_chars=False, use_text_flow=False)
            ]
            page = Page(number=i, width=float(pg.width), height=float(pg.height), words=words)
            page.lines = group_lines(words)
            skew = estimate_skew(page.lines)
            if abs(skew) >= MIN_SKEW:
                # A tilted scan: figures on the right of a row drift onto the
                # row above/below. Regroup with the tilt taken out.
                page.skew = skew
                page.lines = group_lines(words, skew=skew)
            pages.append(page)
    return pages

"""Render the region of a PDF page a figure was read from, highlighted.

This is the human fallback: when a check is ``review`` (or the reviewer just
wants to see it), show the strip of the scan the number came from.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import BinaryIO

import pdfplumber
from PIL import Image, ImageDraw

from .pdf import BBox

RESOLUTION = 110
_SCALE = RESOLUTION / 72


class CropRenderer:
    """Renders highlighted strips, rasterizing each page at most once.

    A packet yields ~30 crops spread over a handful of pages; re-rendering a
    scanned page per crop would dominate request time.
    """

    def __init__(self, source: str | Path | BinaryIO):
        self._pdf = pdfplumber.open(source)
        self._pages: dict[int, Image.Image] = {}

    def __enter__(self) -> CropRenderer:
        return self

    def __exit__(self, *exc: object) -> None:
        self._pdf.close()

    def _page(self, number: int) -> Image.Image:
        if number not in self._pages:
            pg = self._pdf.pages[number - 1]
            self._pages[number] = pg.to_image(resolution=RESOLUTION).original.convert("RGB")
        return self._pages[number]

    def crop(self, page_number: int, bbox: BBox, pad: float = 28, fmt: str = "PNG") -> bytes:
        """A full-width strip around ``bbox`` with the box outlined."""
        img = self._page(page_number).copy()
        draw = ImageDraw.Draw(img, "RGBA")
        draw.rectangle(
            [
                (bbox.x0 - 3) * _SCALE,
                (bbox.top - 2) * _SCALE,
                (bbox.x1 + 3) * _SCALE,
                (bbox.bottom + 2) * _SCALE,
            ],
            outline=(220, 38, 38, 255),
            fill=(250, 204, 21, 70),
            width=2,
        )
        top = max(0, int((bbox.top - pad) * _SCALE))
        bottom = min(img.height, int((bbox.bottom + pad) * _SCALE))
        buf = io.BytesIO()
        img.crop((0, top, img.width, bottom)).save(buf, format=fmt, optimize=True)
        return buf.getvalue()


def render_crop(
    source: str | Path | BinaryIO, page_number: int, bbox: BBox, pad: float = 28
) -> bytes:
    with CropRenderer(source) as r:
        return r.crop(page_number, bbox, pad)

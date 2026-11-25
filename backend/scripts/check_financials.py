"""Run the month-end reconciliation checks on one or more financial packets.

    ./venv/bin/python -m scripts.check_financials "test_data/MOR September 2026.pdf" --html out.html

Prints a table per packet; ``--html`` also writes a review page with the
highlighted source region for every figure.
"""

from __future__ import annotations

import argparse
import base64
import html
from pathlib import Path

from app.services.financials import Status, check_packet
from app.services.financials.checks import Side
from app.services.financials.evidence import render_crop

ICON = {
    Status.PASS: "PASS",
    Status.FAIL: "FAIL",
    Status.REVIEW: "REVIEW",
    Status.MISSING: "MISSING",
    Status.NOT_APPLICABLE: "n/a",
}


def _fmt(v) -> str:
    return "—" if v is None else f"{v:,.2f}"


def _side_html(pdf: Path, side: Side | None) -> str:
    if side is None:
        return "<td>—</td>"
    img = ""
    if side.page and side.bbox:
        png = base64.b64encode(render_crop(pdf, side.page, side.bbox)).decode()
        img = f'<img src="data:image/png;base64,{png}">'
    ver = {True: "verified", False: "OCR doubt", None: ""}[side.verified]
    page = f"p.{side.page}" if side.page else ""
    return (
        f"<td><b>{_fmt(side.amount)}</b> <small>{html.escape(side.source)} {page} {ver}</small>"
        f"<br><small>{html.escape(side.label)}</small>{img}</td>"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdfs", nargs="+", type=Path)
    ap.add_argument("--html", type=Path)
    args = ap.parse_args()

    sections = []
    for pdf in args.pdfs:
        packet, results = check_packet(pdf)
        print(f"\n== {pdf.name}")
        for r in results:
            left = _fmt(r.left.amount) if r.left else "—"
            right = _fmt(r.right.amount) if r.right else "—"
            print(f"  {ICON[r.status]:8} {r.title:58} {left:>15} {right:>15}  {' '.join(r.notes)}")
        bad = [i for p in [packet.balance_sheet] if p for i in p.identities if not i.ok]
        for i in bad:
            print(f"  ! balance sheet identity failed: {i.description}")

        if args.html:
            rows = "".join(
                f'<tr class="{r.status}"><td class="st">{ICON[r.status]}</td><td>{html.escape(r.title)}'
                f"<br><small>{html.escape(' '.join(r.notes))}</small></td>"
                f"{_side_html(pdf, r.left)}{_side_html(pdf, r.right)}</tr>"
                for r in results
            )
            sections.append(f"<h2>{html.escape(pdf.name)}</h2><table>{rows}</table>")

    if args.html:
        args.html.write_text(
            "<!doctype html><meta charset=utf-8><title>Financial checks</title><style>"
            "body{font:14px system-ui;margin:24px}table{border-collapse:collapse;width:100%}"
            "td{border-top:1px solid #ddd;padding:8px;vertical-align:top;width:40%}"
            "td.st{width:70px;font-weight:700}td:nth-child(2){width:20%}"
            "img{display:block;max-width:100%;margin-top:6px;border:1px solid #ccc}"
            ".pass .st{color:#15803d}.fail .st{color:#b91c1c}.review .st,.missing .st{color:#b45309}"
            "</style>" + "".join(sections)
        )
        print(f"\nwrote {args.html}")


if __name__ == "__main__":
    main()

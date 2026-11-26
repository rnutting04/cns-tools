"""CD maturity: dates read from account names, tiers, and the job's
section results with screenshots."""

import io
from datetime import date
from decimal import Decimal

import pytest

from app.services.financials.batch import cd_section, flagged
from app.services.financials.extract import BalanceSheet, BSRow, Value
from app.services.financials.maturity import cd_maturities, maturity_of, tier_for
from app.services.financials.pdf import BBox, Word, build_page

pytestmark = pytest.mark.unit

AS_OF = date(2026, 11, 26)


def row(label, amount, section="cdcdars", top=200.0):
    box = BBox(20, top, 200, top + 9)
    values = {}
    if amount is not None:
        values["total"] = Value(Decimal(amount), 1, BBox(520, top, 570, top + 9), label)
    code = label.split()[0] if label[:4].isdigit() else None
    return BSRow(label=label, code=code, section=section, bbox=box, values=values)


def sheet(*rows):
    return BalanceSheet(page=1, rows=list(rows), identities=[])


def header_page(period="Period 10/31/2026"):
    words = [Word(w, BBox(20 + 60 * i, 40, 70 + 60 * i, 49)) for i, w in enumerate(period.split())]
    return build_page(1, 612, 792, words)


class TestDates:
    @pytest.mark.parametrize(
        "label, expected",
        [
            ("1320 R-CD OZK 2/13/27 13m 3.6% (0650)", date(2027, 2, 13)),
            ("1007 Oper CDAR Truist 11/27/26 52w 1.0%", date(2026, 11, 27)),
            ("1305 Rese CD BMO 8/21/2025 18m (2881)", date(2025, 8, 21)),
            # Account digits in brackets aren't a date; the real one comes first.
            ("1310 R-CD Ozk 8/10/27 11m 4.2% (5/7/8) (05", date(2027, 8, 10)),
        ],
    )
    def test_full_dates(self, label, expected):
        md = maturity_of(label)
        assert md is not None and md.when == expected and not md.month_only

    def test_month_and_year_counts_from_the_first(self):
        md = maturity_of("1307 R-CD Suncoast 12/26 11m 4.16%(2706)")
        assert md is not None and md.when == date(2026, 12, 1) and md.month_only

    @pytest.mark.parametrize(
        "label",
        ["1003 Oper CDAR Truist 4w .50%", "1491 IMA FPL Treasury Bill", "1006 Oper CD HUN 5m"],
    )
    def test_no_date(self, label):
        assert maturity_of(label) is None

    def test_impossible_date_is_skipped(self):
        assert maturity_of("1320 R-CD OZK 13/45/27") is None

    @pytest.mark.parametrize(
        "days, tier",
        [(-1, "matured"), (0, "due_30"), (30, "due_30"), (31, "due_60"), (60, "due_60"),
         (61, "due_90"), (90, "due_90"), (91, "later")],
    )  # fmt: skip
    def test_tiers(self, days, tier):
        assert tier_for(days) == tier


class TestMaturities:
    def _run(self):
        bs = sheet(
            row("Bank", None, "bank", 100),
            row("1000 Oper Truist - 5711", "9638.94", "bank", 110),
            row("CD/CDAR's", None, "cdcdars", 190),
            row("1320 R-CD OZK 2/13/27 13m 3.6% (0650)", "166019.96", top=200),
            row("1315 R-CD HUN 11/12/26 8m 3.93% (4447)", "113877.02", top=212),
            row("1308 R-CD HUN 10/24/26 13m 3.5% (4735)", "52278.14", top=224),
            row("1306 R-CD OZK 12/4/26 13m 3.6% (1857)", "59259.17", top=236),
            row("1310 R-CD OZK 8/17/27 11m 4.2% (0037)", "167468.94", top=248),
            row("1003 Oper CDAR Truist 4w .50%", "52453.58", top=260),
            row("1375 Rese Truist Investment 4.35%", "512162.59", top=272),
            row("1330 R-CD OZK 1/12/27 8m 4.1% (3891)", "0.00", top=284),
            row("Total CD/CDAR's", "1123159.40", top=296),
            row("Total Assets", "1200000.00", "assets", 320),
            row("1309 R-CD OZK 4/1/27 not an asset", "5.00", "liabilities", 340),
        )
        return cd_maturities(bs, [header_page()], as_of=AS_OF)

    def test_tiers_and_order(self):
        r = self._run()
        assert r.period_end == date(2026, 10, 31)
        assert [(c.label.split()[0], c.tier) for c in r.cds] == [
            ("1308", "matured"),
            ("1315", "matured"),
            ("1306", "due_30"),
            ("1320", "due_90"),
            ("1310", "later"),
            ("1003", "no_date"),
            ("1375", "investment"),
        ]

    def test_bank_accounts_zero_balances_and_liabilities_are_left_out(self):
        labels = [c.label for c in self._run().cds]
        assert not any(lbl.startswith(("1000", "1330", "1309", "Total")) for lbl in labels)

    def test_notes_explain_each_flag(self):
        by = {c.label.split()[0]: c for c in self._run().cds}
        assert "before this balance sheet's date (10/31/2026)" in by["1308"].notes[0]
        assert "14 days ago" in by["1315"].notes[0]
        assert by["1306"].notes == ["Matures 12/4/2026, in 8 days."]
        assert by["1310"].notes == []
        assert "4w term" in by["1003"].notes[0]
        assert not by["1375"].flagged and by["1003"].flagged

    def test_line_box_spans_name_and_amount(self):
        c = self._run().cds[0]
        assert c.bbox.x0 == 20 and c.bbox.x1 == 570


class TestSection:
    def test_result_and_flag(self, monkeypatch):
        from app.services.financials import batch, maturity
        from app.services.financials.batch import Section

        bs = sheet(
            row("1320 R-CD OZK 2/13/27 13m 3.6% (0650)", "166019.96", top=200),
            row("1310 R-CD OZK 8/17/27 11m 4.2% (0037)", "167468.94", top=212),
        )
        monkeypatch.setattr(
            batch, "extract_packet", lambda pages: type("P", (), {"balance_sheet": bs})
        )
        monkeypatch.setattr(maturity, "today", lambda: AS_OF)
        out = cd_section(Section("Test", [header_page()]))
        assert out["as_of"] == "2026-11-26" and out["period_end"] == "2026-10-31"
        soon, later = out["cds"]
        assert soon["tier"] == "due_90" and soon["days"] == 79 and len(soon["shots"]) == 1
        assert later["shots"] == []
        assert flagged("cd_maturity", out)
        assert not flagged("cd_maturity", {**out, "cds": [later]})


class TestShots:
    def _pdf(self) -> bytes:
        import pypdfium2 as pdfium

        doc = pdfium.PdfDocument.new()
        for _ in range(3):
            doc.new_page(612, 792)
        buf = io.BytesIO()
        doc.save(buf)
        return buf.getvalue()

    def test_fills_section_shots_and_keeps_few_pages(self):
        from app.services.financials.tasks import _SectionShots

        shots = _SectionShots(self._pdf())
        for page in (1, 2, 3):
            shot = {"role": "report", "page": page, "bbox": [20, 200, 570, 209], "caption": "x"}
            shots.fill({"cds": [{"shots": [shot]}]})
            assert shot["image"].startswith("data:image/jpeg;base64,")
        assert shots.renderer is not None and len(shots.renderer._pages) == 2
        shots.close()

    def test_unreadable_pdf_leaves_shots_empty(self):
        from app.services.financials.tasks import _SectionShots

        shots = _SectionShots(b"not a pdf")
        shot = {"role": "report", "page": 1, "bbox": [0, 0, 1, 1], "caption": "x"}
        shots.fill({"cds": [{"shots": [shot]}]})
        assert "image" not in shot
        shots.close()

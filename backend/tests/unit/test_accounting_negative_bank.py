"""Negative bank balances: which rows are read, the flags, and the job's
section results with screenshots."""

from decimal import Decimal

import pytest

from app.services.financials.batch import Section, flagged, negative_bank_section
from app.services.financials.extract import BSRow, Value, _balance_sheet
from app.services.financials.negative import negative_balances
from app.services.financials.pdf import BBox

pytestmark = pytest.mark.unit


def row(label, section="bank", top=200.0, **cols):
    values = {
        c: Value(Decimal(a), 1, BBox(300 + 80 * i, top, 360 + 80 * i, top + 9), label)
        for i, (c, a) in enumerate(cols.items())
    }
    code = label.split()[0] if label[:4].isdigit() else None
    box = BBox(20, top, 200, top + 9)
    return BSRow(label=label, code=code, section=section, bbox=box, values=values)


def heading(label, top):
    return BSRow(label=label, code=None, section="", bbox=BBox(20, top, 200, top + 9))


def sheet(*rows):
    """Rows through the real section/sum logic, so Total Bank is checked."""
    return _balance_sheet(1, list(rows))


def typical(overdrawn="-1234.56"):
    return sheet(
        heading("Bank", 100),
        row("1000 Oper Truist - 5721", top=110, operating=overdrawn, total=overdrawn),
        row("1300 Rese Truist - 5748", top=122, reserve="71234.56", total="71234.56"),
        row("1301 Rese Bank Ozk - 3173", top=134, reserve="0.00", total="0.00"),
        row("Total Bank", top=146, operating=overdrawn, reserve="71234.56", total="70000.00"),
        heading("Accounts Receivable", 160),
        row("1110 Allowance for Bad Debt", top=170, operating="-500.00", total="-500.00"),
        heading("Cash", 184),
        row("1010 Petty Cash", top=194, operating="-5.00", total="-5.00"),
        heading("CD/CDAR's", 208),
        row("1320 R-CD OZK 2/13/27 13m 3.6% (0650)", top=218, reserve="-10.00", total="-10.00"),
        row("Total Assets", top=240, total="1.00"),
        heading("Liability", 260),
        row("2010 Accounts Payable", top=270, operating="-99.00", total="-99.00"),
    )


class TestNegatives:
    def test_overdrawn_accounts_first_others_in_sheet_order(self):
        r = negative_balances(typical())
        assert [(a.label.split()[0], a.negative) for a in r.accounts] == [
            ("1000", True),
            ("1320", True),
            ("1300", False),
        ]
        assert r.totals_ok is True

    def test_non_bank_rows_zero_balances_and_totals_are_left_out(self):
        labels = [a.label for a in negative_balances(typical()).accounts]
        # Allowance, petty cash, liabilities, a zero account and the Total line.
        assert not any(lbl.startswith(("1110", "1010", "2010", "1301", "Total")) for lbl in labels)

    def test_note_and_figure(self):
        a = negative_balances(typical()).accounts[0]
        assert a.amount == Decimal("-1234.56") and a.verified is True
        assert a.notes == [
            "Overdrawn: Operating -1,234.56. Check the bank rec and fund the account."
        ]
        assert a.bbox.x0 == 20 and a.bbox.x1 == 440  # name through the Total figure

    def test_fund_share_overdrawn_in_a_positive_account(self):
        bs = sheet(
            heading("Bank", 100),
            row("1000 Oper Truist - 8571", top=110, fund1="-6168.64", fund2="77833.16",
                total="71664.52"),
        )  # fmt: skip
        (a,) = negative_balances(bs).accounts
        assert a.negative and a.amount == Decimal("-6168.64")
        assert "Fund 1 -6,168.64" in a.notes[0] and "total is 71,664.52" in a.notes[0]

    def test_total_bank_that_doesnt_add_up(self):
        # A lost parenthesis: the overdraft reads positive, the sum fails.
        r = negative_balances(typical(overdrawn="1234.56"))
        assert [a.label[:4] for a in r.negatives] == ["1320"]  # only the CD
        assert r.totals_ok is False
        assert r.total_checks == ["bank accounts sum to Total Bank (total)"]
        page, box = r.bank_area
        assert page == 1 and box.top == 110 and box.bottom == 155

    def test_only_the_total_column_sum_counts(self):
        # Master association: a fund figure read into the wrong column
        # breaks the fund sum, but Total ties, so no sign was misread.
        bs = sheet(
            heading("Bank", 100),
            row("1000 Oper Truist", top=110, fund1="77833.16", total="77833.16"),
            row("1300 Rec Rese", top=122, fund2="100.00", total="100.00"),
            row("Total Bank", top=134, fund1="77733.16", fund2="200.00", total="77933.16"),
        )
        r = negative_balances(bs)
        assert r.totals_ok is True and r.bank_area is None

    def test_no_total_bank_line(self):
        bs = sheet(heading("Bank", 100), row("1000 Oper Truist", top=110, total="5.00"))
        r = negative_balances(bs)
        assert r.totals_ok is None and r.bank_area is None


class TestSection:
    def _run(self, monkeypatch, bs):
        from app.services.financials import batch

        monkeypatch.setattr(
            batch, "extract_packet", lambda pages: type("P", (), {"balance_sheet": bs})
        )
        return negative_bank_section(Section("Test", []))

    def test_result_and_flag(self, monkeypatch):
        out = self._run(monkeypatch, typical())
        neg, cd, ok = out["accounts"]
        assert neg["negative"] and neg["amounts"] == {"operating": -1234.56, "total": -1234.56}
        assert len(neg["shots"]) == 1 and neg["shots"][0]["page"] == 1
        assert ok["shots"] == [] and out["shots"] == []
        assert flagged("negative_bank", out)
        assert not flagged("negative_bank", {**out, "accounts": [ok]})

    def test_sum_failure_flags_and_shows_the_bank_section(self, monkeypatch):
        out = self._run(monkeypatch, typical(overdrawn="1234.56"))
        assert out["totals_ok"] is False and len(out["shots"]) == 1
        assert not any(a["negative"] for a in out["accounts"] if a["label"].startswith("1000"))
        assert flagged("negative_bank", out)

    def test_unreadable_balance_sheet(self, monkeypatch):
        out = self._run(monkeypatch, None)
        assert "problem" in out and flagged("negative_bank", out)

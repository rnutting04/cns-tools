"""MASS Reserve Schedule workbook: no line item Balance may be negative."""

import io
from decimal import Decimal
from pathlib import Path

import openpyxl
import pytest

from app.services.excel.reserve_schedule import check_workbook

pytestmark = pytest.mark.unit

HEADER = [
    "Code",
    "Description",
    "Start of Year",
    "Receipts",
    "Adjustment",
    "Percentage",
    "Expenses",
    "Balance",
]


def _line(code, desc, balance):
    return [code, desc, 0, 0, 0, 0, 0, balance]


def _workbook(**tabs) -> io.BytesIO:
    """Each tab: list of rows placed under a date row, a blank, and the header."""
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for name, rows in tabs.items():
        ws = wb.create_sheet(name)
        ws.append(["2026-11-30"])
        ws.append([])
        ws.append(HEADER)
        for r in rows:
            ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def test_clean_tab_has_no_issues():
    res = check_workbook(
        _workbook(
            AMC=[
                _line(7010, "Roof", 61442.76),
                _line(7030, "Walkways", 0),
                [None, "TOTAL", 0, 0, 0, 1, 0, 61442.76],
            ]
        )
    )
    assert res.issues == []
    assert res.sheets[0].line_items == 2


def test_negative_component_flagged_with_location():
    # Like CAR: two pool components overspent.
    res = check_workbook(
        _workbook(
            CAR=[
                _line(7010, "Roof", 63191.83),
                _line(7061, "Pool Resurface", -10806.115166948199),
                _line(7062, "Pool Equipment", -20569.554805258842),
                [None, "TOTAL", 0, 0, 0, 1, 0, 277231.07],
            ]
        )
    )
    assert [(i.cell, i.code, i.description, i.balance) for i in res.issues] == [
        ("H5", "7061", "Pool Resurface", Decimal("-10806.12")),
        ("H6", "7062", "Pool Equipment", Decimal("-20569.55")),
    ]


def test_totals_subtotals_and_rows_below_total_are_not_line_items():
    res = check_workbook(
        _workbook(
            BM2=[
                ["Painting"],  # group heading
                _line(7020, "Paint", 100),
                [None, "Total Paint", 0, 0, 0, 0, 0, -50],  # subtotal: excluded
                _line(7010, "Roof", 200),
                [None, "TOTAL", 0, 0, 0, 1, 0, -10],  # total: excluded
                [None, "Assessments", None, 141826.44],  # receipts breakdown, no balance
                [None, None, None, 0, "out of balance by"],
            ]
        )
    )
    assert res.issues == []
    assert res.sheets[0].line_items == 2


def test_float_noise_is_not_negative_and_group_is_reported():
    res = check_workbook(
        _workbook(
            SSC=[
                ["SIRS Non-Waivable"],
                _line(7010, "Roof", -0.0000001),
                _line(7012, "Roofing - Lexan Dome", -3116.68),
            ]
        )
    )
    [issue] = res.issues
    assert issue.group == "SIRS Non-Waivable"
    assert issue.balance == Decimal("-3116.68")


def test_text_balances_are_read_and_non_numbers_flagged():
    res = check_workbook(
        _workbook(WCA=[_line(1, "A", "(150.00)"), _line(2, "B", "TBD"), _line(3, "C", " ")])
    )
    assert {(i.code, i.problem) for i in res.issues} == {("1", "negative"), ("2", "not_a_number")}


def test_tab_without_balance_header_is_reported_unchecked():
    wb = openpyxl.Workbook()
    wb.active.title = "XYZ"
    wb.active.append(["Notes only"])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    assert check_workbook(buf).sheets[0].checked is False


MASS = (
    Path(__file__).resolve().parents[2]
    / "test_data"
    / "context"
    / "MASS Reserve Schedule - 2026.xlsx"
)


@pytest.mark.skipif(not MASS.exists(), reason="MASS workbook not present")
def test_real_mass_workbook():
    res = check_workbook(str(MASS))
    assert len(res.sheets) == 125
    assert all(s.checked for s in res.sheets)
    assert len(res.issues) == 22
    car = {(i.cell, i.balance) for i in res.issues if i.sheet == "CAR"}
    assert car == {("H10", Decimal("-10806.12")), ("H11", Decimal("-20569.55"))}

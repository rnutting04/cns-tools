"""Combined multi-association PDFs: splitting by association and the
background job that runs a tool over every section."""

import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.models.accounting_job import AccountingJob
from app.models.letter_job import JobStatus
from app.services.financials.batch import association_name, split_sections
from app.services.financials.pdf import BBox, Word, build_page, merge_split_numbers, parse_amounts

pytestmark = pytest.mark.unit


def page(number, header, footer=None, ocr=False):
    rows = [(30 + 15 * i, text) for i, text in enumerate(header)]
    if footer:
        rows.append((740, footer))
    words = [
        Word(w, BBox(30 + 50 * j, top, 30 + 50 * j + 6 * len(w), top + 9))
        for top, text in rows
        for j, w in enumerate(text.split())
    ]
    return build_page(number, 612, 792, words, ocr=ocr)


def ie(number, name, dept="Operating"):
    return page(
        number,
        [
            "Saturday, November 18, 2023 15:18",
            name,
            "Income and Expense Report",
            "Period 10/1/2023 To 10/31/2023",
            f"Current Month {dept} Year to Date {dept}",
        ],
    )


def bs(number, name, page_of="Page 1 of 1", ocr=True):
    return page(
        number,
        ["Balance Sheet Wednesday November 25 2026 15:57", "Period 10/31/2026", name],
        footer=page_of,
        ocr=ocr,
    )


class TestAssociationName:
    def test_income_expense_header(self):
        assert association_name(ie(1, "1500 State Street Condo")) == "1500 State Street Condo"

    def test_balance_sheet_header(self):
        assert association_name(bs(1, "Anna Maria Island Club")) == "Anna Maria Island Club"

    def test_numeric_association_name(self):
        assert association_name(ie(1, "5400")) == "5400"


class TestSplit:
    def test_operating_and_reserve_pages_stay_together(self):
        pages = [ie(1, "Amber Glen"), ie(2, "Amber Glen", "Reserve"), ie(3, "Arbor Oaks")]
        assert [(s.name, s.page_range) for s in split_sections(pages)] == [
            ("Amber Glen", (1, 2)),
            ("Arbor Oaks", (3, 3)),
        ]

    def test_numbered_associations_are_not_merged(self):
        # One letter apart, but different associations.
        pages = [ie(1, "Banbury I"), ie(2, "Banbury II"), ie(3, "Stone Harbour I", "Reserve")]
        assert [s.name for s in split_sections(pages)] == [
            "Banbury I",
            "Banbury II",
            "Stone Harbour I",
        ]

    def test_ocr_roman_numerals_split_on_page_restart(self):
        # OCR read "II"/"III" as "Il"/"Ill"; each sheet restarts at Page 1.
        pages = [bs(1, "Stone Harbour Il"), bs(2, "Stone Harbour Ill")]
        assert len(list(split_sections(pages))) == 2

    def test_multi_page_balance_sheet_with_ocr_name_damage_stays_together(self):
        pages = [
            bs(1, "Fair Lane Acres, Inc.", "Page 1 of 2"),
            bs(2, "Fair Lane Acres. Inc.", "Page 2 of 2"),
            bs(3, "Glen Oaks Ridge", "Page 1 of 1"),
        ]
        assert [s.page_range for s in split_sections(pages)] == [(1, 2), (3, 3)]


class TestOcrNumberRepair:
    def test_split_thousands_rejoined(self):
        words = [
            Word("388,", BBox(354, 100, 370, 109)),
            Word("748.91", BBox(372, 100, 398, 109)),
            Word("704,474.61", BBox(417, 100, 461, 109)),
        ]
        assert [w.text for w in merge_split_numbers(words)] == ["388,748.91", "704,474.61"]

    def test_adjacent_columns_not_joined(self):
        words = [Word("488", BBox(290, 100, 304, 109)), Word("629.30", BBox(330, 100, 356, 109))]
        assert len(merge_split_numbers(words)) == 2

    @pytest.mark.parametrize(
        "token, value",
        [
            ("268,27", "268.27"),
            ("§2,511.92", "52511.92"),
            ("(1O0.00)", "-100.00"),
            ("0,00", "0.00"),
        ],
    )
    def test_ocr_character_slips(self, token, value):
        assert [str(v) for v in parse_amounts(token)] == [value]

    @pytest.mark.parametrize("token", ["12,345", "Oper", "10/31/2026", "2.95%", "Il"])
    def test_non_amounts_left_alone(self, token):
        assert parse_amounts(token) == []


IE_COMBINED = (
    Path(__file__).resolve().parents[2]
    / "test_data"
    / "context"
    / "CSC_Income_and_Expense_Report.pdf"
)


@pytest.mark.skipif(not IE_COMBINED.exists(), reason="combined sample not present")
def test_job_runs_tool_over_each_association():
    import pypdfium2 as pdfium

    from app.services.financials.tasks import run_accounting_job

    # First 13 pages: 1500 State Street, 5400, 624 Palm, Amber Glen, Anna Maria Island Club.
    src = pdfium.PdfDocument(str(IE_COMBINED))
    sub = pdfium.PdfDocument.new()
    sub.import_pages(src, list(range(13)))
    buf = io.BytesIO()
    sub.save(buf)

    job = AccountingJob(
        tool="revenue_threshold", filename="combined.pdf", input_path="k", results=[], pages_done=0
    )
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = job
    with (
        patch("app.services.financials.tasks.SessionLocal", return_value=db),
        patch("app.services.financials.tasks.storage_service") as storage,
    ):
        storage.download_file.return_value = buf.getvalue()
        run_accounting_job.run("00000000-0000-0000-0000-000000000001")

    assert job.status is JobStatus.complete
    assert job.total_pages == job.pages_done == 13
    assert [r["association"] for r in job.results] == [
        "1500 State Street Condo",
        "5400",
        "624 Palm Condo",
        "Amber Glen",
        "Anna Maria Island Club",
    ]
    tiers = {r["association"]: r["result"]["ytd_actual"]["tier"] for r in job.results}
    assert tiers["5400"] == "audit" and tiers["Amber Glen"] == "none"
    storage.delete_file.assert_called_once_with("k")
    assert job.input_path is None

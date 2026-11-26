"""AR & prepaid across combined files: the balance sheets, the CSC AR Names
report and the CSC_Prepaid report, each holding every association."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.models.accounting_job import AccountingJob
from app.models.letter_job import JobStatus
from app.services.financials.batch import association_name, same_association, split_sections
from app.services.financials.extract import parse_ar_aging, parse_prepaid_assessments
from app.services.financials.pdf import BBox, Word, build_page, parse_amounts
from app.services.financials.receivables import Found, pair, read_section, reconcile

pytestmark = pytest.mark.unit

# Column centres of the synthetic balance sheet.
OPER, RESE, TOTAL = 400, 470, 540


def laid_out(number, rows, footer="Page 1 of 1", ocr=True):
    """A page from rows of (x, text) cells, one row every 14pt."""
    words = []
    for i, cells in enumerate(rows):
        top = 30 + 14 * i
        for x, text in cells:
            for j, w in enumerate(text.split()):
                x0 = x + 40 * j
                words.append(Word(w, BBox(x0, top, x0 + 5.5 * len(w), top + 9)))
    if footer:
        words += [
            Word(w, BBox(500 + 25 * j, 740, 520 + 25 * j, 749))
            for j, w in enumerate(footer.split())
        ]
    return build_page(number, 612, 792, words, ocr=ocr)


def num(x_centre, text):
    """An amount centred on a column."""
    return (x_centre - 2.75 * len(text), text)


def balance_sheet(number, name, ar="5,880.22", prepaid="15,570.32", footer="Page 1 of 1"):
    rows = [
        [(30, "Balance Sheet"), (300, "Wednesday, November 25, 2026 15:57")],
        [(30, "Period 10/31/2026")],
        [(30, name)],
        [(OPER - 25, "Operating"), (RESE - 20, "Reserve"), (TOTAL - 12, "Total")],
        [(90, "Assets")],
        [(40, "1100"), (70, "Acct Receivable Members"), num(OPER, ar), num(TOTAL, ar)],
        [(90, "Total Assets"), num(OPER, ar), num(TOTAL, ar)],
        [(90, "Liabilities & Equity")],
    ]
    if prepaid:
        rows.append(
            [
                (40, "2100"),
                (70, "Prepaid Member Assessment"),
                num(OPER, prepaid),
                num(TOTAL, prepaid),
            ]
        )
    return laid_out(number, rows, footer)


def ar_report(number, name, balance="5,880.22", buckets=None, footer="Page 1 of 1"):
    buckets = buckets or ["2,781.40", "2,680.68", "418.14", "0.00"]
    return laid_out(
        number,
        [
            [(30, "CSC AR NAMES"), (300, "Wednesday, November 25, 2026 17:20")],
            [(30, "Period 10/31/2026")],
            [(30, name)],
            [(30, "Acct # Status Unit/Lot # Resident Contact Current Balance")],
            [(30, "14942 38 Wengell,Diane"), (300, " ".join([*buckets, balance]))],
            [(30, "Count: 13"), (300, " ".join([*buckets, balance]))],
        ],
        footer,
    )


def prepaid_report(number, name, rows, total, footer="Page 1 of 1"):
    body = [
        [(30, f"Owner{i}, Pat"), (250, f"1 Main St {i}"), (430, f"1490{i}"), (520, a)]
        for i, a in enumerate(rows)
    ]
    return laid_out(
        number,
        [
            [(30, "CSC_ Prepaid"), (300, "Wednesday, November 25, 2026 4:07:36 PM")],
            [(80, "Period 10/31/2026")],
            [(520, "Prepaid")],
            [(30, "Resident Contact"), (430, "Account #"), (520, "Amount")],
            [(250, "Property Address")],
            [(30, name)],
            *body,
            *([[(520, total)]] if total else []),
        ],
        footer,
    )


class TestNames:
    def test_prepaid_header_name_under_column_headings(self):
        p = prepaid_report(1, "624 Palm Condo", ["-0.50", "-5,854.00"], "-5,854.50")
        assert association_name(p) == "624 Palm Condo"

    def test_ar_header(self):
        assert association_name(ar_report(1, "Palma Sola Trace Condo")) == "Palma Sola Trace Condo"

    def test_owner_row_is_not_a_name(self):
        # A continuation page repeats no name; its first row has no amount
        # (OCR lost it) but does have the owner's "Last, First" and account.
        p = laid_out(
            2,
            [
                [(30, "CSC_ Prepaid"), (300, "Wednesday, November 25, 2026 4:40:12 PM")],
                [(80, "Period 10/31/2026")],
                [(30, "Resident Contact"), (430, "Account #")],
                [(250, "Property Address")],
                [(30, "Lash, Andrew & Judy"), (250, "4753 Cayo Costa Place"), (430, "15865")],
                [
                    (30, "Samad, Husam A"),
                    (250, "4518 Egmont Drive"),
                    (430, "15788"),
                    (520, "-75.20"),
                ],
            ],
            "Page 2 of 6",
        )
        assert association_name(p) == ""

    def test_misprinted_page_counter_does_not_merge_associations(self):
        # The combined balance sheets number a blank page "1 of 2" and the
        # next association's sheet "2 of 2": the name decides.
        pages = [
            balance_sheet(1, "Runaway Bay", footer="Page 1 of 2"),
            laid_out(
                2,
                [[(30, "Balance Sheet")], [(30, "Period 10/31/2026")], [(30, "Runaway Bay")]],
                "Page 1 of 2",
            ),
            balance_sheet(3, "Sabal Harbour", footer="Page 2 of 2"),
        ]
        assert [(s.name, s.page_range) for s in split_sections(pages)] == [
            ("Runaway Bay", (1, 2)),
            ("Sabal Harbour", (3, 3)),
        ]


class TestSameAssociation:
    @pytest.mark.parametrize(
        "a, b",
        [
            ("Carpentras at the Villages of Avignon", "Carpentras at the Villages of Avi"),
            ("Crooked Creek III at Sarasota National", "Crooked Creek Ill at Sarasota N:"),
            ("Veranda III at Lakewood National", "Veranda III at Lakewood Nation<"),
            ("Oak Run Ill at Sarasota National", "Oak Run III at Sarasota National"),
            ("Baywood Colony $1", "Baywood Colony S1"),
            ("Stone Harbour Il", "Stone Harbour II"),
        ],
    )
    def test_same(self, a, b):
        assert same_association(a, b)

    @pytest.mark.parametrize(
        "a, b",
        [
            ("Veranda V at Lakewood National", "Veranda VI at Lakewood National"),
            ("Crooked Creek", "Crooked Creek III at Sarasota National"),
            ("Terrace V at Lakewood National", "Terrace VII Lakewood National"),
            ("Banbury I", "Banbury II"),
            ("Country Meadows", "McIntosh Meadows"),
        ],
    )
    def test_different(self, a, b):
        assert not same_association(a, b)

    def test_exact_names_pair_before_loose_ones(self):
        pool = [Found("ar", n, i, i) for i, n in enumerate(["Valgo II", "Valgo Il", "Valgo"])]
        got = pair(["Valgo Il", "Valgo II"], pool)
        assert [f.first_page for f in got] == [1, 0]

    def test_partial_name_paired_only_when_unique(self):
        pool = [Found("prepaid", "Meadows", 1, 1), Found("prepaid", "Second", 2, 2)]
        got = pair(["McIntosh Meadows", "Ironwood Second", "Country Meadows Two"], pool)
        # "Meadows" fits two names, so neither gets it; "Second" fits one.
        assert got[0] is None and got[2] is None
        assert got[1] is pool[1]


class TestReportTotals:
    @pytest.mark.parametrize(
        "token, value", [("-61,905,.32", "-61905.32"), ("=15,570,.32", "15570.32")]
    )
    def test_stray_comma_before_decimal(self, token, value):
        assert [str(abs(v)) for v in parse_amounts(token)] == [value.lstrip("-")]

    def test_prepaid_total_falls_back_to_row_sum(self):
        # OCR lost the total line under its underline.
        p = prepaid_report(1, "Riggs Landing", ["-15.00", "-16,199.00"], None)
        r = parse_prepaid_assessments([p])
        assert r.total.amount == Decimal("16214.00")
        assert r.total.guessed and "added up" in r.total.note

    def test_ar_total_falls_back_to_row_sum(self):
        p = laid_out(
            1,
            [
                [(30, "CSC AR NAMES")],
                [(30, "Willow Walk")],
                [(30, "39133 420 Rewalt,Kathleen"), (300, "0.00 0.49 0.00 0.00 0.49")],
                [(30, "39022 385 Brenner,Donald"), (300, "0.00 0.20 0.00 0.00 0.20")],
            ],
        )
        r = parse_ar_aging([p])
        assert r.total.amount == Decimal("0.69") and r.total.guessed


def found(role, name, section_pages):
    sections = list(split_sections(section_pages))
    assert len(sections) == 1
    return read_section(role, sections[0])


class TestReconcile:
    def test_pairs_across_files_and_compares(self):
        result = reconcile(
            {
                "balance_sheet": [
                    found("balance_sheet", "5400", [balance_sheet(1, "5400")]),
                    found(
                        "balance_sheet", "Valgo", [balance_sheet(2, "Valgo", "100.00", "6,287.49")]
                    ),
                ],
                "ar": [
                    found(
                        "ar",
                        "Valgo",
                        [ar_report(5, "Valgo", "100.00", ["0.00", "100.00", "0.00", "0.00"])],
                    ),
                    found("ar", "5400", [ar_report(6, "5400")]),
                ],
                "prepaid": [
                    found(
                        "prepaid",
                        "5400",
                        [prepaid_report(7, "5400", ["-570.32", "-15,000.00"], "-15,570.32")],
                    ),
                    found(
                        "prepaid", "Valgo", [prepaid_report(8, "Valgo", ["-6,441.68"], "-6,441.68")]
                    ),
                ],
            }
        )
        by_name = {r["association"]: r for r in result}
        assert list(by_name) == ["5400", "Valgo"]
        statuses = lambda r: {c["id"]: c["status"] for c in r["result"]["checks"]}  # noqa: E731
        assert statuses(by_name["5400"]) == {"ar": "pass", "prepaid_assessments": "pass"}
        assert not by_name["5400"]["flagged"]
        valgo = by_name["Valgo"]
        assert statuses(valgo) == {"ar": "pass", "prepaid_assessments": "fail"}
        assert valgo["flagged"]
        pp = valgo["result"]["checks"][1]
        assert pp["difference"] == pytest.approx(-154.19)
        assert valgo["result"]["pages"] == {
            "balance_sheet": [2, 2],
            "ar": [5, 5],
            "prepaid": [8, 8],
        }
        # Says why in plain words, and points at both figures.
        assert "The report is 154.19 higher." in pp["notes"][0]
        assert [(s["role"], s["page"]) for s in pp["shots"]] == [
            ("balance_sheet", 2),
            ("prepaid", 8),
        ]
        assert pp["shots"][0]["caption"] == "Balance sheet p.2: 2100 Prepaid Member Assessment"
        # Passing checks carry no screenshots.
        assert by_name["5400"]["result"]["checks"][0]["shots"] == []

    def test_same_difference_on_ar_and_prepaid_is_called_out(self):
        result = reconcile(
            {
                "balance_sheet": [
                    found(
                        "balance_sheet",
                        "Waterford Condo",
                        [balance_sheet(1, "Waterford Condo", "62,216.98", "43,865.57")],
                    )
                ],
                "ar": [
                    found(
                        "ar",
                        "Waterford Condo",
                        [
                            ar_report(
                                2,
                                "Waterford Condo",
                                "18,471.64",
                                ["18,471.64", "0.00", "0.00", "0.00"],
                            )
                        ],
                    )
                ],
                "prepaid": [
                    found(
                        "prepaid",
                        "Waterford Condo",
                        [prepaid_report(3, "Waterford Condo", ["-120.23"], "-120.23")],
                    )
                ],
            }
        )
        checks = result[0]["result"]["checks"]
        assert [c["status"] for c in checks] == ["fail", "fail"]
        assert all("both off by 43,745.34" in " ".join(c["notes"]) for c in checks)

    def test_missing_report_and_unmatched_association(self):
        result = reconcile(
            {
                "balance_sheet": [
                    found(
                        "balance_sheet",
                        "Arbor Oaks",
                        [balance_sheet(1, "Arbor Oaks", prepaid=None)],
                    )
                ],
                "ar": [found("ar", "Lionshead", [ar_report(2, "Lionshead")])],
            }
        )
        arbor, lions = result
        (check,) = arbor["result"]["checks"]
        assert check["id"] == "ar" and check["status"] == "missing"
        assert lions["association"] == "Lionshead" and lions["flagged"]
        assert "no balance sheet matched" in lions["result"]["problem"]

    def test_account_absent_and_no_report_is_not_applicable(self):
        result = reconcile(
            {
                "balance_sheet": [
                    found(
                        "balance_sheet",
                        "Arbor Oaks",
                        [balance_sheet(1, "Arbor Oaks", prepaid=None)],
                    )
                ],
                "prepaid": [],
            }
        )
        assert result[0]["result"]["checks"][0]["status"] == "not_applicable"

    def test_not_applicable_shows_where_the_line_would_be(self):
        page = laid_out(
            1,
            [
                [(30, "Balance Sheet"), (300, "Wednesday, November 25, 2026 15:57")],
                [(30, "Period 10/31/2026")],
                [(30, "Botanica")],
                [(OPER - 25, "Operating"), (RESE - 20, "Reserve"), (TOTAL - 12, "Total")],
                [(90, "Assets")],
                [(40, "1000"), (70, "Oper Truist"), num(OPER, "100.00"), num(TOTAL, "100.00")],
                [(40, "1130"), (70, "Prepaid Insurance"), num(OPER, "50.00"), num(TOTAL, "50.00")],
                [(90, "Total Assets"), num(OPER, "150.00"), num(TOTAL, "150.00")],
            ],
        )
        result = reconcile(
            {"balance_sheet": [found("balance_sheet", "Botanica", [page])], "ar": []}
        )
        (check,) = result[0]["result"]["checks"]
        assert check["status"] == "not_applicable"
        assert "from 1000 Oper Truist to 1130 Prepaid Insurance" in check["notes"][0]
        (shot,) = check["shots"]
        assert shot["caption"] == "Balance sheet p.1: where 1100 would be"
        top, bottom = shot["bbox"][1], shot["bbox"][3]
        assert top < 30 + 14 * 5 + 1 and bottom > 30 + 14 * 6  # spans both lines

    def test_suggests_the_closest_unpaired_name(self):
        result = reconcile(
            {
                "balance_sheet": [
                    found(
                        "balance_sheet",
                        "Arbor Oaks",
                        [balance_sheet(1, "Arbor Oaks", prepaid=None)],
                    )
                ],
                "ar": [found("ar", "Arbor Lakes", [ar_report(2, "Arbor Lakes")])],
            }
        )
        arbor, lakes = result
        (check,) = arbor["result"]["checks"]
        assert check["status"] == "missing"
        assert "shows 5,880.22 on 1100" in check["notes"][0]
        assert "unpaired section named “Arbor Lakes” (p.2)" in check["notes"][-1]
        assert (
            "Closest balance sheet without this report: “Arbor Oaks” (p.1)"
            in (lakes["result"]["problem"])
        )
        assert [s["role"] for s in lakes["result"]["shots"]] == ["ar"]


class TestImages:
    def _pdf(self, pages=2) -> bytes:
        import io

        import pypdfium2 as pdfium

        doc = pdfium.PdfDocument.new()
        for _ in range(pages):
            doc.new_page(612, 792)
        buf = io.BytesIO()
        doc.save(buf)
        return buf.getvalue()

    def test_fills_each_shot_with_a_jpeg(self):
        from app.services.financials.tasks import add_images

        shot = {"role": "ar", "page": 2, "bbox": [300, 100, 400, 110], "caption": "x"}
        results = [{"result": {"checks": [{"shots": [shot]}]}}]
        add_images(results, {"ar": self._pdf()})
        assert shot["image"].startswith("data:image/jpeg;base64,")

    def test_an_unreadable_file_just_leaves_shots_without_images(self):
        from app.services.financials.tasks import add_images

        shot = {"role": "ar", "page": 1, "bbox": [0, 0, 10, 10], "caption": "x"}
        add_images([{"result": {"problem": "p", "shots": [shot]}}], {"ar": b"not a pdf"})
        assert "image" not in shot


class TestJob:
    def _run(self, files):
        from app.services.financials.tasks import run_accounting_job

        keys = {role: f"accounting/j/{role}.pdf" for role in files}
        job = AccountingJob(
            tool="receivables",
            filename="x",
            input_path=__import__("json").dumps(keys),
            results=[],
            pages_done=0,
        )
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = job

        def iter_pages(source, **_):
            yield from files[source.getvalue().decode()]

        with (
            patch("app.services.financials.tasks.SessionLocal", return_value=db),
            patch("app.services.financials.tasks.storage_service") as storage,
            patch("app.services.financials.tasks.iter_pages", side_effect=iter_pages),
            patch(
                "app.services.financials.tasks.page_count",
                side_effect=lambda s: len(files[s.getvalue().decode()]),
            ),
        ):
            storage.download_file.side_effect = lambda key: key.rsplit("/", 1)[1][:-4].encode()
            run_accounting_job.run("00000000-0000-0000-0000-000000000001")
        return job, storage, keys

    def test_reads_every_file_then_compares(self):
        job, storage, keys = self._run(
            {
                "balance_sheet": [
                    balance_sheet(1, "5400"),
                    balance_sheet(2, "Amber Glen", "0.00", None),
                ],
                "ar": [ar_report(1, "5400")],
                "prepaid": [prepaid_report(1, "5400", ["-15,570.32"], "-15,570.32")],
            }
        )
        assert job.status is JobStatus.complete, job.error_detail
        assert job.total_pages == job.pages_done == 4
        assert [r["association"] for r in job.results] == ["5400", "Amber Glen"]
        assert {c["status"] for c in job.results[0]["result"]["checks"]} == {"pass"}
        deleted = {c.args[0] for c in storage.delete_file.call_args_list}
        assert deleted == set(keys.values()) and job.input_path is None

    def test_file_in_the_wrong_slot_fails_clearly(self):
        job, _, _ = self._run(
            {
                "balance_sheet": [balance_sheet(1, "5400")],
                # The prepaid report uploaded as the AR file.
                "ar": [prepaid_report(1, "5400", ["-1.00"], "-1.00")],
            }
        )
        assert job.status is JobStatus.failed
        assert "AR file doesn't look like" in job.error_detail

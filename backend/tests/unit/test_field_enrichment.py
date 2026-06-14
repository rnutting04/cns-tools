"""Unit tests for the pure field-enrichment functions (no DB, no network)."""

import pytest
from freezegun import freeze_time

from app.config.letter_config import NOTICE_CANDIDACY_DEADLINE_DAYS
from app.models.association import Association
from app.models.user import User
from app.services.letters import field_enrichment as fe

pytestmark = pytest.mark.unit


class TestOrdinalNumber:
    @pytest.mark.parametrize(
        "n,expected",
        [
            (1, "1st"),
            (2, "2nd"),
            (3, "3rd"),
            (4, "4th"),
            (11, "11th"),
            (12, "12th"),
            (13, "13th"),
            (21, "21st"),
            (22, "22nd"),
            (23, "23rd"),
            (101, "101st"),
            (111, "111th"),
        ],
    )
    def test_ordinals(self, n, expected):
        assert fe._ordinal_number(n) == expected


class TestStringVariants:
    def test_upper_lower_title(self):
        variants = fe._string_variants("name", "jane doe")
        assert variants == {
            "name_upper": "JANE DOE",
            "name_lower": "jane doe",
            "name_title": "Jane Doe",
        }


class TestDateVariants:
    def test_valid_iso_date_produces_all_variants(self):
        variants = fe._date_variants("meeting", "2026-03-09")
        assert variants["meeting_iso"] == "2026-03-09"
        assert variants["meeting_short"] == "03/09/2026"
        assert variants["meeting_long"] == "March 9, 2026"
        assert variants["meeting_formal"] == "9th day of March 2026"
        assert variants["meeting_month_year"] == "March 2026"

    def test_non_date_string_returns_empty(self):
        assert fe._date_variants("meeting", "not-a-date") == {}


class TestNoticeCandidacyDeadline:
    def test_subtracts_configured_days(self):
        deadline = fe._compute_notice_candidacy_deadline("2026-04-15")
        # 38 days before 2026-04-15 is 2026-03-08
        assert deadline.isoformat() == "2026-03-08"
        assert NOTICE_CANDIDACY_DEADLINE_DAYS == 38

    @pytest.mark.parametrize("bad", [None, "", "15-04-2026", "garbage"])
    def test_invalid_or_missing_returns_none(self, bad):
        assert fe._compute_notice_candidacy_deadline(bad) is None


def _association() -> Association:
    return Association(
        legal_name="Sunset Ridge Homeowners Association, Inc.",
        filter_name="Sunset Ridge",
        location_name="Bradenton",
    )


def _manager() -> User:
    return User(
        fname="Jane",
        lname="Doe",
        title="Community Manager",
        email="jane@example.com",
    )


class TestBuildFieldContext:
    @freeze_time("2026-06-14")
    def test_core_derived_fields(self):
        ctx = fe.build_field_context({}, _association(), _manager())
        assert ctx["legal_association_name"] == "Sunset Ridge Homeowners Association, Inc."
        assert ctx["filtered_association_name"] == "Sunset Ridge"
        assert ctx["assn_city"] == "Bradenton"
        assert ctx["manager_full_name"] == "Jane Doe"
        assert ctx["manager_email"] == "jane@example.com"
        assert ctx["today_date"] == "2026-06-14"

    def test_no_manager_yields_blank_manager_fields(self):
        ctx = fe.build_field_context({}, _association(), None)
        assert ctx["manager_full_name"] == ""
        assert ctx["manager_titles"] == ""
        assert ctx["manager_email"] == ""

    def test_unknown_office_location_is_blank(self):
        ctx = fe.build_field_context({"office_location": None}, _association(), None)
        assert ctx["office_street"] == ""
        assert ctx["office_city_state_zip"] == ""
        assert ctx["office_phone"] == ""

    def test_notice_deadline_set_when_meeting_date_present(self):
        ctx = fe.build_field_context({"date": "2026-04-15"}, _association(), None)
        assert ctx["notice_deadline"] == "2026-03-08"

    def test_notice_deadline_absent_without_date(self):
        ctx = fe.build_field_context({}, _association(), None)
        assert "notice_deadline" not in ctx

    def test_variants_are_expanded_for_user_input(self):
        ctx = fe.build_field_context({"meeting": "2026-03-09"}, _association(), None)
        assert ctx["meeting_long"] == "March 9, 2026"
        assert ctx["meeting_upper"] == "2026-03-09".upper()

    def test_does_not_mutate_input(self):
        user_input = {"foo": "bar"}
        fe.build_field_context(user_input, _association(), None)
        assert user_input == {"foo": "bar"}

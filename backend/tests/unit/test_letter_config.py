"""Unit tests for letter_config lookups (deterministic paths, no YAML coupling)."""

import pytest

from app.config.letter_config import get_office, render_proxy_vote

pytestmark = pytest.mark.unit


class TestGetOffice:
    def test_none_returns_empty_office(self):
        office = get_office(None)
        assert office == {
            "office_street": "",
            "office_city_state_zip": "",
            "office_phone": "",
        }

    def test_unknown_key_returns_empty_office(self):
        office = get_office("__definitely_not_a_real_office__")
        assert office["office_street"] == ""
        assert office["office_phone"] == ""


class TestRenderProxyVote:
    def test_missing_type_returns_empty(self):
        assert render_proxy_vote({}) == ("", False)

    def test_unknown_type_returns_empty(self):
        assert render_proxy_vote({"type": "__not_a_real_vote_type__"}) == ("", False)

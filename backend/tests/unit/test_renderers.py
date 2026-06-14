"""Unit tests for document renderers (operate on in-memory .docx bytes; no DB)."""

import pytest

from app.services import renderers
from tests.docx_utils import docx_tables, docx_text, make_docx

pytestmark = pytest.mark.unit


class TestCountWordHelpers:
    @pytest.mark.parametrize("n,expected", [(1, "ONE(1)"), (8, "EIGHT(8)"), (11, "11(11)")])
    def test_word_num(self, n, expected):
        assert renderers._word_num(n) == expected

    @pytest.mark.parametrize("n,expected", [(1, "one (1)"), (8, "eight (8)"), (11, "11 (11)")])
    def test_word_num_lower(self, n, expected):
        assert renderers._word_num_lower(n) == expected


class TestBuildBallotFieldValues:
    def test_extracts_candidates_and_count(self):
        candidates, fv = renderers._build_ballot_field_values(
            {"candidates": ["A", "B"], "candidate_vote_limit": 2}
        )
        assert candidates == ["A", "B"]
        assert fv["candidate_count"] == "2"
        assert fv["candidate_count_word_num"] == "TWO(2)"
        assert fv["candidate_count_word_num_lower"] == "two (2)"

    def test_invalid_vote_limit_defaults_to_zero(self):
        _, fv = renderers._build_ballot_field_values(
            {"candidates": [], "candidate_vote_limit": "not-a-number"}
        )
        assert fv["candidate_count"] == "0"

    def test_missing_candidates_yields_empty_list(self):
        candidates, _ = renderers._build_ballot_field_values({})
        assert candidates == []


class TestSimpleRenderer:
    def test_replaces_placeholder(self):
        template = make_docx(["Dear {{name}},", "Welcome to {{place}}."])
        out = renderers.simple_renderer(template, {"name": "Alice", "place": "Sunset Ridge"})
        text = docx_text(out)
        assert "Dear Alice," in text
        assert "Welcome to Sunset Ridge." in text
        assert "{{" not in text

    def test_unresolved_split_placeholder_raises(self):
        # A placeholder present with no matching value stays unresolved -> ValueError.
        template = make_docx(["Hello {{missing}}"])
        with pytest.raises(ValueError):
            renderers.simple_renderer(template, {"name": "Alice"})


class TestBallotRenderer:
    def test_one_column_for_few_candidates(self):
        names = [f"Cand {i}" for i in range(3)]
        template = make_docx(["Count: {{candidate_count}}", "{{BLOCK:BALLOT_CANDIDATES}}"])
        out = renderers.ballot_renderer(template, {"candidates": names, "candidate_vote_limit": 3})
        tables = docx_tables(out)
        assert len(tables) == 1
        assert len(tables[0].columns) == 1
        text = docx_text(out)
        for n in names:
            assert n in text
        assert "Count: 3" in text

    def test_two_columns_above_threshold(self):
        names = [f"Cand {i}" for i in range(9)]  # > 8 -> two columns
        template = make_docx(["{{BLOCK:BALLOT_CANDIDATES}}"])
        out = renderers.ballot_renderer(template, {"candidates": names, "candidate_vote_limit": 4})
        tables = docx_tables(out)
        assert len(tables) == 1
        assert len(tables[0].columns) == 2

    def test_no_candidates_removes_anchor(self):
        template = make_docx(["Before", "{{BLOCK:BALLOT_CANDIDATES}}", "After"])
        out = renderers.ballot_renderer(template, {"candidates": []})
        text = docx_text(out)
        assert "{{BLOCK:BALLOT_CANDIDATES}}" not in text
        assert docx_tables(out) == []


class TestElectronicBallotRenderer:
    def test_builds_four_column_table_with_checkboxes(self):
        names = [f"Cand {i}" for i in range(4)]
        template = make_docx(["{{BLOCK:ELECTRONIC_BALLOT_CANDIDATES}}"])
        out = renderers.electronic_ballot_renderer(
            template, {"candidates": names, "candidate_vote_limit": 2}
        )
        tables = docx_tables(out)
        assert len(tables) == 1
        assert len(tables[0].columns) == 4
        text = docx_text(out)
        assert "☐" in text  # ballot checkbox glyph
        for n in names:
            assert n in text


class TestRegistry:
    def test_registry_exposes_all_renderer_types(self):
        assert set(renderers.RENDERERS) == {
            "simple",
            "proxy",
            "ballot",
            "electronic_ballot",
            "notice_candidacy",
        }

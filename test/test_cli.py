"""Tests for dvdrip._cli."""

import pytest

from dvdrip._cli import _parse_titles_arg
from dvdrip._errors import UserError


class TestParseTitlesArg:
    def test_all_titles(self) -> None:
        assert _parse_titles_arg("*") is None

    def test_single_number(self) -> None:
        assert _parse_titles_arg("3") == [3]

    def test_comma_separated(self) -> None:
        assert _parse_titles_arg("1,3,5") == [1, 3, 5]

    def test_range(self) -> None:
        assert _parse_titles_arg("2-5") == [2, 3, 4, 5]

    def test_range_no_start(self) -> None:
        assert _parse_titles_arg("-3") == [1, 2, 3]

    def test_mixed(self) -> None:
        assert _parse_titles_arg("1,3-5,7") == [1, 3, 4, 5, 7]

    def test_deduplicates(self) -> None:
        assert _parse_titles_arg("1,1,2") == [1, 2]

    def test_invalid_raises(self) -> None:
        with pytest.raises(UserError, match="integer ranges"):
            _parse_titles_arg("abc")

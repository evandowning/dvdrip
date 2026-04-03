"""Tests for dvdrip._errors."""

import pytest

from dvdrip._errors import UserError


class TestUserError:
    def test_message(self) -> None:
        err = UserError("something went wrong")
        assert err.message == "something went wrong"
        assert str(err) == "something went wrong"

    def test_is_exception(self) -> None:
        msg = "bad input"
        with pytest.raises(UserError, match=msg):
            raise UserError(msg)

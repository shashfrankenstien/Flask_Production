import pytest

from flask_production.state import BaseStateHandler


def test_base_state_handler_is_abstract():
	with pytest.raises(TypeError, match="abstract"):
		BaseStateHandler()

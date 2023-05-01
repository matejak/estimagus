import pytest

import estimage.plugins as tm
import estimage.plugins.null as null_plugin


def test_get_plugin_dynamically():
    assert tm.get_plugin("null") == null_plugin
    with pytest.raises(NameError):
        assert tm.get_plugin("nuff")

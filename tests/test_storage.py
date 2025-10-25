import tempfile
import os

import pytest

import estimage.inidata as tm
from estimage import persistence
from estimage.persistence.card import ini
import estimage.data as data
from tests.test_events import early_event, less_early_event


@pytest.fixture
def temp_filename():
    fd, filename = tempfile.mkstemp()
    os.close(fd)

    yield filename

    os.remove(filename)


@pytest.fixture
def inifile_temploc(temp_filename):
    class TmpIniCardIO:
        CONFIG_FILENAME = temp_filename

    yield TmpIniCardIO
    

def test_persistence_type_sanity():
    with pytest.raises(RuntimeError, match="class"):
        persistence.get_persistence(int, "toml")
    with pytest.raises(RuntimeError, match="format"):
        persistence.get_persistence(data.BaseCard, "zozo")
    persistence.get_persistence(data.BaseCard, "toml")


# To test: Loader knows how to load/save respective stuff
def test_save_tree_load_same(temp_filename):
    t2 = data.BaseCard("second")
    cardio_inifile_cls = persistence.get_persistence(t2.__class__, "toml")
    cardio_inifile_cls.SAVE_FILENAME = temp_filename
    cardio_inifile_cls.LOAD_FILENAME = temp_filename

    t1 = data.BaseCard("first")
    t1.add_element(t2)
    t1.save_metadata(cardio_inifile_cls)

    t2.save_metadata(cardio_inifile_cls)

    loaded_card = data.BaseCard.load_metadata("first", cardio_inifile_cls)
    assert loaded_card.name == "first"
    assert loaded_card.children[0].name == "second"
    assert loaded_card.children[0].parent is loaded_card
    assert loaded_card.parent is None

    loaded_leaf = data.BaseCard.load_metadata("second", cardio_inifile_cls)
    assert loaded_leaf.parent.name == "first"

    t3 = data.BaseCard("third")
    loaded_leaf.add_element(t3)

    loaded_leaf.save_metadata(cardio_inifile_cls)
    t3.save_metadata(cardio_inifile_cls)

    loaded_subleaf = data.BaseCard.load_metadata("third", cardio_inifile_cls)
    assert loaded_subleaf.parent.name == "second"
    assert loaded_subleaf.parent.parent.name == "first"

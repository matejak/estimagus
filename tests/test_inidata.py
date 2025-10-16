import tempfile
import os
import datetime

import pytest

import estimage.inidata as tm
from estimage import persistence
from estimage.persistence.card import ini
import estimage.data as data


@pytest.fixture
def temp_filename():
    fd, filename = tempfile.mkstemp()
    os.close(fd)

    yield filename

    os.remove(filename)


def get_file_based_io(io_type, backend, filename):
    io = persistence.get_persistence(io_type, backend)
    io.SAVE_FILENAME = filename
    io.LOAD_FILENAME = filename
    return io


@pytest.fixture
def appdata_inifile(temp_filename):
    class TmpIniAppdata(tm.IniAppdata):
        CONFIG_FILENAME = temp_filename

    yield TmpIniAppdata


def test_appdata_storage(appdata_inifile):
    data = appdata_inifile()
    data.RETROSPECTIVE_PERIOD = [
        datetime.datetime(2001, 4, 1),
        datetime.datetime(2001, 6, 30),
    ]
    data.PROJECTIVE_QUARTER = "abcd"
    data.RETROSPECTIVE_QUARTER = "cd00"
    data.save()

    data2 = appdata_inifile.load()
    assert data2.RETROSPECTIVE_PERIOD == data.RETROSPECTIVE_PERIOD
    assert data2.PROJECTIVE_QUARTER == data.PROJECTIVE_QUARTER
    assert data2.RETROSPECTIVE_QUARTER == data.RETROSPECTIVE_QUARTER

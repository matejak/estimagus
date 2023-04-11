import datetime

import estimage.plugins.redhat_compliance as tm


def test_period_conversion():
    assert tm.epoch_start_to_datetime("CY22Q1") == datetime.datetime(2022, 1, 1)
    assert tm.epoch_start_to_datetime("CY23Q1") == datetime.datetime(2023, 1, 1)
    assert tm.epoch_start_to_datetime("CY23Q2") == datetime.datetime(2023, 4, 1)
    assert tm.epoch_start_to_datetime("CY23Q3") == datetime.datetime(2023, 7, 1)

    assert tm.epoch_end_to_datetime("CY23Q4") == datetime.datetime(2023, 12, 31)
    assert tm.epoch_end_to_datetime("CY24Q1") == datetime.datetime(2024, 3, 31)


def test_next_period():
    assert tm.next_epoch_of("CY22Q1") == "CY22Q2"
    assert tm.next_epoch_of("CY22Q2") == "CY22Q3"
    assert tm.next_epoch_of("CY22Q4") == "CY23Q1"

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


def test_date_to_period():
    assert tm.datetime_to_epoch(datetime.datetime(2022, 1, 1)) == "CY22Q1"
    assert tm.datetime_to_epoch(datetime.datetime(2022, 4, 1)) == "CY22Q2"
    assert tm.datetime_to_epoch(datetime.datetime(2023, 3, 31)) == "CY23Q1"
    assert tm.datetime_to_epoch(datetime.datetime(2023, 11, 30)) == "CY23Q4"


def tests_days_to_next_epoch():
    assert tm.days_to_next_epoch(datetime.datetime(2022, 3, 31)) == 0
    assert tm.days_to_next_epoch(datetime.datetime(2023, 12, 31)) == 0
    assert tm.days_to_next_epoch(datetime.datetime(2023, 11, 30)) == 31

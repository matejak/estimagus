import estimage.entities.status as tm


def test_status_extraction():
    assert tm.get_canonical_status("bzzt") == "bzzt"
    assert tm.get_canonical_status("0") == "irrelevant"
    assert tm.get_canonical_status("2") == "todo"
    assert tm.get_canonical_status("10") == "irrelevant"

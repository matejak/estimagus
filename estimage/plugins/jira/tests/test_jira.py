import estimage.plugins.jira as tm

from estimage import data


def test_resolve_inheritance_trivial():
    a = data.BaseTarget("")
    tm.resolve_inheritance_of_attributes("a", dict(a=a), dict())



def test_format_stats():
    data = tm.Collected(Retrospective=0, Projective=0, Events=0)
    assert tm.stats_to_summary(data) == "Collected nothing."

    data = tm.Collected(Retrospective=1, Projective=0, Events=0)
    assert tm.stats_to_summary(data) == "Collected 1 retrospective items."

    data = tm.Collected(Retrospective=1, Projective=0, Events=1)
    assert tm.stats_to_summary(data) == "Collected 1 retrospective items and 1 events."

    data = tm.Collected(Retrospective=1, Projective=2, Events=1)
    assert tm.stats_to_summary(data) == "Collected 1 retrospective items, 2 planning items and 1 events."

    data = tm.Collected(Retrospective=0, Projective=2, Events=1)
    assert tm.stats_to_summary(data) == "Collected 2 planning items and 1 events."

    data = tm.Collected(Retrospective=0, Projective=0, Events=5)
    assert tm.stats_to_summary(data) == "Collected 5 events."

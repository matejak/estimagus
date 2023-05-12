import estimage.plugins.jira as tm

from estimage import data



def test_resolve_inheritance_trivial():
    a = data.BaseTarget("")
    tm.resolve_inheritance_of_attributes("a", dict(a=a), dict())

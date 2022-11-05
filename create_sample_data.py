import app.simpledata as sd


def create_task(name):
    t = sd.Target()
    t.name = name
    t.title = f"Issue {name}"
    t.description = f"Description of Issue {name}"
    t.save_metadata()
    return t


def create_epic(name, children=None):
    t = sd.Target()
    t.name = name
    t.title = f"Epic {name}"
    t.description = f"Description of Epic {name}"
    if children:
        t.dependents = children
    t.save_metadata()
    return t


def create_tasks_and_epics():
    t1 = create_task("one")
    t2 = create_task("two")
    t3 = create_task("three")
    e1 = create_epic("first", children=[t1, t2])
    e3 = create_epic("deep", children=[t3])
    e2 = create_epic("shallow", children=[e3])


if __name__ == "__main__":
    create_tasks_and_epics()

import estimage.simpledata as sd


def create_task(cls, name, points):
    t = cls()
    t.name = name
    t.point_cost = points
    t.title = f"Issue {name}"
    t.description = f"Description of Issue {name}"
    t.save_metadata()
    t.save_point_cost()
    return t


def create_projective_task(name, points):
    return create_task(sd.ProjTarget, name, points)


def create_retrospective_task(name, points):
    return create_task(sd.RetroTarget, name, points)


def create_epic(cls, name, children=None):
    t = cls()
    t.name = name
    t.title = f"Epic {name}"
    t.description = f"Description of Epic {name}"
    if children:
        t.dependents = children
    t.save_metadata()
    return t


def create_projective_epic(name, children=None):
    return create_epic(sd.ProjTarget, name, children)


def create_retrospective_epic(name, children=None):
    return create_epic(sd.RetroTarget, name, children)


def create_projective_tasks_and_epics():
    t1 = create_projective_task("future-one", 1)
    t2 = create_projective_task("future-two", 2)
    t3 = create_projective_task("future-three", 3)
    create_projective_epic("future-first", children=[t1, t2])
    e3 = create_projective_epic("future-deep", children=[t3])
    create_projective_epic("future-shallow", children=[e3])


def create_retrospective_events():
    pass


def create_retrospective_tasks_and_epics():
    t1 = create_retrospective_task("past-one", 1)
    t2 = create_retrospective_task("past-two", 2)
    t3 = create_retrospective_task("past-three", 3)
    create_retrospective_epic("past-first", children=[t1, t2])
    e3 = create_retrospective_epic("past-deep", children=[t3])
    create_retrospective_epic("past-shallow", children=[e3])

    t4 = create_retrospective_task("past-four", 5)
    t5 = create_retrospective_task("past-five", 4)
    create_retrospective_epic("past-second", children=[t4, t5])


if __name__ == "__main__":
    create_projective_tasks_and_epics()
    create_retrospective_tasks_and_epics()

import dataclasses
import typing

import estimage.simpledata


@dataclasses.dataclass
class Workload:
    points: float = 0
    targets: typing.List[str] = dataclasses.field(default_factory=list)
    point_parts: typing.Dict[str, float] = dataclasses.field(default_factory=dict)
    proportions: typing.Dict[str, float] = dataclasses.field(default_factory=dict)

    @classmethod
    def of_person(cls, person_name, targets, model=None):
        ret = cls()
        if not model:
            model = estimage.simpledata.get_model(targets)
        for target in targets:
            if person_name in target.collaborators:
                ret._apply_target(target, model)
        return ret


    def _apply_target(self, target, model):
        collaborating_group = set(target.collaborators)
        collaborating_group.add(target.assignee)
        proportion = 1.0 / len(target.collaborators)
        points_contribution = model.remaining_point_estimate_of(target.name).expected
        points_contribution *= proportion
        self.points += points_contribution
        self.point_parts[target.name] = points_contribution
        self.proportions[target.name] = proportion
        self.targets.append(target.name)


def get_all_collaborators(targets):
    ret = set()
    for t in targets:
        ret.update(set(t.collaborators))
        ret.add(t.assignee)
    return ret


def get_all_workloads(targets, model=None):
    all_collaborators = get_all_collaborators(targets)
    ret = dict()
    for name in all_collaborators:
        ret[name] = Workload.of_person(name, targets, model)
    return ret


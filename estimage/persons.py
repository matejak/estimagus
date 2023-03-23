import dataclasses
import typing

import numpy as np
import scipy as sp

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
    if "" in ret:
        ret.remove("")
    return ret


def get_all_workloads(targets, model=None):
    all_collaborators = get_all_collaborators(targets)
    ret = dict()
    for name in all_collaborators:
        ret[name] = Workload.of_person(name, targets, model)
    return ret


# For a naming reference, see https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.linprog.html
def gen_bub(task_sizes, persons_potential):
    ret = np.ones(2 * len(persons_potential)) * sum(task_sizes) / sum(persons_potential)
    for i, pot in enumerate(persons_potential):
        ret[2 * i] *= pot
        ret[2 * i + 1] *= -pot
    return ret


def gen_c(task_sizes, persons_potential):
    num_tasks = len(task_sizes)
    num_persons = len(persons_potential)
    ret = np.zeros(num_tasks * num_persons + num_persons * 2)
    for i in range(1, num_persons + 1):
        ret[-2 * i] = 1
    return ret


def gen_Aub(task_sizes, persons_potential):
    num_tasks = len(task_sizes)
    num_persons = len(persons_potential)
    ret = np.zeros((num_persons * 2, num_tasks * num_persons + num_persons * 2))
    for perso_idx in range(num_persons):
        ret[perso_idx * 2, perso_idx * num_tasks:(perso_idx * num_tasks + num_tasks)] = 1
        ret[perso_idx * 2, num_persons * num_tasks + perso_idx * 2] = -1
        ret[perso_idx * 2 + 1, perso_idx * num_tasks:(perso_idx * num_tasks + num_tasks)] = -1
        ret[perso_idx * 2 + 1, num_persons * num_tasks + 2 * perso_idx + 1] = -1
    return ret


def gen_Aeq(task_sizes, persons_potential):
    num_tasks = len(task_sizes)
    num_persons = len(persons_potential)
    ret = np.zeros((num_tasks + num_persons, num_tasks * num_persons + num_persons * 2))
    for task_idx in range(num_tasks):
        sl = slice(task_idx, num_tasks * num_persons, num_tasks)
        ret[task_idx, sl] = 1
    for perso_idx in range(num_persons):
        ret[num_tasks + perso_idx, num_persons * num_tasks + 2 * perso_idx] = 1
        ret[num_tasks + perso_idx, num_persons * num_tasks + 2 * perso_idx + 1] = -1
    return ret


def gen_beq(task_sizes, persons_potential):
    num_tasks = len(task_sizes)
    num_persons = len(persons_potential)
    ret = np.zeros(num_tasks + num_persons)
    for task_idx in range(num_tasks):
        ret[task_idx] = task_sizes[task_idx]
    return ret


def solve(task_sizes, persons_potential):
    num_tasks = len(task_sizes)
    num_persons = len(persons_potential)
    interesting_solution_len = num_tasks * num_persons
    c = gen_c(task_sizes, persons_potential)
    Aub = gen_Aub(task_sizes, persons_potential)
    bub = gen_bub(task_sizes, persons_potential)
    Aeq = gen_Aeq(task_sizes, persons_potential)
    beq = gen_beq(task_sizes, persons_potential)
    solution = sp.optimize.linprog(c, Aub, bub, Aeq, beq)
    ret = solution.x[:interesting_solution_len].reshape(num_persons, num_tasks)
    return ret

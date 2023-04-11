import dataclasses
import typing
import collections

import numpy as np
import scipy as sp

import estimage.data as data


@dataclasses.dataclass
class Workload:
    name: str = ""
    points: float = 0
    targets: typing.List[data.BaseTarget] = dataclasses.field(default_factory=list)
    point_parts: typing.Dict[str, float] = dataclasses.field(default_factory=dict)
    proportions: typing.Dict[str, float] = dataclasses.field(default_factory=dict)


def get_people_associaged_with(target: data.BaseTarget) -> typing.Set[str]:
    associated_people = set()
    associated_people.add(target.assignee)
    associated_people.update(set(target.collaborators))
    associated_people.discard("")
    return associated_people


@dataclasses.dataclass
class Workloads:
    points: float = 0
    targets: typing.List[data.BaseTarget] = dataclasses.field(default_factory=list)
    persons_potential: typing.Dict[str, float] = dataclasses.field(
        default_factory=lambda: collections.defaultdict(lambda: 0))

    def __init__(self,
                 targets: typing.Iterable[data.BaseTarget],
                 model: data.EstiModel,
                 * args, ** kwargs):
        super().__init__(* args, ** kwargs)

        self.model = model
        self.targets_by_name = collections.OrderedDict()
        self.targets = targets
        self.persons_potential = dict()
        for i, t in enumerate(targets):
            self.targets_by_name[t.name] = t
        self._target_persons_map = dict()
        self._fill_in_collaborators()

    def _fill_in_collaborators(self):
        all_collaborators = set()
        for name, t in self.targets_by_name.items():
            self.points += self.model.remaining_point_estimate_of(name).expected

            associated_people = get_people_associaged_with(t)
            self._target_persons_map[name] = associated_people
            all_collaborators.update(associated_people)

        for c in all_collaborators:
            self.persons_potential[c] = 1.0

    def get_who_works_on(self, target_name: str) -> typing.Set[str]:
        return self._target_persons_map.get(target_name, set())

    def of_person(self, person_name: str) -> Workload:
        raise NotImplementedError()


class SimpleWorkloads(Workloads):

    def of_person(self, person_name: str) -> Workload:
        ret = Workload(name=person_name)
        for target in self.targets:
            if person_name in target.collaborators:
                self._apply_target(ret, person_name, target)
        return ret

    def _apply_target(self, ret, who, target):
        collaborating_group = self.get_who_works_on(target.name)
        own_potential = self.persons_potential[who]
        target_potential = sum([self.persons_potential.get(name) for name in collaborating_group])

        proportion = own_potential / target_potential
        points_contribution = self.model.remaining_point_estimate_of(target.name).expected
        points_contribution *= proportion
        ret.points += points_contribution
        ret.point_parts[target.name] = points_contribution
        ret.proportions[target.name] = proportion
        ret.targets.append(target)


class OptimizedWorkloads(Workloads):
    def __init__(self,
                 targets: typing.Iterable[data.BaseTarget],
                 model: data.EstiModel,
                 * args, ** kwargs):
        super().__init__(targets, model, * args, ** kwargs)
        self._solution = None
        self.task_totals = np.zeros(len(targets))
        self.persons_indices = dict()
        self.targets_indices = dict()
        self._create_indices()

    def _create_indices(self):
        for index, person_name in enumerate(self.persons_potential):
            self.persons_indices[person_name] = index
        for index, target in enumerate(self.targets):
            self.targets_indices[target.name] = index

    def cost_matrix(self):
        ret = np.ones((len(self.persons_potential), len(self.targets_by_name)))
        ret *= np.inf
        for collab_idx, collab_name in enumerate(self.persons_potential):
            for task_idx, task_name in enumerate(self.targets_by_name):
                task_collaborators = self._target_persons_map[task_name]
                if collab_name in task_collaborators:
                    ret[collab_idx, task_idx] = 1
        return ret

    def solve_problem(self):
        task_sizes = np.array([
            self.model.remaining_point_estimate_of(t.name).expected
            for t in self.targets_by_name.values()])
        if len(task_sizes) == 0 or len(self.persons_potential) == 0:
            return
        costs = self.cost_matrix()
        if len(indices := np.where(np.logical_and(np.min(costs, axis=0) == np.inf, task_sizes > 0))[0]):
            task_names = [self.targets[i].name for i in indices]
            msg = f"Nobody wants to work on some tasks: {task_names}"
            raise ValueError(msg)
        self._solution = solve(task_sizes, self.persons_potential.values(), costs)
        self.task_totals = np.sum(self._solution, axis=0)

    def of_person(self, person_name):
        person_index = self.persons_indices[person_name]
        ret = Workload()
        ret.points = sum(self._solution[person_index])
        for task_index, task_name in enumerate(self.targets_by_name.keys()):
            projection = self._solution[person_index, task_index]
            if projection == 0:
                continue
            ret.targets.append(self.targets_by_name[task_name])
            ret.point_parts[task_name] = projection
            ret.proportions[task_name] = projection / self.task_totals[task_index]
        return ret


def get_all_collaborators(targets):
    ret = set()
    for t in targets:
        ret.update(set(t.collaborators))
        ret.add(t.assignee)
    if "" in ret:
        ret.remove("")
    return ret


# For a naming reference, see https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.linprog.html
# bub:
# 0..num_persons * 2:
#   Either person works less than their potential, or they work more
#   odd(leading) rows represent + work - difference <= (positive) potential
#   even rows represent - work - difference <= - (positive) potential
def gen_bub(task_sizes, persons_potential):
    ret = np.ones(2 * len(persons_potential)) * sum(task_sizes) / sum(persons_potential)
    for i, pot in enumerate(persons_potential):
        coeff_when_person_working_less = -1
        person_working_more_index = i * 2
        person_working_less_index = person_working_more_index + 1

        ret[person_working_more_index] *= pot
        ret[person_working_less_index] *= pot * coeff_when_person_working_less
    return ret


# 0..num_tasks * num_persons: The same meaning as cost matrix that is flattened
# +0..2 * num_persons: Pairs of identical values, represent absolute values
#  of diff between work done by a person and their work potential
def gen_c(task_sizes, persons_potential):
    num_tasks = len(task_sizes)
    num_persons = len(persons_potential)
    ret = np.zeros(num_tasks * num_persons + num_persons * 2)
    for i in range(1, num_persons + 1):
        ret[-2 * i] = 1
    return ret


# Aub rows:
# 0..num_persons * 2:
#   Either person works less than their potential, or they work more
#   The sum of their work minus their potential, their work difference, is defined here
def gen_Aub(task_sizes, persons_potential):
    num_tasks = len(task_sizes)
    num_persons = len(persons_potential)
    ret = np.zeros((num_persons * 2, num_tasks * num_persons + num_persons * 2))
    for perso_idx in range(num_persons):
        persons_work_start_index = perso_idx * num_tasks
        persons_work_end_index = persons_work_start_index + num_tasks
        persons_work_slice = slice(persons_work_start_index, persons_work_end_index)

        one_work_difference_index = num_persons * num_tasks + perso_idx * 2
        other_work_difference_index = one_work_difference_index + 1
        coeff_when_person_working_more = 1
        coeff_when_person_working_less = -1
        person_working_more_index = perso_idx * 2
        person_working_less_index = person_working_more_index + 1

        ret[person_working_more_index, persons_work_slice] = coeff_when_person_working_more
        ret[person_working_more_index, one_work_difference_index] = -1
        ret[person_working_less_index, persons_work_slice] = coeff_when_person_working_less
        ret[person_working_less_index, other_work_difference_index] = -1
    return ret


def _record_lhs_contributions_make_whole_task(Aeq, starting_row_idx, num_tasks, num_persons):
    for task_idx in range(num_tasks):
        sl = slice(task_idx, num_tasks * num_persons, num_tasks)
        Aeq[starting_row_idx + task_idx, sl] = 1


def _record_lhs_differences_are_the_same(Aeq, starting_row_idx, num_tasks, num_persons):
    first_col_index_of_differences = num_persons * num_tasks
    for perso_idx in range(num_persons):
        Aeq[starting_row_idx + perso_idx, first_col_index_of_differences + 2 * perso_idx] = 1
        Aeq[starting_row_idx + perso_idx, first_col_index_of_differences + 2 * perso_idx + 1] = -1


def _record_lhs_no_work_on_unwanted_items(Aeq, starting_row_idx, indices_of_zeros):
    for idx, zero_idx in enumerate(indices_of_zeros):
        Aeq[starting_row_idx + idx, zero_idx] = 1


# Aeq rows:
# 0..num_tasks: Task composition
# +0..num_persons: Two consequent columns are the same
# +0..num_zeros: Work done by person on a task is zero (if the cost is infinite)
def gen_Aeq(task_sizes, persons_potential, labor_cost=None):
    num_tasks = len(task_sizes)
    num_persons = len(persons_potential)
    if labor_cost is None:
        labor_cost = np.ones((num_persons, num_tasks))
    indices_of_zeros = np.where(labor_cost.flatten() == np.inf)[0]
    ret = np.zeros((num_tasks + num_persons + len(indices_of_zeros), num_tasks * num_persons + num_persons * 2))
    _record_lhs_contributions_make_whole_task(ret, 0, num_tasks, num_persons)
    _record_lhs_differences_are_the_same(ret, num_tasks, num_tasks, num_persons)
    zeros_start = num_tasks + num_persons
    _record_lhs_no_work_on_unwanted_items(ret, zeros_start, indices_of_zeros)
    return ret


def _record_rhs_contributions_make_whole_task(beq, starting_idx, task_sizes):
    num_tasks = len(task_sizes)
    for task_idx in range(num_tasks):
        beq[starting_idx + task_idx] = task_sizes[task_idx]


def _record_rhs_differences_are_the_same(beq, starting_row_idx):
    pass


def _record_rhs_no_work_on_unwanted_items(beq, starting_row_idx):
    pass


def gen_beq(task_sizes, persons_potential, labor_cost=None):
    num_tasks = len(task_sizes)
    num_persons = len(persons_potential)
    if labor_cost is None:
        labor_cost = np.ones((num_persons, num_tasks))
    number_of_zeros = np.sum(labor_cost == np.inf)
    ret = np.zeros(num_tasks + num_persons + number_of_zeros)
    _record_rhs_contributions_make_whole_task(ret, 0, task_sizes)
    return ret


def solve(task_sizes, persons_potential, labor_cost=None):
    if len(task_sizes) == 0:
        return []
    if len(persons_potential) == 0:
        msg = "No persons to assign tasks to."
        raise ValueError(msg)
    num_tasks = len(task_sizes)
    num_persons = len(persons_potential)
    interesting_solution_len = num_tasks * num_persons
    c = gen_c(task_sizes, persons_potential)
    Aub = gen_Aub(task_sizes, persons_potential)
    bub = gen_bub(task_sizes, persons_potential)
    Aeq = gen_Aeq(task_sizes, persons_potential, labor_cost)
    beq = gen_beq(task_sizes, persons_potential, labor_cost)
    solution = sp.optimize.linprog(c, Aub, bub, Aeq, beq)
    if not solution.success:
        msg = solution.message
        raise ValueError(msg)
    ret = solution.x[:interesting_solution_len].reshape(num_persons, num_tasks)
    return ret

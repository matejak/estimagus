import dataclasses
import typing
import collections

import numpy as np
import scipy as sp

import estimage.data as data


class WorkloadSummary(typing.NamedTuple):
    expected_effort_of_full_potential: float


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
    persons_indices: typing.Dict[str, int] = dataclasses.field(default_factory=dict)
    targets_indices: typing.Dict[str, int] = dataclasses.field(default_factory=dict)
    work_matrix = np.ndarray
    task_sizes = np.ndarray

    def __init__(self,
                 targets: typing.Iterable[data.BaseTarget],
                 model: data.EstiModel,
                 * args, ** kwargs):
        super().__init__(* args, ** kwargs)

        self.model = model
        self.targets_by_name = collections.OrderedDict()
        self.targets = targets
        self.persons_potential = dict()
        self.persons_indices = dict()
        self.targets_indices = dict()
        for t in targets:
            self.targets_by_name[t.name] = t
        self._target_persons_map = dict()
        self._fill_in_collaborators()
        self.task_sizes = np.array([
            self.model.remaining_point_estimate_of(t.name).expected
            for t in self.targets_by_name.values()])
        self.work_matrix = np.zeros((len(self.persons_potential), len(targets)))
        self._create_indices()

    def _create_indices(self):
        for index, person_name in enumerate(self.persons_potential):
            self.persons_indices[person_name] = index
        for index, target in enumerate(self.targets):
            self.targets_indices[target.name] = index

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

    def summary(self) -> WorkloadSummary:
        effort_per_potential = self.task_sizes.sum() / sum(self.persons_potential.values())
        ret = WorkloadSummary(
            expected_effort_of_full_potential=effort_per_potential,
        )
        return ret


class SimpleWorkloads(Workloads):

    def solve_problem(self):
        for tidx, target in enumerate(self.targets):
            for pidx, person_name in enumerate(self.persons_potential):
                collaborating_group = self.get_who_works_on(target.name)
                if person_name not in collaborating_group:
                    continue

                own_potential = self.persons_potential[person_name]
                target_potential = sum([self.persons_potential.get(name) for name in collaborating_group])

                proportion = own_potential / target_potential
                points_contribution = self.task_sizes[tidx]
                points_contribution *= proportion

                self.work_matrix[pidx, tidx] = points_contribution

    def of_person(self, person_name):
        ret = Workload(name=person_name)
        if person_name not in self.persons_indices:
            return ret
        person_index = self.persons_indices[person_name]
        ret.points = sum(self.work_matrix[person_index])
        task_totals = np.sum(self.work_matrix, axis=0)
        for task_index, task_name in enumerate(self.targets_by_name.keys()):
            projection = self.work_matrix[person_index, task_index]
            if projection == 0:
                continue
            ret.targets.append(self.targets_by_name[task_name])
            ret.point_parts[task_name] = projection
            ret.proportions[task_name] = projection / task_totals[task_index]
        return ret


class OptimizedWorkloads(Workloads):
    def __init__(self,
                 targets: typing.Iterable[data.BaseTarget],
                 model: data.EstiModel,
                 * args, ** kwargs):
        super().__init__(targets, model, * args, ** kwargs)
        self.task_totals = np.zeros(len(targets))
        self.targets_indices = dict()
        self._create_indices()

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
        if len(self.task_sizes) == 0 or len(self.persons_potential) == 0:
            return
        costs = self.cost_matrix()
        if len(indices := np.where(np.logical_and(np.min(costs, axis=0) == np.inf, self.task_sizes > 0))[0]):
            task_names = [self.targets[i].name for i in indices]
            msg = f"Nobody wants to work on some tasks: {task_names}"
            raise ValueError(msg)
        self.work_matrix = solve(self.task_sizes, self.persons_potential.values(), costs)
        self.task_totals = np.sum(self.work_matrix, axis=0)

    def of_person(self, person_name):
        person_index = self.persons_indices[person_name]
        ret = Workload()
        ret.points = sum(self.work_matrix[person_index])
        for task_index, task_name in enumerate(self.targets_by_name.keys()):
            projection = self.work_matrix[person_index, task_index]
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
# +0..num_persons: Nothing to see here
def gen_bub(task_sizes, persons_potential):
    work_per_potential_unit = sum(task_sizes) / sum(persons_potential)
    num_persons = len(persons_potential)
    ret = np.ones(3 * num_persons) * work_per_potential_unit
    coeff_when_person_working_less = -1
    for i, pot in enumerate(persons_potential):
        person_working_more_index = i * 2
        person_working_less_index = person_working_more_index + 1

        ret[person_working_more_index] *= pot
        ret[person_working_less_index] *= pot * coeff_when_person_working_less
    ret[2 * num_persons:] = 0
    return ret


# 0..num_tasks * num_persons: The same meaning as cost matrix that is flattened
# +0..num_persons: Absolute values of diff between work done by a person and their work potential
# +0..num_persons: Effort of particular person (work done over potential)
# +1: Maximum of the person's effort
def gen_c(task_sizes, persons_potential):
    num_tasks = len(task_sizes)
    num_persons = len(persons_potential)
    ret = np.zeros(num_tasks * num_persons + num_persons * 2 + 1)
    index_of_first_diff = num_persons * num_tasks
    for i in range(1, num_persons + 1):
        ret[i + index_of_first_diff] = 0.5 / num_persons
    ret[-1] = 1
    return ret


def _define_persons_overwork_or_underwork(Aub, starting_row_idx, num_persons, num_tasks):
    for perso_idx in range(num_persons):
        persons_work_start_index = perso_idx * num_tasks
        persons_work_end_index = persons_work_start_index + num_tasks
        persons_work_slice = slice(persons_work_start_index, persons_work_end_index)

        work_difference_index = num_persons * num_tasks + perso_idx
        coeff_when_person_working_more = 1
        coeff_when_person_working_less = -1
        person_working_more_index = starting_row_idx + perso_idx * 2
        person_working_less_index = starting_row_idx + person_working_more_index + 1

        Aub[person_working_more_index, persons_work_slice] = coeff_when_person_working_more
        Aub[person_working_more_index, work_difference_index] = -1
        Aub[person_working_less_index, persons_work_slice] = coeff_when_person_working_less
        Aub[person_working_less_index, work_difference_index] = -1


def _define_persons_greatest_effort(Aub, starting_row_idx, num_persons, num_tasks):
    greatest_effort_index = num_tasks * num_persons + 2 * num_persons
    for perso_idx in range(num_persons):
        current_effort_index = num_tasks * num_persons + num_persons + perso_idx
        Aub[starting_row_idx + perso_idx, current_effort_index] = 1
        Aub[starting_row_idx + perso_idx, greatest_effort_index] = -1


# Aub rows:
# 0..num_persons * 2:
#   Either person works less than their potential, or they work more
#   The sum of their work minus their potential, their work difference, is defined here
# +0..num_persons: Definition of max of person's efforts
def gen_Aub(task_sizes, persons_potential):
    num_tasks = len(task_sizes)
    num_persons = len(persons_potential)
    ret = np.zeros((
        num_persons * 3,
        num_tasks * num_persons + num_persons * 2 + 1))
    starting_idx = 0
    _define_persons_overwork_or_underwork(ret, starting_idx, num_persons, num_tasks)
    starting_idx += 2 * num_persons
    _define_persons_greatest_effort(ret, starting_idx, num_persons, num_tasks)
    return ret


def _record_lhs_contributions_make_whole_task(Aeq, starting_row_idx, num_tasks, num_persons):
    for task_idx in range(num_tasks):
        sl = slice(task_idx, num_tasks * num_persons, num_tasks)
        Aeq[starting_row_idx + task_idx, sl] = 1


def _record_lhs_differences_are_the_same(Aeq, starting_row_idx):
    pass


def _record_lhs_no_work_on_unwanted_items(Aeq, starting_row_idx, indices_of_zeros):
    for idx, zero_idx in enumerate(indices_of_zeros):
        Aeq[starting_row_idx + idx, zero_idx] = 1


def _record_lhs_effort_applied(Aeq, starting_row_idx, persons_potential, num_tasks):
    num_persons = len(persons_potential)
    effort_index_base = num_persons * num_tasks + num_persons
    for person_idx, potential in enumerate(persons_potential):
        relative_effort = 1.0 / potential
        task_slice = slice(person_idx * num_tasks, (person_idx + 1) * num_tasks)
        effort_index = effort_index_base + person_idx

        Aeq[starting_row_idx + person_idx, task_slice] = 1.0 * relative_effort
        Aeq[starting_row_idx + person_idx, effort_index] = -1


# Aeq rows:
# 0..num_tasks: Task composition
# +0..num_zeros: Work done by person on a task is zero (if the cost is infinite)
# +0..num_persons: Definition of work effort (work done divided by potential)
def gen_Aeq(task_sizes, persons_potential, labor_cost=None):
    num_tasks = len(task_sizes)
    num_persons = len(persons_potential)
    if labor_cost is None:
        labor_cost = np.ones((num_persons, num_tasks))
    indices_of_zeros = np.where(labor_cost.flatten() == np.inf)[0]
    ret = np.zeros((
        num_tasks + len(indices_of_zeros) + num_persons,
        num_tasks * num_persons + num_persons * 2 + 1))
    starting_index = 0
    _record_lhs_contributions_make_whole_task(ret, starting_index, num_tasks, num_persons)
    starting_index += num_tasks
    _record_lhs_no_work_on_unwanted_items(ret, starting_index, indices_of_zeros)
    starting_index += len(indices_of_zeros)
    _record_lhs_effort_applied(ret, starting_index, persons_potential, num_tasks)
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
    ret = np.zeros(num_tasks + number_of_zeros + num_persons)
    _record_rhs_contributions_make_whole_task(ret, 0, task_sizes)
    return ret


def solve(task_sizes, persons_potential, labor_cost=None):
    num_tasks = len(task_sizes)
    num_persons = len(persons_potential)
    if num_tasks == 0:
        return []
    if num_persons == 0:
        msg = "No persons to assign tasks to."
        raise ValueError(msg)
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

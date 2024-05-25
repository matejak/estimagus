import re
import datetime
import collections
import dateutil.relativedelta
import typing

import flask

from ... import simpledata, data
from .. import jira, redhat_jira
from ...webapp import web_utils
from .forms import CryptoForm
from ..jira.forms import AuthoritativeForm, ProblemForm


Statuses = redhat_jira.Statuses
MPLPointPlot = redhat_jira.MPLPointPlot


EXPORTS = dict(
    AuthoritativeForm="AuthoritativeForm",
    ProblemForm="ProblemForm",
    MPLPointPlot="MPLPointPlot",
    Statuses="Statuses",
    Workloads="Workloads",
)


PROJECT_NAME = "CRYPTO"


TEMPLATE_OVERRIDES = {
    "tree_view_retrospective.html": "crypto-retrotree.html",
}


class InputSpec(redhat_jira.InputSpec):
    @classmethod
    def from_form_and_app(cls, form, app) -> "InputSpec":
        ret = super().from_form_and_app(form, app)
        ret.cutoff_date = app.get_config_option("RETROSPECTIVE_PERIOD")[0]
        return ret

    def set_cutoff_date(self, input_form):
        pass

    def set_queries(self, input_form):
        sprint = "openSprints()"
        query_tpl = "filter = 12350823 AND Sprint in {sprint} AND issuetype in (task, bug, Story)"
        self.retrospective_query = query_tpl.format(sprint=sprint)
        if input_form.project_next.data:
            sprint = "futureSprints()"
        self.projective_query = query_tpl.format(sprint=sprint)


class Importer(redhat_jira.Importer):
    def _get_owner_epic_of(self, assignee, committed):
        if not assignee:
            assignee = "nobody"
        name = f"{PROJECT_NAME}-{assignee}"
        if committed:
            name += "-C"

        epic = self._cards_by_id.get(name)

        if not epic:
            epic = self.item_class(name)
            epic.assignee = assignee
            epic.title = f"Issues of {assignee}"
            epic.tier = 1
            epic.status = "in_progress"
            if committed:
                epic.title = "Committed " + epic.title
                epic.tier = 0
            self._cards_by_id[name] = epic
        return epic

    def put_cards_under_artificial_epics(self, tasks):
        epic_names = set()
        for task_name in tasks:
            task = self._cards_by_id[task_name]
            epic = self._get_owner_epic_of(task.assignee, "label:Committed" in task.tags)
            epic.add_element(task)
            epic_names.add(epic.name)
        return epic_names

    def _parent_has_only_unestimated_children(self, pname):
        children = self._cards_by_id[pname].children
        rolling_sum = 0
        for c in children:
            rolling_sum += abs(c.point_cost)
        return rolling_sum == 0

    def _propagate_estimates_of_estimated_task_to_unestimated_subtasks(self, pname):
        parent = self._cards_by_id[pname]
        if parent.point_cost == 0:
            return
        if not self._parent_has_only_unestimated_children(pname):
            return
        points_per_child = parent.point_cost / len(parent.children)
        for c in parent.children:
            c.point_cost = points_per_child

    def distribute_subtasks_points_to_tasks(self):
        names_of_not_parents = set()
        for c in self._cards_by_id.values():
            if not c.children and c.parent:
                names_of_not_parents.add(c.name)
        names_of_parents_of_not_parents = {self._cards_by_id[cname].parent.name for cname in names_of_not_parents}
        for pn in names_of_parents_of_not_parents:
            self._propagate_estimates_of_estimated_task_to_unestimated_subtasks(pn)

    def _query_children_to_get_children(self, parent_name, query_order):
        return False

    def _export_jira_tree_to_cards(self, root_results):
        new_cards = super()._export_jira_tree_to_cards(root_results)
        new_epic_names = self.put_cards_under_artificial_epics(root_results)
        return new_cards.union(new_epic_names)

    def import_data(self, spec):
        super().import_data(spec)
        self.distribute_subtasks_points_to_tasks()

    def merge_jira_item_without_children(self, item):

        result = super().merge_jira_item_without_children(item)

        result.point_cost = self._get_points_of(item)
        return result

    @classmethod
    def _accepted(cls, jira_string, item):
        resolution = item.get_field("resolution")
        resolution_text = ""
        if resolution:
            resolution_text = resolution.name
        if jira_string == "Closed":
            if "Accepted" in item.get_field("labels"):
                return "Done"
            elif resolution_text == "Done" and item.get_field("issuetype").name == "Sub-task":
                return "Done"
            elif resolution_text == "Done":
                return "Review"
            else:
                jira_string = "not_done_therefore_irrelevant"
        return jira_string

    @classmethod
    def _status_to_state(cls, item, jira_string):
        item_name = item.key

        if item_name.startswith(PROJECT_NAME + "-"):
            jira_string = cls._accepted(jira_string, item)
            return super()._status_to_state(item, jira_string)
        else:
            jira_string = cls._accepted(jira_string, item)
            return super()._status_to_state(item, jira_string)


def do_stuff(spec, ios_by_target):
    importer = Importer(spec)
    importer.import_data()
    importer.save(ios_by_target)
    return importer.get_collected_stats()


class Workloads:
    def __init__(self,
                 cards: typing.Iterable[data.BaseCard],
                 model: data.EstiModel,
                 * args, ** kwargs):
        cards = [t for t in cards if t.tier == 0]
        super().__init__(* args, model=model, cards=cards, ** kwargs)

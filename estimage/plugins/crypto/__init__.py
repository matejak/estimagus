import re
import datetime
import collections
import dateutil.relativedelta
import typing

import flask

from ... import simpledata, data, persistence
from .. import jira, redhat_compliance
from ...webapp import web_utils
from ...entities import status
from ...visualize.burndown import StatusStyle
from .forms import CryptoForm


JiraFooter = jira.JiraFooter

EXPORTS = dict(
    Footer="JiraFooter",
    MPLPointPlot="MPLPointPlot",
    Statuses="Statuses",
    Workloads="Workloads",
)


PROJECT_NAME = "CRYPTO"

class Statuses:
    def __init__(self):
        super().__init__()
        self.statuses.extend([
            status.Status.create("rhel-in_progress", started=True, wip=True, done=False),
            status.Status.create("rhel-integration", started=True, wip=False, done=False),
        ])


class MPLPointPlot:
    def get_styles(self):
        ret = super().get_styles()
        ret["rhel-in_progress"] = StatusStyle(color=(0.1, 0.2, 0.5, 0.4), label="BZ In Progress", weight=60)
        ret["rhel-integration"] = StatusStyle(color=(0.2, 0.4, 0.7, 0.6), label="BZ Integration", weight=61)
        return ret



TEMPLATE_OVERRIDES = {
    "tree_view_retrospective.html": "crypto-retrotree.html",
}

class InputSpec(jira.InputSpec):
    @classmethod
    def from_form_and_app(cls, form, app) -> "InputSpec":
        ret = cls()
        ret.server_url = "https://issues.redhat.com"
        ret.token = form.token.data
        ret.cutoff_date = app.get_config_option("RETROSPECTIVE_PERIOD")[0]
        query = f"project = {PROJECT_NAME} AND type = Task AND sprint in openSprints()"
        query = "filter = 12350823 AND Sprint in openSprints() AND labels = committed AND issuetype in (task, bug, Story)"
        query = "filter = 12350823 AND Sprint in openSprints() AND issuetype in (task, bug, Story)"
        ret.retrospective_query = query
        ret.projective_query = ""
        ret.item_class = app.get_final_class("BaseCard")
        return ret


def get_tasks(jira_connection, query, all_items_by_name, parents_child_keymap):
    tasks = jira_connection.search_issues(
        query, expand="changelog,renderedFields", maxResults=0)

    new_task_names = set()
    for task in tasks:
        new_task_names.add(task.key)
        if task.key in all_items_by_name:
            continue
        all_items_by_name[task.key] = task
        jira.identify_epic_subtasks(jira_connection, task, all_items_by_name, parents_child_keymap)
        jira.recursively_identify_task_subtasks(jira_connection, task, all_items_by_name, parents_child_keymap)
    return new_task_names


class Importer(jira.Importer):
    STORY_POINTS = "customfield_12310243"
    EPIC_LINK = "customfield_12311140"

    def _get_points_of(self, item):
        return float(item.get_field(self.STORY_POINTS) or 0)

    # def _set_points_of(self, item, points):
        # item.update({self.STORY_POINTS: round(points, 2)})

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
            if committed:
                epic.title = "Committed " + epic.title
                epic.tier = 0
            self._cards_by_id[name] = epic
        return epic

    def put_tasks_under_artificial_epics(self, tasks):
        epic_names = set()
        for task_name in tasks:
            task = self._cards_by_id[task_name]
            epic = self._get_owner_epic_of(task.assignee, "label:Committed" in task.tags)
            epic.add_element(task)
            epic_names.add(epic.name)
        return epic_names


    def import_data(self, spec):
        retro_tasks = set()
        issue_names_requiring_events = set()
        if spec.retrospective_query:
            self.report("Gathering retro stuff")
            retro_tasks = get_tasks(
                self.jira, spec.retrospective_query, self._all_issues_by_name,
                self._parents_child_keymap)
            new_cards = self.export_jira_epic_chain_to_cards(retro_tasks)
            self._cards_by_id.update(new_cards)
            new_epic_names = self.put_tasks_under_artificial_epics(retro_tasks)
            self._retro_cards.update(new_cards.keys())
            self._retro_cards.update(new_epic_names)
            issue_names_requiring_events.update(new_cards.keys())
            self._cards_by_id.update(new_cards)

        proj_tasks = set()
        if spec.projective_query:
            self.report("Gathering proj stuff")
            proj_tasks = get_epics_and_their_tasks_by_id(
                self.jira, spec.projective_query, self._all_issues_by_name,
                self._parents_child_keymap)
            new_names = proj_epic_names.difference(retro_epic_names)
            new_cards = self.export_jira_epic_chain_to_cards(new_names)
            known_names = proj_epic_names.intersection(retro_epic_names)
            known_cards = self.export_jira_epic_chain_to_cards(known_names)
            self._cards_by_id.update(new_cards)
            self._projective_cards.update(new_cards.keys())
            self._projective_cards.update(known_cards.keys())

        self.resolve_inheritance(proj_tasks.union(retro_tasks))

        for name in issue_names_requiring_events:
            extractor = jira.EventExtractor(self._all_issues_by_name[name], spec.cutoff_date)
            new_events = extractor.get_task_events(self)
            self._all_events.extend(new_events)

    def merge_jira_item_without_children(self, item):

        result = super().merge_jira_item_without_children(item)

        result.point_cost = self._get_points_of(item)
        return result

    def update_points_of(self, our_task, points):
        jira_task = self.find_card(our_task.name)
        remote_points = self._get_points_of(jira_task)
        if remote_points == points:
            return jira_task
        if remote_points != our_task.point_cost:
            msg = (
                f"Trying to update issue {our_task.name} "
                f"with cached value {our_task.point_cost}, "
                f"while it has {remote_points}."
            )
            raise ValueError(msg)
        self._set_points_of(jira_task, points)
        jira_task.find(jira_task.key)
        return self.merge_jira_item_without_children(jira_task)

    @classmethod
    def _accepted(cls, jira_string, item):
        if jira_string == "Closed":
            if "Accepted" in item.get_field("labels"):
                return "Done"
            elif item.get_field("resolution") == "Done":
                return "Done"
        return jira_string

    @classmethod
    def _status_to_state(cls, item, jira_string):
        item_name = item.key

        if item_name.startswith(PROJECT_NAME):
            jira_string = cls._accepted(jira_string, item)
            return super()._status_to_state(item, jira_string)
        elif item_name.startswith("RHELPLAN"):
            jira_string = cls._accepted(jira_string, item)
            return redhat_compliance.RHELPLAN_STATUS_TO_STATE.get(jira_string, "irrelevant")
        elif item_name.startswith("RHEL"):
            jira_string = cls._accepted(jira_string, item)
            return redhat_compliance.RHEL_STATUS_TO_STATE.get(jira_string, "irrelevant")
        else:
            jira_string = cls._accepted(jira_string, item)
            return redhat_compliance.JIRA_STATUS_TO_STATE.get(jira_string, "irrelevant")


def do_stuff(spec):
    importer = Importer(spec)
    importer.import_data(spec)
    retro_io = web_utils.get_retro_loader()[1]
    proj_io = web_utils.get_proj_loader()[1]
    importer.save(retro_io, proj_io, simpledata.EventManager)
    return importer.get_collected_stats()


class Workloads:
    def __init__(self,
                 cards: typing.Iterable[data.BaseCard],
                 model: data.EstiModel,
                 * args, ** kwargs):
        cards = [t for t in cards if t.tier == 0]
        super().__init__(* args, model=model, cards=cards, ** kwargs)

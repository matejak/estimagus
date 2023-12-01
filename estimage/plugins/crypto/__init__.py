import re
import datetime
import collections
import dateutil.relativedelta
import typing

import flask

from ... import simpledata, data, persistence
from .. import jira
from ...webapp import web_utils
from .forms import CryptoForm


# TEMPLATE_EXPORTS = dict(base="rhc-base.html")


PROJECT_NAME = "CRYPTO"
jira.JIRA_STATUS_TO_STATE["Closed"] = jira.target.State.done


class InputSpec(jira.InputSpec):
    @classmethod
    def from_form_and_app(cls, form, app) -> "InputSpec":
        ret = cls()
        ret.server_url = "https://issues.redhat.com"
        ret.token = form.token.data
        ret.cutoff_date = app.config["RETROSPECTIVE_PERIOD"][0]
        query = f"project = {PROJECT_NAME} AND type = Epic AND Sprint in openSprints()"
        query = f"project = Crypto AND type = Task AND sprint in openSprints()"
        ret.retrospective_query = query
        ret.projective_query = query
        ret.item_class = app.config["classes"]["BaseTarget"]
        return ret


def get_tasks(jira, query, all_items_by_name, parents_child_keymap):
    tasks = jira.search_issues(
        query, expand="changelog,renderedFields", maxResults=0)

    new_task_names = set()
    for task in tasks:
        new_task_names.add(task.key)
        if task.key in all_items_by_name:
            continue
        all_items_by_name[task.key] = task
        identify_epic_subtasks(jira, task, all_items_by_name, parents_child_keymap)
        jira.recursively_identify_task_subtasks(jira, task, all_items_by_name, parents_child_keymap):
    return new_task_names


class Importer(jira.Importer):
    STORY_POINTS = "customfield_12310243"
    EPIC_LINK = "customfield_12311140"

    def _get_points_of(self, item):
        return float(item.get_field(self.STORY_POINTS) or 0)

    # def _set_points_of(self, item, points):
        # item.update({self.STORY_POINTS: round(points, 2)})

    def _get_owner_epic_of(self, assignee, committed):
        name = f"{PROJECT_NAME}-{task.assignee}"
        if committed:
            name += "-C"

        epic = self._all_issues_by_name.get(name)

        if not epic:
            epic = self.item_class(name)
            epic.assignee = assignee
            epic.title = f"Issues of {assignee}"
            if committed:
                epic.title = "Committed " + epic.title
        return epic

    def put_tasks_under_artificial_epics(tasks):
        epic_names = set()
        for task in tasks:
            epic = self._get_owner_epic_of(task.assignee, "Committed" in task.tags)
            epic.add_element(task)
            epic_names.add(epic.name)


    def import_data(self, spec):
        retro_tasks = set()
        if spec.retrospective_query:
            self.report("Gathering retro stuff")
            retro_tasks = get_tasks(
                self.jira, spec.retrospective_query, self._all_issues_by_name,
                self._parents_child_keymap)
            self.put_tasks_under_artificial_epics(retro_tasks)
            new_targets = self.export_jira_epic_chain_to_targets(retro_epic_names)
            self._retro_targets.update(new_targets.keys())
            issue_names_requiring_events.update(new_targets.keys())
            self._targets_by_id.update(new_targets)

        proj_tasks = set()
        if spec.projective_query:
            self.report("Gathering proj stuff")
            proj_tasks = get_epics_and_their_tasks_by_id(
                self.jira, spec.projective_query, self._all_issues_by_name,
                self._parents_child_keymap)
            new_names = proj_epic_names.difference(retro_epic_names)
            new_targets = self.export_jira_epic_chain_to_targets(new_names)
            known_names = proj_epic_names.intersection(retro_epic_names)
            known_targets = self.export_jira_epic_chain_to_targets(known_names)
            self._targets_by_id.update(new_targets)
            self._projective_targets.update(new_targets.keys())
            self._projective_targets.update(known_targets.keys())

        self.resolve_inheritance(proj_epic_names.union(retro_epic_names))

        for name in issue_names_requiring_events:
            new_events = get_task_events(self._all_issues_by_name[name], spec.cutoff_date)
            self._all_events.extend(new_events)


    def merge_jira_item_without_children(self, item):

        result = super().merge_jira_item_without_children(item)

        result.point_cost = self._get_points_of(item)
        return result

    def update_points_of(self, our_task, points):
        jira_task = self.find_target(our_task.name)
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


def do_stuff(spec):
    importer = Importer(spec)
    importer.import_data(spec)
    retro_io = web_utils.get_retro_loader()[1]
    proj_io = web_utils.get_proj_loader()[1]
    importer.save(retro_io, proj_io, simpledata.EventManager)

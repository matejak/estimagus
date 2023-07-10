import re
import datetime
import collections
import dateutil.relativedelta
import typing

import flask

from ... import simpledata, data, persistence
from ...entities import target
from .. import jira
from ...webapp import web_utils
from .forms import AuthoritativeForm


EXPORTS = dict(
    BaseTarget="BaseTarget",
    AuthoritativeForm="AuthoritativeForm",
    Workloads="Workloads",
)
# TEMPLATE_EXPORTS = dict(base="rhc-base.html")


QUARTER_TO_MONTH_NUMBER = None
PROJECT_NAME = "OPENSCAP"
MONTHS_IN_QUARTER = 3


TEMPLATE_OVERRIDES = {
    "tree_view_retrospective.html": "rhcompliance-retrotree.html",
}


RHELPLAN_STATUS_TO_STATE = {
    "New": target.State.todo,
    "Verified": target.State.done,
    "Closed": target.State.done,
    "In Progress": target.State.in_progress,
    "ASSIGNED": target.State.in_progress,
    "ON_DEV": target.State.in_progress,
    "POST": target.State.in_progress,
    "MODIFIED": target.State.in_progress,
    "Review": target.State.review,
    "ON_QA": target.State.review,
    "To Do": target.State.todo,
}


class InputSpec(jira.InputSpec):
    @classmethod
    def from_form_and_app(cls, input_form, app) -> "InputSpec":
        ret = cls()
        ret.server_url = "https://issues.redhat.com"
        ret.token = input_form.token.data
        epoch = input_form.quarter.data
        planning_epoch = epoch
        if input_form.project_next.data:
            planning_epoch = next_epoch_of(planning_epoch)
        ret.cutoff_date = epoch_start_to_datetime(epoch)
        query_lead = f"project = {PROJECT_NAME} AND type = Epic AND"
        retro_narrowing = f"sprint = {epoch} AND Commitment in (Committed, Planned)"
        proj_narrowing = f"sprint = {planning_epoch}"
        ret.retrospective_query = " ".join((query_lead, retro_narrowing))
        ret.projective_query = " ".join((query_lead, proj_narrowing))
        ret.item_class = app.config["classes"]["BaseTarget"]
        return ret


def epoch_start_to_datetime(epoch: str):
    epoch_groups = re.search(r"CY(\d\d)Q(\d)", epoch)
    year_number = int(epoch_groups.group(1))
    quarter_number = int(epoch_groups.group(2))
    return datetime.datetime(2000 + year_number, 1 + (quarter_number - 1) * MONTHS_IN_QUARTER, 1)


def epoch_end_to_datetime(epoch: str):
    epoch_start = epoch_start_to_datetime(epoch)
    epoch_end = epoch_start + dateutil.relativedelta.relativedelta(months=MONTHS_IN_QUARTER)
    epoch_end -= datetime.timedelta(days=1)
    return epoch_end


def next_epoch_of(epoch: str) -> str:
    next_epoch_start = epoch_end_to_datetime(epoch) + datetime.timedelta(days=1)
    quarter = (next_epoch_start.month - 1) // MONTHS_IN_QUARTER + 1
    return f"CY{next_epoch_start.year - 2000}Q{quarter}"


def datetime_to_epoch(date: datetime.datetime) -> str:
    year = date.year % 100
    quarter = (date.month - 1) // MONTHS_IN_QUARTER + 1
    return f"CY{year}Q{quarter}"


def days_to_next_epoch(date: datetime.datetime) -> int:
    current_epoch = datetime_to_epoch(date)
    end = epoch_end_to_datetime(current_epoch)
    return (end - date).days


def extract_status_updates(all_events):
    last_updates = dict()
    for e in all_events:
        if not e.quantity == "status_summary":
            continue
        put_status_update_time_into_results(last_updates, e)
    return last_updates


def put_status_update_time_into_results(results, update_event):
    task_name = update_event.task_name
    if task_name in results:
        results[task_name] = max(results[task_name], update_event.time)
    else:
        results[task_name] = update_event.time


def apply_status_updates(issues_by_name, all_events):
    last_updates_by_id = extract_status_updates(all_events)
    for issue_name, date in last_updates_by_id.items():
        issues_by_name[issue_name].status_summary_time = date


def apply_some_events_into_issues(issues_by_name, all_events):
    apply_status_updates(issues_by_name, all_events)


class Importer(jira.Importer):
    STORY_POINTS = "customfield_12310243"
    EPIC_LINK = "customfield_12311140"
    CONTRIBUTORS = "customfield_12315950"
    COMMITMENT = "customfield_12317404"
    STATUS_SUMMARY = "customfield_12317299"
    WORK_START = "customfield_12313941"
    WORK_END = "customfield_12313942"

    def _get_points_of(self, item):
        return float(item.get_field(self.STORY_POINTS) or 0)

    def _set_points_of(self, item, points):
        item.update({self.STORY_POINTS: round(points, 2)})

    def merge_jira_item_without_children(self, item):

        result = super().merge_jira_item_without_children(item)

        result.point_cost = self._get_points_of(item)
        result.status_summary = self._get_contents_of_rendered_field(item, self.STATUS_SUMMARY)
        result.loading_plugin = "jira-rhcompliance"
        self._record_collaborators(result, item)
        self._record_commitment_as_tier_and_tags(result, item)
        self._record_work_span(result, item)

        return result

    def _record_collaborators(self, result, item):
        result.collaborators = []
        try:
            result.collaborators += [
                jira.name_from_field(c) for c in item.get_field(self.CONTRIBUTORS) or []]
        except AttributeError:
            pass

    def _record_commitment_as_tier_and_tags(self, result, item):
        result.tier = 0
        try:
            if commitment_item := item.get_field(self.COMMITMENT):
                result.tags.add(f"commitment:{commitment_item.value.lower()}")
                if commitment_item.value.lower() == "planned":
                    result.tier = 1
        except AttributeError:
            pass

    def _record_work_span(self, result, item):
        work_span = [None, None]
        if work_end := item.get_field(self.WORK_END):
            work_span[-1] = jira.jira_date_to_datetime(work_end)

        if work_start := item.get_field(self.WORK_START):
            work_span[0] = jira.jira_date_to_datetime(work_start)

        if work_span[0] or work_span[-1]:
            result.work_span = tuple(work_span)

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

    def save(self, retro_target_io_class, proj_target_io_class, event_manager_class):
        apply_some_events_into_issues(self._targets_by_id, self._all_events)
        return super().save(retro_target_io_class, proj_target_io_class, event_manager_class)

    @classmethod
    def _status_to_state(cls, item, jira_string):
        item_name = item.key

        if item_name.startswith("OPENSCAP"):
            return super()._status_to_state(item, jira_string)
        elif item_name.startswith("RHELPLAN"):
            return RHELPLAN_STATUS_TO_STATE.get(jira_string, target.State.unknown)
        else:
            return RHELPLAN_STATUS_TO_STATE.get(jira_string, target.State.unknown)


def _get_simple_spec(token):
    Spec = collections.namedtuple("Spec", ["server_url", "token", "item_class"])
    spec = Spec(
        server_url="https://issues.redhat.com",
        token=token,
        item_class=flask.current_app.config["classes"]["BaseTarget"])
    return spec


def refresh_targets(names, mode, token):
    spec = _get_simple_spec(token)
    if mode == "projective":
        io_cls = web_utils.get_proj_loader()[1]
    else:
        io_cls = web_utils.get_retro_loader()[1]
    real_targets = [data.BaseTarget.load_metadata(name, io_cls) for name in names]
    importer = Importer(spec)
    importer.refresh_targets(real_targets, io_cls)


def write_some_points(form):
    return write_points_to_task(form.task_name.data, form.token.data, float(form.point_cost.data))


def write_points_to_task(name, token, points):
    spec = _get_simple_spec(token)
    io_cls = web_utils.get_proj_loader()[1]
    importer = Importer(spec)
    our_target = data.BaseTarget.load_metadata(name, io_cls)
    updated_target = importer.update_points_of(our_target, points)
    updated_target.save_metadata(io_cls)


def do_stuff(spec):
    retro_loader = web_utils.get_retro_loader()[1]
    proj_loader = web_utils.get_proj_loader()[1]
    importer = Importer(spec)
    importer.import_data(spec)
    importer.save(retro_loader, proj_loader, simpledata.EventManager)


class BaseTarget:
    status_summary: str
    status_summary_time: datetime.datetime

    def __init__(self, * args, **kwargs):
        super().__init__(* args, ** kwargs)

        self.status_summary = ""
        self.status_summary_time = None

    def pass_data_to_saver(self, saver):
        super().pass_data_to_saver(saver)
        saver.save_status_update(self)

    def load_data_by_loader(self, loader):
        super().load_data_by_loader(loader)
        loader.load_status_update(self)


@persistence.loader_of(BaseTarget, "ini")
class IniTargetStateLoader:
    def load_status_update(self, t):
        t.status_summary = self._get_our(t, "status_summary")
        time_str = self._get_our(t, "status_summary_time")
        if time_str:
            t.status_summary_time = datetime.datetime.fromisoformat(time_str)


@persistence.saver_of(BaseTarget, "ini")
class IniTargetStateSaver:
    def save_status_update(self, t):
        self._store_our(t, "status_summary")
        if t.status_summary_time:
            self._store_our(t, "status_summary_time", t.status_summary_time.isoformat())


class Workloads:
    def __init__(self,
                 targets: typing.Iterable[data.BaseTarget],
                 model: data.EstiModel,
                 * args, ** kwargs):
        targets = [t for t in targets if t.tier == 0]
        super().__init__(* args, model=model, targets=targets, ** kwargs)

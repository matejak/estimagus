import re
import datetime
import dataclasses
import collections
import dateutil.relativedelta

import flask

from ... import simpledata, data
from .. import jira

bp = flask.Blueprint("rhcompliance", __name__, template_folder="templates")

from . import routes


EXPORTS = dict(
    PertPlotter="PertPlotter",
    BaseTarget="BaseTarget",
)
TEMPLATE_EXPORTS = dict(base="rhc-base.html")


QUARTER_TO_MONTH_NUMBER = None
PROJECT_NAME = "OPENSCAP"


TEMPLATE_OVERRIDES = {
    "tree_view_retrospective.html": "rhcompliance-retrotree.html",
}


def register_own_blueprint(app):
    app.register_blueprint(bp, url_prefix="/plugins")


class PertPlotter:
    PERT_COLOR = "red"
    EXPECTED_COLOR = "grey"


class InputSpec(jira.InputSpec):
    @classmethod
    def from_form_and_app(cls, input_form, app) -> "InputSpec":
        ret = cls()
        ret.server_url = "https://issues.redhat.com"
        ret.token = input_form.token.data
        epoch = input_form.quarter.data
        ret.cutoff_date = epoch_start_to_datetime(epoch)
        query_lead = f"project = {PROJECT_NAME} AND type = Epic AND"
        retro_narrowing = f"sprint = {epoch} AND Commitment in (Committed, Planned)"
        proj_narrowing = f"(sprint = {epoch} OR fixVersion = {epoch})"
        ret.retrospective_query = " ".join((query_lead, retro_narrowing))
        ret.projective_query = " ".join((query_lead, proj_narrowing))
        ret.item_class = app.config["classes"]["BaseTarget"]
        return ret


def epoch_start_to_datetime(epoch: str):
    epoch_groups = re.search(r"CY(\d\d)Q(\d)", epoch)
    year_number = int(epoch_groups.group(1))
    quarter_number = int(epoch_groups.group(2))
    return datetime.datetime(2000 + year_number, 1 + (quarter_number - 1) * 3, 1)


def epoch_end_to_datetime(epoch: str):
    epoch_start = epoch_start_to_datetime(epoch)
    epoch_end = epoch_start + dateutil.relativedelta.relativedelta(months=3)
    epoch_end -= datetime.timedelta(days=1)
    return epoch_end


def next_epoch_of(epoch: str) -> str:
    next_epoch_start = epoch_end_to_datetime(epoch) + datetime.timedelta(days=1)
    quarter = (next_epoch_start.month - 1) // 3 + 1
    return f"CY{next_epoch_start.year - 2000}Q{quarter}"


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

    def merge_jira_item_without_children(self, item):

        result = super().merge_jira_item_without_children(item)

        result.point_cost = float(item.get_field(self.STORY_POINTS) or 0)
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

    def save(self, retro_target_io_class, proj_target_io_class, event_manager_class):
        apply_some_events_into_issues(self._targets_by_id, self._all_events)
        return super().save(retro_target_io_class, proj_target_io_class, event_manager_class)


def refresh_targets(names, mode, token):
    Spec = collections.namedtuple("Spec", ["server_url", "token"])
    spec = Spec(server_url="https://issues.redhat.com", token=token)
    if mode == "projective":
        io_cls = simpledata.ProjTargetIO
    else:
        io_cls = simpledata.RetroTargetIO
    real_targets = [data.BaseTarget.load_metadata(name, io_cls) for name in names]
    importer = Importer(spec)
    importer.refresh_targets(real_targets, io_cls)


def do_stuff(spec):
    importer = Importer(spec)
    importer.import_data(spec)
    importer.save(simpledata.RetroTargetIO, simpledata.ProjTargetIO, simpledata.EventManager)


@dataclasses.dataclass(init=False)
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

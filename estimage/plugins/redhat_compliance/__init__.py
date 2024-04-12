import re
import datetime
import collections
import dateutil.relativedelta
import typing

from ... import simpledata, data, persistence
from ...entities import status
from ...webapp import web_utils
from ...visualize.burndown import StatusStyle
from .. import jira
from .forms import AuthoritativeForm, ProblemForm


EXPORTS = dict(
    AuthoritativeForm="AuthoritativeForm",
    ProblemForm="ProblemForm",
    BaseCard="BaseCard",
    MPLPointPlot="MPLPointPlot",
    Statuses="Statuses",
    CardSynchronizer="CardSynchronizer",
    Workloads="Workloads",
)


QUARTER_TO_MONTH_NUMBER = None
PROJECT_NAME = "OPENSCAP"
MONTHS_IN_QUARTER = 3


TEMPLATE_OVERRIDES = {
    "tree_view_retrospective.html": "rhcompliance-retrotree.html",
}


RHEL_STATUS_TO_STATE = {
    "New": "todo",
    "Planning": "todo",
    "Verified": "done",
    "Closed": "done",
    "Done": "done", # not really a state, but used
    "In Progress": "rhel-in_progress",
    "Integration": "rhel-integration",
    "Release Pending": "done",
    "To Do": "todo",
}


RHELPLAN_STATUS_TO_STATE = {
    "New": "todo",
    "Verified": "done",
    "Closed": "done",
    "Abandoned": "irrelevant",
    "ASSIGNED": "rhel-in_progress",
    "ON_DEV": "rhel-in_progress",
    "POST": "rhel-in_progress",
    "MODIFIED": "rhel-integration",
    "ON_QA": "rhel-integration",
}


JIRA_STATUS_TO_STATE = {
    "Backlog": "todo",
    "Refinement": "todo",
    "New": "todo",
    "Done": "done",
    "Abandoned": "irrelevant",
    "Closed": "irrelevant",
    "In Progress": "in_progress",
    "Needs Peer Review": "review",
    "To Do": "todo",
}

class CardSynchronizer(jira.CardSynchronizer):
    @classmethod
    def from_form(cls, form):
        kwargs = dict()
        kwargs["server_url"] = "https://issues.redhat.com"
        kwargs["token"] = form.token.data
        kwargs["importer_cls"] = Importer
        return cls(** kwargs)


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
        ret.item_class = app.get_final_class("BaseCard")
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
    STATUS_SUMMARY_OLD = "customfield_12317299"
    STATUS_SUMMARY_NEW = "customfield_12320841"
    WORK_START = "customfield_12313941"
    WORK_END = "customfield_12313942"

    def _get_points_of(self, item):
        return float(item.get_field(self.STORY_POINTS) or 0)

    def _set_points_of(self, item, points):
        item.update({self.STORY_POINTS: round(points, 2)})

    def _get_status_summary(self, item):
        ret = self._get_contents_of_rendered_field(item, self.STATUS_SUMMARY_OLD)
        if ret:
            return ret
        ret = self._get_contents_of_rendered_field(item, self.STATUS_SUMMARY_NEW)
        return ret

    def merge_jira_item_without_children(self, item):

        result = super().merge_jira_item_without_children(item)

        result.point_cost = self._get_points_of(item)
        result.status_summary = self._get_status_summary(item)
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

    def get_points_of(self, our_task):
        jira_task = self.find_card(our_task.name)
        remote_points = self._get_points_of(jira_task)
        return remote_points

    def update_points_of(self, our_task, points):
        jira_task = self.find_card(our_task.name)
        self._set_points_of(jira_task, points)
        our_task.point_cost = points
        return our_task

    def save(self, retro_card_io_class, proj_card_io_class, event_manager_class):
        apply_some_events_into_issues(self._cards_by_id, self._all_events)
        return super().save(retro_card_io_class, proj_card_io_class, event_manager_class)

    @classmethod
    def _status_to_state(cls, item, jira_string):
        item_name = item.key

        if item_name.startswith("OPENSCAP"):
            return super()._status_to_state(item, jira_string)
        elif item_name.startswith("RHELPLAN"):
            return RHELPLAN_STATUS_TO_STATE.get(jira_string, "irrelevant")
        elif item_name.startswith("RHEL"):
            return RHEL_STATUS_TO_STATE.get(jira_string, "irrelevant")
        else:
            return JIRA_STATUS_TO_STATE.get(jira_string, "irrelevant")


def _get_simple_spec(token, card_cls):
    Spec = collections.namedtuple("Spec", ["server_url", "token", "item_class"])
    spec = Spec(
        server_url="https://issues.redhat.com",
        token=token,
        item_class=card_cls)
    return spec


def refresh_cards(names, io_cls, card_cls, token):
    spec = _get_simple_spec(token, card_cls)
    real_cards = [data.BaseCard.load_metadata(name, io_cls) for name in names]
    importer = Importer(spec)
    importer.refresh_cards(real_cards, io_cls)


def do_stuff(spec):
    importer = Importer(spec)
    importer.import_data(spec)
    retro_io = web_utils.get_retro_loader()[1]
    proj_io = web_utils.get_proj_loader()[1]
    importer.save(retro_io, proj_io, simpledata.EventManager)
    return importer.get_collected_stats()


class Statuses:
    def __init__(self):
        super().__init__()
        self.statuses.extend([
            status.Status.create("review", started=True, wip=False, done=False),
            status.Status.create("rhel-in_progress", started=True, wip=True, done=False),
            status.Status.create("rhel-integration", started=True, wip=False, done=False),
        ])


class MPLPointPlot:
    def get_styles(self):
        ret = super().get_styles()
        ret["review"] = StatusStyle(color=(0.1, 0.2, 0.7, 0.6), label="Needs Review", weight=80)
        ret["rhel-in_progress"] = StatusStyle(color=(0.1, 0.2, 0.5, 0.4), label="BZ In Progress", weight=60)
        ret["rhel-integration"] = StatusStyle(color=(0.2, 0.4, 0.7, 0.6), label="BZ Integration", weight=61)
        return ret


class BaseCard:
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


@persistence.loader_of(BaseCard, "ini")
class IniCardStateLoader:
    def load_status_update(self, t):
        t.status_summary = self._get_our(t, "status_summary")
        time_str = self._get_our(t, "status_summary_time")
        if time_str:
            t.status_summary_time = datetime.datetime.fromisoformat(time_str)


@persistence.saver_of(BaseCard, "ini")
class IniCardStateSaver:
    def save_status_update(self, t):
        self._store_our(t, "status_summary")
        if t.status_summary_time:
            self._store_our(t, "status_summary_time", t.status_summary_time.isoformat())


class Workloads:
    def __init__(self,
                 cards: typing.Iterable[data.BaseCard],
                 model: data.EstiModel,
                 * args, ** kwargs):
        cards = [t for t in cards if t.tier == 0]
        super().__init__(* args, model=model, cards=cards, ** kwargs)

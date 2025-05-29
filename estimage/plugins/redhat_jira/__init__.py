import datetime

from ... import data
from ...visualize.burndown import StatusStyle
from ... import persistence
from .. import jira


RHEL_STATUS_TO_STATE = {
    "New": "todo",
    "Planning": "todo",
    "Verified": "done",
    "Done": "done", # not really a state, but used
    "In Progress": "rhel-in_progress",
    "Integration": "rhel-integration",
    "Release Pending": "done",
    "To Do": "todo",
}


RHELPLAN_STATUS_TO_STATE = {
    "New": "todo",
    "Verified": "done",
    "Abandoned": "irrelevant",
    "ASSIGNED": "rhel-in_progress",
    "ON_DEV": "rhel-in_progress",
    "POST": "rhel-in_progress",
    "MODIFIED": "rhel-integration",
    "ON_QA": "rhel-integration",
}


OJA_ETC_STATUS_TO_STATE = {
    "New": "todo",
    "Refinement": "todo",
    "Backlog": "todo",
    "To Do": "todo",
    "Stakeholder Review": "todo",
    "In Progress": "in_progress",
    "Closed": "irrelevant",
    "Review": "review",
    "Stakeholder Acceptance": "review",
    "Resolved": "done",
    "Done": "done", # not really a state, but used
}


EXPORTS = dict(
    MPLPointPlot="MPLPointPlot",
    Statuses="Statuses",
)


class EventExtractor(jira.EventExtractor):
    def _field_to_event(self, date, field_name, former_value, new_value):
        evt = super()._field_to_event(date, field_name, former_value, new_value)
        if field_name == "Story Points":
            evt = data.Event(self.task.key, "points", date)
            evt.value_before = float(former_value or 0)
            evt.value_after = float(new_value or 0)
            evt.msg = f"Points changed from {former_value} to {new_value}"
        elif field_name in ("Latest Status Summary", "Status Summary"):
            evt = data.Event(self.task.key, "status_summary", date)
            evt.value_before = former_value
            evt.value_after = new_value
            evt.msg = f"Event summary changed to {new_value}"
        return evt


class InputSpec(jira.InputSpec):
    @classmethod
    def from_form_and_app(cls, input_form, app) -> "InputSpec":
        ret = cls()
        ret.token = input_form.token.data
        ret.server_url = "https://issues.redhat.com"
        ret.item_class = app.get_final_class("BaseCard")
        ret.set_cutoff_date(input_form)
        ret.set_queries(input_form)
        return ret


class SyncImporter(jira.importer.BareboneImporter):
    STORY_POINTS = "customfield_12310243"
    def __init__(self, * args, ** kwargs):
        super().__init__(* args, ** kwargs)
        self.subsequent_request_time_off = 2

    def _get_points_of(self, item):
        ret = self._get_contents_of_field(item, self.STORY_POINTS, 0)
        return ret

    def _set_points_of(self, item, points):
        item.update({self.STORY_POINTS: round(points, 2)})

    def get_points_of(self, our_task):
        jira_task = self.find_card(our_task.name)
        remote_points = self._get_points_of(jira_task)
        return remote_points

    def update_points_of(self, our_task, points):
        jira_task = self.find_card(our_task.name)
        self._set_points_of(jira_task, points)
        our_task.point_cost = points
        return our_task


class Importer(jira.Importer, SyncImporter):
    EPIC_LINK = "customfield_12311140"
    CONTRIBUTORS = "customfield_12315950"
    WORK_START = "customfield_12313941"
    WORK_END = "customfield_12313942"

    @classmethod
    def _status_to_state(cls, item, jira_string):
        if cls._item_is_closed_done(item, jira_string):
            return "done"

        item_name = item.key

        if item_name.startswith("RHELPLAN-"):
            return RHELPLAN_STATUS_TO_STATE.get(jira_string, "irrelevant")
        elif item_name.startswith("RHEL-"):
            return RHEL_STATUS_TO_STATE.get(jira_string, "irrelevant")
        else:
            return OJA_ETC_STATUS_TO_STATE.get(jira_string, "irrelevant")

    def import_data(self, extractor_cls=EventExtractor):
        return super().import_data(extractor_cls)

    def merge_jira_item_without_children(self, item):

        result = super().merge_jira_item_without_children(item)

        result.point_cost = self._get_points_of(item)
        result.loading_plugin = "jira-redhat"
        self._record_collaborators(result, item)
        self._record_work_span(result, item)
        return result

    def _record_collaborators(self, result, item):
        result.collaborators = []
        try:
            result.collaborators += [
                jira.get_name_from_person_field(c) for c in item.get_field(self.CONTRIBUTORS) or []]
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


class ImporterWithStatus(Importer):
    STATUS_SUMMARY_OLD = "customfield_12317299"
    STATUS_SUMMARY_NEW = "customfield_12320841"

    def save(self, ios_by_target):
        apply_some_events_into_issues(self._cards_by_id, self._all_events)
        return super().save(ios_by_target)

    def _get_status_summary(self, item):
        ret = self._get_contents_of_rendered_field(item, self.STATUS_SUMMARY_OLD)
        if ret:
            return ret
        ret = self._get_contents_of_rendered_field(item, self.STATUS_SUMMARY_NEW)
        return ret

    def merge_jira_item_without_children(self, item):

        result = super().merge_jira_item_without_children(item)

        result.status_summary = self._get_status_summary(item)
        return result


class BaseCardWithStatus:
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


@persistence.loader_of(BaseCardWithStatus, "ini")
class IniCardStateLoader:
    def load_status_update(self, t):
        t.status_summary = self._get_our(t, "status_summary")
        time_str = self._get_our(t, "status_summary_time")
        if time_str:
            t.status_summary_time = datetime.datetime.fromisoformat(time_str)


@persistence.saver_of(BaseCardWithStatus, "ini")
class IniCardStateSaver:
    def save_status_update(self, t):
        self._store_our(t, "status_summary")
        if t.status_summary_time:
            self._store_our(t, "status_summary_time", t.status_summary_time.isoformat())


class CardSynchronizer(jira.CardSynchronizer):
    @classmethod
    def from_form(cls, form):
        kwargs = dict()
        kwargs["server_url"] = "https://issues.redhat.com"
        kwargs["token"] = form.token.data
        kwargs["importer_cls"] = SyncImporter
        return cls(** kwargs)


class Statuses:
    def __init__(self):
        super().__init__()
        self.statuses.extend([
            data.Status.create("review", started=True, wip=False, done=False),
            data.Status.create("rhel-in_progress", started=True, wip=True, done=False),
            data.Status.create("rhel-integration", started=True, wip=False, done=False),
        ])


class MPLPointPlot:
    def get_styles(self):
        ret = super().get_styles()
        ret["review"] = StatusStyle(color=(0.1, 0.2, 0.7, 0.6), label="Needs Review", weight=80)
        ret["rhel-in_progress"] = StatusStyle(color=(0.1, 0.2, 0.5, 0.4), label="BZ In Progress", weight=60)
        ret["rhel-integration"] = StatusStyle(color=(0.2, 0.4, 0.7, 0.6), label="BZ Integration", weight=61)
        return ret


def do_stuff(spec, ios_by_target):
    importer = Importer(spec)
    importer.import_data()
    importer.save(ios_by_target)
    return importer.get_collected_stats()

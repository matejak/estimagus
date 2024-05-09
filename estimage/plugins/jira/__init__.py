import dataclasses
import datetime
import collections
import time
import typing

from jira import JIRA, exceptions

from ...entities import card
from ... import simpledata
from ...entities import event as evts
from ... import simpledata


JIRA_STATUS_TO_STATE = {
    "New": "todo",
    "Done": "done",
    "Closed": "irrelevant",
    "In Progress": "in_progress",
    "To Do": "todo",
}


JIRA_PRIORITY_TO_VALUE = {
    "Blocker": 90,
    "Critical": 80,
    "Major": 70,
    "Normal": 50,
    "Minor": 30,
}


Collected = collections.namedtuple("Collected", ("Retrospective", "Projective", "Events"))


class CardSynchronizer:
    def __init__(self, server_url, token, importer_cls, ** kwargs):
        self.server_url = server_url
        self.token = token
        self.importer_cls = importer_cls
        super().__init__(** kwargs)

    @classmethod
    def from_form(cls, form):
        raise NotImplementedError

    def _get_spec(self):
        ret = InputSpec()
        ret.server_url = self.server_url
        ret.token = self.token
        ret.item_class = card.BaseCard
        return ret

    def get_tracker_points_of(self, c: card.BaseCard) -> float:
        spec = self._get_spec()
        spec.item_class = c.__class__
        importer = self.importer_cls(spec)
        return importer.get_points_of(c)

    def insert_points_into_tracker(self, c: card.BaseCard, target_points: float):
        spec = self._get_spec()
        spec.item_class = c.__class__
        importer = self.importer_cls(spec)
        importer.update_points_of(c, target_points)


@dataclasses.dataclass(init=False)
class InputSpec:
    token: str
    server_url: str
    retrospective_query: str
    projective_query: str
    cutoff_date: datetime.date
    item_class: typing.Type

    @classmethod
    def from_form_and_app(cls, input_form, app) -> "InputSpec":
        ret = cls()
        ret.token = input_form.token.data
        ret.server_url = input_form.server.data
        ret.item_class = app.get_final_class("BaseCard")
        self.set_cutoff_date(input_form)
        self.set_queries(input_form)
        return ret

    def set_cutoff_date(self, input_form):
        self.cutoff_date = input_form.cutoffDate.data

    def set_queries(self, input_form):
        self.retrospective_query = input_form.retroQuery.data
        self.projective_query = input_form.projQuery.data


def jira_retry(func, * args, ** kwargs):
    return jira_retry_n(5, 5, func, * args, ** kwargs)


def jira_retry_n(retries, longest_pause, func, * args, ** kwargs):
    try:
        result = func(* args, ** kwargs)
    except exceptions.JIRAError:
        if retries <= 0:
            raise
        time.sleep(longest_pause / retries)
        print(f"Failed {func.__name__}, retrying {retries} more times")
        result = jira_retry_n(retries - 1, longest_pause, func, * args, ** kwargs)
    return result


def get_name_from_person_field(field_contents):
    return field_contents.emailAddress.split("@", 1)[0]


def save_exported_jira_tasks(all_cards_by_id, id_selection, card_io_class):
    to_save = [all_cards_by_id[tid] for tid in id_selection]
    card_io_class.bulk_save_metadata(to_save)


def jira_datetime_to_datetime(jira_datetime):
    date_str = jira_datetime.split("+")[0]
    return datetime.datetime.fromisoformat(date_str)


def jira_date_to_datetime(jira_date):
    return datetime.datetime.strptime(jira_date, "%Y-%m-%d")


class EventExtractor:
    def __init__(self, task, cutoff_date=None):
        self.task = task
        self.cutoff_datetime = None
        if cutoff_date:
            self.cutoff_datetime = datetime.datetime(
                cutoff_date.year, cutoff_date.month, cutoff_date.day)
        self.importer = Importer

    def get_histories(self):
        return [
            history for history in self.task.changelog.histories
            if jira_datetime_to_datetime(history.created) >= self.cutoff_datetime
        ]

    def _field_to_event(self, date, field_name, former_value, new_value):
        evt = None
        if field_name == "status":
            evt = evts.Event(self.task.key, "state", date)
            evt.value_before = self.importer.status_to_state(self.task, former_value)
            evt.value_after = self.importer.status_to_state(self.task, new_value)
            evt.msg = f"Status changed from '{former_value}' to '{new_value}'"
        return evt

    def import_event(self, event, date):

        field_name = event.field
        former_value = event.fromString
        new_value = event.toString

        evt = self._field_to_event(date, field_name, former_value, new_value)
        return evt

    def append_event_entry(self, events, event, date):
        event = self.import_event(event, date)
        if event is not None:
            events.append(event)
        return events

    def get_events_from_task_histories(self, histories):
        events = []
        for history in histories:
            date = jira_datetime_to_datetime(history.created)

            for event in history.items:
                self.append_event_entry(events, event, date)
        return events

    def get_task_events(self, importer=None):
        if importer:
            self.importer = importer
        recent_enough_histories = self.get_histories()
        events = self.get_events_from_task_histories(recent_enough_histories)
        return events


class JiraWithRetry(JIRA):
    def search_issues(self, * args, ** kwargs):
        return jira_retry(super().search_issues, * args, ** kwargs)

    def issue(self, * args, ** kwargs):
        return jira_retry(super().issue, * args, ** kwargs)


class Importer:
    def __init__(self, spec):
        self._cards_by_id = dict()
        self._all_issues_by_name = dict()
        self._parent_name_to_children_names = dict()

        self._retro_cards = set()
        self._projective_cards = set()
        self._all_events = []

        try:
            self.jira = JiraWithRetry(spec.server_url, token_auth=spec.token, validate=True)
        except exceptions.JIRAError as exc:
            msg = f"Error establishing a Jira session: {exc.text}"
            raise RuntimeError(msg) from exc
        self.item_class = spec.item_class

    def report(self, msg):
        print(msg)

    def _execute_search_query(self, query):
        items = self.jira.search_issues(query, expand="changelog,renderedFields", maxResults=0)
        return items

    def _perform_and_process_query(self, query):
        results = self._execute_search_query(query)
        results_by_name = {r.key: r for r in results}
        self._all_issues_by_name.update(results_by_name)
        got_names = set(results_by_name.keys())
        return got_names

    def _find_children_by_querying_children(self, parent_name, children_attribute="Epic Link", query_template='{children_query}'):
        children_query = f'"{children_attribute}" = {parent_name}'
        children_names = self._perform_and_process_query(query_template.format(children_query=children_query))
        self._parent_name_to_children_names[parent_name] = children_names
        return children_names

    def _find_children_by_examining_parent(self, parent_name, children_field_name="subtasks"):
        parent = self._all_issues_by_name[parent_name]
        children = parent.get_field(children_field_name)
        child_names = set()
        for c in children:
            c = self.jira.issue(c.key, expand="changelog,renderedFields")
            child_names.add(c.key)
            self._all_issues_by_name[c.key] = c
        self._parent_name_to_children_names[parent.key] = child_names
        return child_names

    def _query_children_to_get_children(self, parent_name, query_order):
        return query_order < 2

    def _expand_primary_query_result(self, result_name, order=1):
        children_names = set()
        if self._query_children_to_get_children(result_name, order):
            children_names = self._find_children_by_querying_children(result_name)
        else:
            children_names = self._find_children_by_examining_parent(result_name)
        if children_names:
            new_children = self._expand_primary_query_results(children_names, order + 1)

    def _expand_primary_query_results(self, result_names, order=1):
        for name in result_names:
            if name not in self._parent_name_to_children_names:
                new_results = self._expand_primary_query_result(name, order)
            else:
                new_results = self._parent_name_to_children_names[name]

    def _expand_primary_query_to_tree(self, names_obtained):
        self._expand_primary_query_results(names_obtained, 1)

    def _get_or_create_card(self, name):
        if name in self._cards_by_id:
            card = self._cards_by_id[name]
        else:
            issue = self._all_issues_by_name[name]
            card = self.merge_jira_item_without_children(issue)
        return card

    def export_issue_tree_to_cards(self, root_names: typing.Iterable[str]) -> dict[str, card.BaseCard]:
        exported_cards_by_id = dict()
        for name in root_names:
            exported_cards_by_id[name] = self._get_or_create_card(name)

            children_names = self._parent_name_to_children_names.get(name, [])
            if not children_names:
                continue
            chain = self.export_issue_tree_to_cards(children_names)
            exported_cards_by_id.update(chain)
        return exported_cards_by_id

    def find_card(self, name: str):
        card = self.jira.issue(name)
        if not card:
            msg = (
                f"{card} not found"
            )
            raise ValueError(msg)
        return card

    def _get_and_record_jira_tree(self, query):
        core_results = self._perform_and_process_query(query)
        self._expand_primary_query_to_tree(core_results)
        return core_results

    def _export_jira_tree_to_cards(self, root_results):
        new_cards = self.export_issue_tree_to_cards(root_results)
        self._cards_by_id.update(new_cards)
        self.resolve_inheritance(new_cards)
        return set(new_cards.keys())

    def import_data(self, spec, extractor_cls=EventExtractor):
        issue_names_requiring_events = set()

        if spec.retrospective_query:
            self.report("Gathering retro stuff")
            root_results = self._get_and_record_jira_tree(spec.retrospective_query)
            new_cards = self._export_jira_tree_to_cards(root_results)
            self._retro_cards.update(new_cards)

        if spec.projective_query:
            self.report("Gathering proj stuff")
            root_results = self._get_and_record_jira_tree(spec.projective_query)
            new_cards = self._export_jira_tree_to_cards(root_results)
            self._projective_cards.update(new_cards)

        new_cards = self._retro_cards.union(self._projective_cards)
        for name in new_cards:
            if name not in self._all_issues_by_name:
                continue
            extractor = extractor_cls(self._all_issues_by_name[name], spec.cutoff_date)
            new_events = extractor.get_task_events(self)
            self._all_events.extend(new_events)

    def resolve_inheritance(self, root_names: typing.Iterable[str]):
        for root_name in root_names:
            self.resolve_inheritance_of_attributes(root_name)

    def inherit_attributes(self, parent, child):
        parent.add_element(child)
        child.tier = parent.tier

    def resolve_inheritance_of_attributes(self, name):
        item = self._cards_by_id[name]
        child_names = self._parent_name_to_children_names.get(item.name, [])
        for child_name in child_names:
            child = self._cards_by_id[child_name]
            self.inherit_attributes(item, child)
            self.resolve_inheritance_of_attributes(child_name)

    def _get_contents_of_rendered_field(self, item, field_name):
        ret = self._get_contents_of_field(item, field_name, "")
        try:
            ret = getattr(item.renderedFields, field_name)
        except AttributeError:
            pass
        ret = ret.replace("\r", "")
        return ret

    def _get_contents_of_field(self, item, field_name, default_value=None):
        ret = default_value
        try:
            ret = item.get_field(field_name) or default_value
        except AttributeError:
            pass
        return ret

    @classmethod
    def status_to_state(cls, item, jira_string=""):
        if not jira_string:
            jira_string = item.get_field("status").name
        ret = cls._status_to_state(item, jira_string)
        return ret

    @classmethod
    def _item_is_closed_done(cls, item, jira_string):
        resolution = item.get_field("resolution")
        resolution_text = ""
        if resolution:
            resolution_text = resolution.name
        if jira_string == "Closed" and resolution_text == "Done":
            return True
        return False

    @classmethod
    def _status_to_state(cls, item, jira_string):
        if cls._item_is_closed_done(item, jira_string):
            jira_string = "Done"
        return JIRA_STATUS_TO_STATE.get(jira_string, "irrelevant")

    def merge_jira_item_without_children(self, item):
        result = self.item_class(item.key)
        result.uri = item.permalink()
        result.loading_plugin = "jira"
        result.title = item.get_field("summary") or ""
        result.description = self._get_contents_of_rendered_field(item, "description")
        result.status = self.status_to_state(item)
        priority = item.get_field("priority")
        if not priority:
            result.priority = 0
        else:
            result.priority = JIRA_PRIORITY_TO_VALUE.get(priority.name, 0)

        result.tags = set()

        labels = self._get_contents_of_field(item, "labels", [])
        result.tags = {f"label:{value}" for value in labels}

        if assignee := self._get_contents_of_field(item, "assignee"):
            result.assignee = get_name_from_person_field(assignee)

        return result

    def save(self, retro_card_io_class, proj_card_io_class, event_manager_class):
        if self._retro_cards:
            retro_card_io_class.forget_all()
            save_exported_jira_tasks(self._cards_by_id, self._retro_cards, retro_card_io_class)
        if self._projective_cards:
            proj_card_io_class.forget_all()
            save_exported_jira_tasks(self._cards_by_id, self._projective_cards, proj_card_io_class)

        storer = event_manager_class()
        for e in self._all_events:
            storer.add_event(e)
        storer.save()

    def get_collected_stats(self):
        ret = Collected(
            Retrospective=len(self._retro_cards),
            Projective=len(self._projective_cards),
            Events=len(self._all_events),
        )
        return ret


def _convert_stats_to_strings(stats):
    pieces = []
    if r := stats.Retrospective:
        pieces.append(f"{r} retrospective items")
    if p := stats.Projective:
        pieces.append(f"{p} planning items")
    if e := stats.Events:
        pieces.append(f"{e} events")
    return pieces


def _format_string_stats_into_sentence(pieces):
    if not pieces:
        return "Collected nothing."
    fusion = ", ".join(pieces[:-1])
    if fusion:
        fusion = f"{fusion} and {pieces[-1]}"
    else:
        fusion = pieces[-1]
    return f"Collected {fusion}."


def stats_to_summary(stats):
    pieces = _convert_stats_to_strings(stats)
    return _format_string_stats_into_sentence(pieces)


def do_stuff(spec):
    importer = Importer(spec)
    importer.import_data(spec)
    retro_io = web_utils.get_retro_loader()[1]
    proj_io = web_utils.get_proj_loader()[1]
    importer.save(retro_io, proj_io, simpledata.EventManager)
    return importer.get_collected_stats()

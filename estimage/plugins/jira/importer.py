import time

from jira import JIRA, exceptions


JIRA_STATUS_TO_STATE = {
    "New": "todo",
    "Done": "done",
    "Closed": "irrelevant",
    "In Progress": "in_progress",
    "To Do": "todo",
}


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


class JiraWithRetry(JIRA):
    def search_issues(self, * args, ** kwargs):
        return jira_retry(super().search_issues, * args, ** kwargs)

    def issue(self, * args, ** kwargs):
        return jira_retry(super().issue, * args, ** kwargs)


class BareboneImporter:
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

    def find_card(self, name: str):
        card = self.jira.issue(name)
        if not card:
            msg = f"{card} not found"
            raise ValueError(msg)
        return card

    @classmethod
    def status_to_state(cls, item, jira_string=""):
        if not jira_string:
            jira_string = item.get_field("status").name
        ret = cls._status_to_state(item, jira_string)
        return ret

    @classmethod
    def _status_to_state(cls, item, jira_string):
        if cls._item_is_closed_done(item, jira_string):
            jira_string = "Done"
        return JIRA_STATUS_TO_STATE.get(jira_string, "irrelevant")

    @classmethod
    def _get_contents_of_rendered_field(cls, item, field_name):
        ret = cls._get_contents_of_field(item, field_name, "")
        try:
            ret = getattr(item.renderedFields, field_name)
        except AttributeError:
            pass
        ret = ret.replace("\r", "")
        return ret

    @classmethod
    def _get_contents_of_field(cls, item, field_name, default_value=None):
        ret = default_value
        try:
            ret = item.get_field(field_name) or default_value
        except AttributeError:
            pass
        return ret

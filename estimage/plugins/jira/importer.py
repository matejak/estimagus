import collections
import datetime
import re
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
    def __init__(self, * args, ** kwargs):
        super().__init__(* args, ** kwargs)
        self.last_request_time = datetime.datetime.now()
        # Minimum time between requests in seconds
        self.subsequent_request_time_off = 0

    def wait_until_next_request(self):
        now = datetime.datetime.now()
        time_since_last_request = now - self.last_request_time
        difference_in_seconds = time_since_last_request.total_seconds()
        wait_for = max(0, self.subsequent_request_time_off - difference_in_seconds)
        time.sleep(difference_in_seconds)

    def search_issues(self, * args, ** kwargs):
        self.wait_until_next_request()
        self.last_request_time = datetime.datetime.now()
        return jira_retry(super().search_issues, * args, ** kwargs)

    def issue(self, * args, ** kwargs):
        self.wait_until_next_request()
        self.last_request_time = datetime.datetime.now()
        return jira_retry(super().issue, * args, ** kwargs)


class JiraWrapper:
    def __init__(self, spec):
        self.field_ids_map = dict()
        self._all_issues_by_name = dict()
        auth_kwargs = dict(token_auth=spec.token)
        if self._instance_is_cloud_hosted(spec.server_url) and spec.email:
            auth_kwargs = dict(basic_auth=(spec.email, spec.token))

        try:
            self.jira = JiraWithRetry(spec.server_url, ** auth_kwargs, validate=True)
        except exceptions.JIRAError as exc:
            msg = f"Error establishing a Jira session: {exc.text}"
            raise RuntimeError(msg) from exc

        self.item_class = spec.item_class
        self.expand = []
        self.fields = ["summary"]
        self.construct_field_mapping()

    @staticmethod
    def _instance_is_cloud_hosted(url):
        slashless_url = url.rstrip("/")
        return slashless_url.endswith(".atlassian.net")

    def construct_field_mapping(self):
        pass


class RuntimeFieldMapper(JiraWrapper):
    def construct_field_mapping(self):
        super().construct_field_mapping()
        field_map = collections.defaultdict(list)

        all_fields = self.jira.fields()
        for field in all_fields:
            field_map[field["name"]].append(field["id"])

        self.field_ids_map.update(field_map)


class BareboneImporter(JiraWrapper):
    def __init__(self, spec):
        super().__init__(spec)
        self.fields.extend([
            "status", "resolution",
        ])

    def look_up_field_id(self, name):
        entries = self.field_ids_map.get(name)
        if entries is None:
            msg = f"Unknown field '{name}' in Jira"
            raise ValueError(msg)
        if len(entries) > 1:
            msg = f"Ambiguous field {name} in Jira - Resolves to: {entries}"
            RuntimeWarning(msg)
        return self.field_ids_map.get(name)[0]

    def report(self, msg):
        print(msg)

    def _execute_search_query(self, query):
        items = self.jira.search_issues(query, fields=self.fields, expand=self.expand, maxResults=0)
        return items

    def perform_and_process_query(self, query) -> set:
        results = self._execute_search_query(query)
        results_by_name = {r.key: r for r in results}
        self._all_issues_by_name.update(results_by_name)
        got_names = set(results_by_name.keys())
        return got_names

    def find_card(self, name: str, expand=""):
        card = self.jira.issue(name, expand=expand)
        if not card:
            msg = f"{card} not found"
            raise ValueError(msg)
        return card

    def just_get_or_find_and_store(self, name: str, expand=""):
        if issue := self._all_issues_by_name.get(name):
            return issue
        issue = self.find_card(name, expand)
        self._all_issues_by_name[name] = issue
        return issue

    def status_to_state(self, item, jira_string=""):
        if not jira_string:
            jira_string = self._get_contents_of_field(item, "status").name
        ret = self._status_to_state(item, jira_string)
        return ret

    def _item_is_closed_done(self, item, jira_string):
        resolution = None
        if hasattr(item.fields, "resolution"):
            resolution = self._get_contents_of_field(item, "resolution", "")
        resolution_text = ""
        if resolution:
            resolution_text = resolution.name
        if jira_string == "Closed" and resolution_text == "Done":
            return True
        return False

    def _status_to_state(self, item, jira_string):
        if self._item_is_closed_done(item, jira_string):
            jira_string = "Done"
        return JIRA_STATUS_TO_STATE.get(jira_string, "irrelevant")

    def _get_contents_of_rendered_field(self, item, field_name):
        ret = self._get_field_attribute(item.fields, field_name, "")
        try:
            ret_rendered = self._get_field_attribute(item.renderedFields, field_name, "")
            if ret_rendered:
                ret = ret_rendered
        except AttributeError:
            pass
        ret = ret.replace("\r", "")
        return ret

    def _get_field_attribute(self, fields, field_name, default_value):
        field_name_is_id = field_name in self.fields
        field_name_is_id |= hasattr(fields, field_name)
        if field_name_is_id:
            field_id = field_name
        else:
            field_id = self.look_up_field_id(field_name)
        ret = default_value
        try:
            ret = getattr(fields, field_id)
            if ret is None:
                ret = default_value
        except AttributeError:
            pass
        return ret

    def _get_contents_of_field(self, item, field_name, default_value=None):
        return self._get_field_attribute(item.fields, field_name, default_value)

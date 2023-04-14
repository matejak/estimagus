import re
import datetime
import dateutil.relativedelta

from estimage import simpledata
from . import jira


QUARTER_TO_MONTH_NUMBER = None
PROJECT_NAME = "OPENSCAP"


TEMPLATE_OVERRIDES = {
    "tree_view_retrospective.html": "rhcompliance-retrotree.html",
}


class InputSpec(jira.InputSpec):
    @classmethod
    def from_dict(cls, input_form) -> "InputSpec":
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


class Importer(jira.Importer):
    def merge_jira_item_without_children(self, item):
        STORY_POINTS = "customfield_12310243"
        EPIC_LINK = "customfield_12311140"
        CONTRIBUTORS = "customfield_12315950"
        COMMITMENT = "customfield_12317404"
        STATUS_SUMMARY = "customfield_12317299"
        WORK_START = "customfield_12313941"
        WORK_END = "customfield_12313942"

        result = super().merge_jira_item_without_children(item)

        result.point_cost = float(item.get_field(STORY_POINTS) or 0)
        result.status_summary = item.get_field(STATUS_SUMMARY) or ""
        try:
            result.status_summary = getattr(item.renderedFields, STATUS_SUMMARY).replace("\r", "")
        except AttributeError:
            pass
        try:
            result.collaborators += [
                jira.name_from_field(c) for c in item.get_field(CONTRIBUTORS) or []]
        except AttributeError:
            pass
        result.tier = 0
        try:
            if commitment_item := item.get_field(COMMITMENT):
                result.tags.add(f"commitment:{commitment_item.value.lower()}")
                if commitment_item.value.lower() == "planned":
                    result.tier = 1
        except AttributeError:
            pass

        work_span = [None, None]
        if work_end := item.get_field(WORK_END):
            work_span[-1] = jira.jira_date_to_datetime(work_end)

        if work_start := item.get_field(WORK_START):
            work_span[0] = jira.jira_date_to_datetime(work_start)

        if work_span[0] or work_span[-1]:
            result.work_span = tuple(work_span)

        return result


def do_stuff(spec):
    importer = Importer(spec)
    importer.save(simpledata.RetroTarget, simpledata.ProjTarget, simpledata.EventManager)

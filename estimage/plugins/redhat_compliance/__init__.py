import re
import datetime
import collections
import dateutil.relativedelta
import typing

from ... import simpledata, data, persistence
from ...entities import status
from ...webapp import web_utils
from ...visualize.burndown import StatusStyle
from .. import jira, redhat_jira
from ..jira.forms import AuthoritativeForm, ProblemForm


BaseCardWithStatus = redhat_jira.BaseCardWithStatus
CardSynchronizer = redhat_jira.CardSynchronizer

EXPORTS = dict(
    AuthoritativeForm="AuthoritativeForm",
    ProblemForm="ProblemForm",
    BaseCard="BaseCardWithStatus",
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


OPENSCAP_STATUS_TO_STATE = {
    "Backlog": "todo",
    "Refinement": "todo",
    "New": "todo",
    "Done": "done",
    "Abandoned": "irrelevant",
    "Closed": "irrelevant",
    "In Progress": "in_progress",
    "Needs Peer Review": "review",
    "Review": "review",
    "To Do": "todo",
}


class InputSpec(redhat_jira.InputSpec):
    def _get_epochs(self, input_form):
        epoch = input_form.quarter.data
        planning_epoch = epoch
        if input_form.project_next.data:
            planning_epoch = next_epoch_of(planning_epoch)

        return epoch, planning_epoch

    def set_cutoff_date(self, input_form):
        epoch, planning_epoch = self._get_epochs(input_form)

        self.cutoff_date = epoch_start_to_datetime(epoch)

    def set_queries(self, input_form):
        epoch, planning_epoch = self._get_epochs(input_form)

        query_lead = f"project = {PROJECT_NAME} AND type = Epic AND"
        retro_narrowing = f"sprint = {epoch} AND Commitment in (Committed, Planned)"
        proj_narrowing = f"sprint = {planning_epoch}"
        self.retrospective_query = " ".join((query_lead, retro_narrowing))
        self.projective_query = " ".join((query_lead, proj_narrowing))


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


class Importer(redhat_jira.ImporterWithStatus):

    def merge_jira_item_without_children(self, item):

        result = super().merge_jira_item_without_children(item)

        self._record_commitment_as_tier_and_tags(result, item)
        return result

    def _record_commitment_as_tier_and_tags(self, result, item):
        result.tier = 0
        try:
            if commitment_item := item.get_field(self.COMMITMENT):
                result.tags.add(f"commitment:{commitment_item.value.lower()}")
                if commitment_item.value.lower() == "planned":
                    result.tier = 1
        except AttributeError:
            pass

    @classmethod
    def _status_to_state(cls, item, jira_string):
        if cls._item_is_closed_done(item, jira_string):
            return "done"

        item_name = item.key

        if item_name.startswith("OPENSCAP"):
            return OPENSCAP_STATUS_TO_STATE.get(jira_string, "irrelevant")
        else:
            return super()._status_to_state(item, jira_string)


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


class Workloads:
    def __init__(self,
                 cards: typing.Iterable[data.BaseCard],
                 model: data.EstiModel,
                 * args, ** kwargs):
        cards = [t for t in cards if t.tier == 0]
        super().__init__(* args, model=model, cards=cards, ** kwargs)

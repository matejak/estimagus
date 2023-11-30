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
        ret.retrospective_query = query
        ret.projective_query = query
        ret.item_class = app.config["classes"]["BaseTarget"]
        return ret


class Importer(jira.Importer):
    STORY_POINTS = "customfield_12310243"
    EPIC_LINK = "customfield_12311140"

    def _get_points_of(self, item):
        return float(item.get_field(self.STORY_POINTS) or 0)

    def _set_points_of(self, item, points):
        item.update({self.STORY_POINTS: round(points, 2)})

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

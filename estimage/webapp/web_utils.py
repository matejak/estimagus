import flask
import flask_login

from .. import simpledata as webdata
from .. import utilities


def get_target_tree_with_no_double_occurence(cls):
    all_targets = cls.load_all_targets()
    targets_tree_without_duplicates = utilities.reduce_subsets_from_sets(all_targets)
    return targets_tree_without_duplicates


def get_user_model(user_id, cls, targets_tree_without_duplicates=None):
    if targets_tree_without_duplicates is None:
        targets_tree_without_duplicates = get_target_tree_with_no_double_occurence(cls)
    authoritative_pollster = webdata.AuthoritativePollster()
    user_pollster = webdata.UserPollster(user_id)
    model = webdata.get_model(targets_tree_without_duplicates)
    authoritative_pollster.inform_results(model.get_all_task_models())
    user_pollster.inform_results(model.get_all_task_models())
    return model


def render_template(template_basename, title, **kwargs):
    authenticated_user = ""
    if flask_login.current_user.is_authenticated:
        authenticated_user = flask_login.current_user
    return flask.render_template(
        template_basename, title=title, authenticated_user=authenticated_user, ** kwargs)



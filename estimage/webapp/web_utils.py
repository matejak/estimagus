import flask
import flask_login
import werkzeug

from .. import simpledata as webdata
from .. import utilities, persistence


def get_retro_loader():
    target_class = flask.current_app.config["classes"]["BaseTarget"]
    loader = type("loader", (webdata.RetroTargetIO, persistence.LOADERS[target_class]["ini"]), dict())
    return target_class, loader


def get_proj_loader():
    target_class = flask.current_app.config["classes"]["BaseTarget"]
    loader = type("loader", (webdata.ProjTargetIO, persistence.LOADERS[target_class]["ini"]), dict())
    return target_class, loader


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
    try:
        authoritative_pollster.supply_valid_estimations_to_tasks(model.get_all_task_models())
    except ValueError as exc:
        msg = f"There were errors processing own inputs: {str(exc)}"
        flask.flash(msg)
    try:
        user_pollster.supply_valid_estimations_to_tasks(model.get_all_task_models())
    except ValueError as exc:
        msg = f"There were errors processing consensus inputs: {str(exc)}"
        flask.flash(msg)
    return model


def render_template(path, title, **kwargs):
    loaded_templates = dict()
    loaded_templates["base"] = flask.current_app.jinja_env.get_template("base.html")
    kwargs.update(loaded_templates)
    authenticated_user = ""
    if flask_login.current_user.is_authenticated:
        authenticated_user = flask_login.current_user
    maybe_overriden_path = flask.current_app.config["plugins_templates_overrides"](path)
    return flask.render_template(
        maybe_overriden_path, title=title, authenticated_user=authenticated_user,
        ** kwargs)


def safe_url_to_redirect(candidate):
    if not candidate or werkzeug.urls.url_parse(candidate).netloc != '':
        candidate = flask.url_for('main.tree_view')
    return candidate

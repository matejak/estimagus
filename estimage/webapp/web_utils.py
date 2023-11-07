import flask
import flask_login
import werkzeug

from .. import simpledata as webdata
from .. import utilities, persistence


def _get_entrydef_loader(flavor, backend):
    target_class = flask.current_app.config["classes"]["BaseTarget"]
    # in the special case of the ini backend, the registered loader doesn't call super()
    # when looking up CONFIG_FILENAME
    loader = type("loader", (flavor, persistence.SAVERS[target_class][backend], persistence.LOADERS[target_class][backend]), dict())
    return target_class, loader


def get_retro_loader():
    return _get_entrydef_loader(webdata.RetroTargetIO, "ini")


def get_proj_loader():
    return _get_entrydef_loader(webdata.ProjTargetIO, "ini")


def get_workloads(workload_type):
    if workloads := flask.current_app.config["classes"].get("Workloads"):
        workload_type = type(f"ext_{workload_type.__name__}", (workloads, workload_type), dict())
    return workload_type


def get_all_tasks_by_id_and_user_model(spec, user_id):
    if spec == "retro":
        cls, loader = get_retro_loader()
    elif spec == "proj":
        cls, loader = get_proj_loader()
    else:
        msg = "Unknown specification of source: {spec}"
        raise KeyError(msg)
    all_targets_by_id = loader.get_loaded_targets_by_id(cls)
    targets_list = list(all_targets_by_id.values())
    targets_tree_without_duplicates = utilities.reduce_subsets_from_sets(targets_list)
    model = get_user_model(user_id, targets_tree_without_duplicates)
    model.update_targets_with_values(targets_tree_without_duplicates)
    return all_targets_by_id, model


def get_user_model(user_id, targets_tree_without_duplicates):
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
        custom_items=CUSTOM_MENU_ITEMS, ** kwargs)


def safe_url_to_redirect(candidate):
    if not candidate or werkzeug.urls.url_parse(candidate).netloc != '':
        candidate = flask.url_for('main.tree_view')
    return candidate


CUSTOM_MENU_ITEMS = dict()

def is_primary_menu_of(blueprint, title):
    def wrapper(fun):
        endpoint = f"{blueprint.name}.{fun.__name__}"
        CUSTOM_MENU_ITEMS[title] = endpoint
        return fun
    return wrapper

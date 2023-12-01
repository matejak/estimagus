import flask
import flask_login
import urllib

from .. import simpledata as webdata
from .. import utilities, persistence


def app_is_multihead(app=None):
    if not app:
        app = flask.current_app
    return "head" in app.config


def url_for(endpoint, * args, ** kwargs):
    if app_is_multihead():
        head_name = flask.request.blueprints[-1]
        if head_name in ("login",):
            head_name = "DEMO"
        endpoint = f"{head_name}.{endpoint}"
    return flask.url_for(endpoint, * args, ** kwargs)


def get_final_class(class_name, app=None):
    if app_is_multihead(app):
        head_name = flask.request.blueprints[-1]
        ret = flask.current_app.config["head"][head_name]["classes"].get(class_name)
    else:
        ret = flask.current_app.config["classes"].get(class_name)
    return ret


def _get_entrydef_loader(flavor, backend):
    target_class = get_final_class("BaseTarget")
    # in the special case of the ini backend, the registered loader doesn't call super()
    # when looking up CONFIG_FILENAME
    loader = type("loader", (flavor, persistence.SAVERS[target_class][backend], persistence.LOADERS[target_class][backend]), dict())
    return target_class, loader


def get_retro_loader():
    return _get_entrydef_loader(webdata.RetroTargetIO, "ini")


def get_proj_loader():
    return _get_entrydef_loader(webdata.ProjTargetIO, "ini")


def get_workloads(workload_type):
    if workloads := get_final_class("Workloads"):
        workload_type = type(f"ext_{workload_type.__name__}", (workload_type, workloads), dict())
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
    # maybe_overriden_path = flask.current_app.config["plugins_templates_overrides"](path)
    head_prefix = ""
    if "head" in flask.current_app.config:
        head_prefix = f"{flask.request.blueprints[-1]}."
    return flask.render_template(
        path, head_prefix=head_prefix, title=title, authenticated_user=authenticated_user, relative_url_for=url_for,
        custom_items=CUSTOM_MENU_ITEMS, ** kwargs)


def safe_url_to_redirect(candidate):
    if not candidate or urllib.parse.urlparse(candidate).netloc != '':
        if app_is_multihead():
            candidate = flask.url_for('DEMO.main.tree_view')
        else:
            candidate = flask.url_for('main.tree_view')
    return candidate


CUSTOM_MENU_ITEMS = dict()

def is_primary_menu_of(blueprint, title):
    def wrapper(fun):
        endpoint = f"{blueprint.name}.{fun.__name__}"
        CUSTOM_MENU_ITEMS[title] = endpoint
        return fun
    return wrapper

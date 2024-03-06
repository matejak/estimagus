import flask
import flask_login
import urllib

from .. import simpledata as webdata
from .. import PluginResolver
from .. import utilities, persistence


@PluginResolver.class_is_extendable("Footer")
class Footer:
    def get_footer_html(self):
        return ""


def app_is_multihead(app=None):
    if not app:
        app = flask.current_app
    return "head" in app.config


def head_url_for(endpoint, * args, ** kwargs):
    app = flask.current_app
    endpoint = app.get_correct_context_endpoint(endpoint)
    return flask.url_for(endpoint, * args, ** kwargs)


def _get_card_loader(flavor, backend):
    card_class = flask.current_app.get_final_class("BaseCard")
    # in the special case of the ini backend, the registered loader doesn't call super()
    # when looking up CONFIG_FILENAME
    loader = type("loader", (flavor, persistence.SAVERS[card_class][backend], persistence.LOADERS[card_class][backend]), dict())
    return card_class, loader


def get_retro_loader():
    return _get_card_loader(webdata.RetroCardIO, "ini")


def get_proj_loader():
    return _get_card_loader(webdata.ProjCardIO, "ini")


def get_workloads(workload_type):
    if workloads := flask.current_app.get_final_class("Workloads"):
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
    all_cards_by_id = loader.get_loaded_cards_by_id(cls)
    cards_list = list(all_cards_by_id.values())
    cards_tree_without_duplicates = utilities.reduce_subsets_from_sets(cards_list)
    model = get_user_model(user_id, cards_tree_without_duplicates)
    model.update_cards_with_values(cards_tree_without_duplicates)
    return all_cards_by_id, model


def get_user_model(user_id, cards_tree_without_duplicates):
    authoritative_pollster = webdata.AuthoritativePollster()
    user_pollster = webdata.UserPollster(user_id)
    statuses = flask.current_app.get_final_class("Statuses")()
    model = webdata.get_model(cards_tree_without_duplicates, None, statuses)
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


def get_head_absolute_endpoint(endpoint):
    return flask.current_app.get_correct_context_endpoint(endpoint)


def get_custom_items_dict():
    custom_items = dict()
    app = flask.current_app
    for plugin, (title, endpoint) in CUSTOM_MENU_ITEMS.items():
        if plugin in app.get_plugins_in_context():
            custom_items[title] = get_head_absolute_endpoint(endpoint)
    return custom_items


def render_template(path, title, **kwargs):
    loaded_templates = dict()
    loaded_templates["base"] = flask.current_app.jinja_env.get_template("base.html")
    footer = flask.current_app.get_final_class("Footer")()
    kwargs.update(loaded_templates)
    authenticated_user = ""
    if flask_login.current_user.is_authenticated:
        authenticated_user = flask_login.current_user
    maybe_overriden_path = flask.current_app.translate_path(path)
    custom_menu_items = get_custom_items_dict()
    return flask.render_template(
        maybe_overriden_path, get_head_absolute_endpoint=get_head_absolute_endpoint,
        title=title, authenticated_user=authenticated_user, head_url_for=head_url_for,
        custom_items=custom_menu_items, footer=footer, ** kwargs)


def safe_url_to_redirect(candidate):
    if not candidate or urllib.parse.urlparse(candidate).netloc != '':
        if app_is_multihead():
            candidate = flask.url_for('neck.index')
        else:
            candidate = flask.url_for('main.tree_view')
    return candidate


CUSTOM_MENU_ITEMS = dict()

def is_primary_menu_of(plugin_name, blueprint, title):
    def wrapper(fun):
        endpoint = f"{blueprint.name}.{fun.__name__}"
        CUSTOM_MENU_ITEMS[plugin_name] = (title, endpoint)
        return fun
    return wrapper

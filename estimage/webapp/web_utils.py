import flask
import flask_login
import urllib

from . import routers
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


def get_workloads(workload_type):
    if workloads := flask.current_app.get_final_class("Workloads"):
        workload_type = type(f"ext_{workload_type.__name__}", (workload_type, workloads), dict())
    return workload_type


def get_head_absolute_endpoint(endpoint):
    return flask.current_app.get_correct_context_endpoint(endpoint)


def get_custom_menu_items_dict():
    custom_items = dict()
    app = flask.current_app
    for plugin, (title, endpoint) in CUSTOM_MENU_ITEMS.items():
        if plugin in app.get_plugins_in_context():
            custom_items[title] = get_head_absolute_endpoint(endpoint)
    return custom_items


def render_template(path, title, **kwargs):
    footer = flask.current_app.get_final_class("Footer")()
    authenticated_user = ""
    if flask_login.current_user.is_authenticated:
        authenticated_user = flask_login.current_user

    maybe_overriden_path = flask.current_app.translate_path(path)
    ancestor_path_map = flask.current_app.get_ancestor_map(path)
    kwargs.update(ancestor_path_map)

    custom_menu_items = get_custom_menu_items_dict()
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


def updated_cards_and_events_from_tracker():
    routers.AggregationRouter.clear_cache()

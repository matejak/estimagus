import importlib
import logging


def _get_routes_or_none_or_error(plugin):
    full_module_name = f"{plugin.__name__}.routes"
    try:
        importlib.import_module(full_module_name)
        return plugin.routes
    except ModuleNotFoundError as exc:
        if exc.name == full_module_name:
            msg = f"Plugin {plugin.__name__} doesn't have the routes module"
            logging.info(msg)
            return None
        msg = f"Couldn't import '{full_module_name}' due to a missing dependency '{exc.name}'"
        raise RuntimeError(msg)


def _get_plugin_routes_module(plugin):
    if hasattr(plugin, "routes"):
        return plugin.routes

    return _get_routes_or_none_or_error(plugin)


def get_plugin_blueprint(plugin):
    routes = _get_plugin_routes_module(plugin)
    if not hasattr(routes, "bp"):
        return None
    return routes.bp


def get_plugin(name, base=None):
    if base is None:
        base = "estimage.plugins"
    try:
        plugin = importlib.import_module(f"{base}.{name}")
    except ModuleNotFoundError as exc:
        msg = f"Plugin {name} not found, check for typos ({exc})"
        raise NameError(msg) from exc
    return plugin

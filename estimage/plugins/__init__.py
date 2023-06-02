import importlib


def _get_plugin_routes_module(plugin):
    if not hasattr(plugin, "routes"):
        try:
            importlib.import_module(f"{plugin.__name__}.routes")
        except Exception:
            return None
    return plugin.routes


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

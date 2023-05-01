import importlib


def get_plugin(name, base=None):
    if base is None:
        base = "estimage.plugins"
    try:
        plugin = importlib.import_module(f"{base}.{name}")
    except ModuleNotFoundError as exc:
        msg = f"Plugin {name} not found, check for typos ({exc})"
        raise NameError(msg) from exc
    return plugin

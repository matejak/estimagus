import importlib


def get_plugin(name):
    try:
        plugin = importlib.import_module(f"estimage.plugins.{name}")
    except ModuleNotFoundError:
        msg = "Plugin {name} not found, check for typos"
        raise NameError(msg)
    return plugin

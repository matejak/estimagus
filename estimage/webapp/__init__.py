import collections
import pathlib

import flask
from flask_login import LoginManager
from flask_bootstrap import Bootstrap5
from jinja2 import loaders

from .. import data, simpledata, plugins, PluginResolver
from . import users, config

from .neck import bp as neck_bp
from .main import bp as main_bp
from .vis import bp as vis_bp
from .login import bp as login_bp
from .persons import bp as persons_bp

login = LoginManager()


class PluginFriendlyFlask(flask.Flask):
    def __init__(self, import_name, ** kwargs):
        webapp_folder = pathlib.Path(__file__).absolute().parent
        templates_folder = webapp_folder / "templates"
        plugins_folder = webapp_folder / ".." / "plugins"

        super().__init__(import_name, ** kwargs)
        self.jinja_loader = loaders.FileSystemLoader(
            (templates_folder, plugins_folder))

    @staticmethod
    def _plugin_template_location(plugin_name, template_name):
        return str(pathlib.PurePath(plugin_name) / "templates" / template_name)

    def get_final_class(self, class_name):
        return self.get_config_option("classes").get(class_name)

    def get_config_option(self, option):
        raise NotImplementedError()


class PluginFriendlySingleheadFlask(PluginFriendlyFlask):
    def __init__(self, import_name, ** kwargs):
        super().__init__(import_name, ** kwargs)
        self._plugin_resolver = PluginResolver()
        self._plugin_resolver.add_known_extendable_classes()

    def supply_with_plugins(self, plugins_dict):
        for plugin in plugins_dict.values():
            self._plugin_resolver.resolve_extension(plugin)

    def store_plugins_to_config(self):
        self.config["classes"] = self._plugin_resolver.class_dict

    def get_config_option(self, option):
        return self.config[option]


class PluginFriendlyMultiheadFlask(PluginFriendlyFlask):
    def __init__(self, import_name, ** kwargs):
        super().__init__(import_name, ** kwargs)
        self._plugin_resolvers = dict()

    def _new_head(self, name):
        self._plugin_resolvers[name] = PluginResolver()
        self._plugin_resolvers[name].add_known_extendable_classes()

    def supply_with_plugins(self, head, plugins_dict):
        self._new_head(head)
        for plugin in plugins_dict.values():
            self._plugin_resolvers[head].resolve_extension(plugin)

    def store_plugins_to_config(self, head):
        self.config["head"][head]["classes"] = self._plugin_resolvers[head].class_dict

    @property
    def current_head(self):
        return flask.request.blueprints[-1]

    def get_config_option(self, option):
        return self.config["head"][self.current_head][option]


def create_app(config_class=config.Config):
    app = PluginFriendlySingleheadFlask(__name__)
    app.jinja_env.globals.update(dict(State=data.State))
    app.config.from_object(config_class)
    config_class = simpledata.AppData
    config_class.DATADIR = pathlib.Path(app.config["DATA_DIR"])
    app.config.from_object(config.read_or_create_config(simpledata.AppData))
    plugins_dict = {name: plugins.get_plugin(name) for name in app.config["PLUGINS"]}

    app.supply_with_plugins(plugins_dict)
    app.store_plugins_to_config()

    app.register_blueprint(main_bp)
    app.register_blueprint(vis_bp, url_prefix="/vis")
    app.register_blueprint(login_bp)
    app.register_blueprint(persons_bp)
    for plugin in plugins_dict.values():
        bp = plugins.get_plugin_blueprint(plugin)
        if bp:
            app.register_blueprint(bp, url_prefix="/plugins")
    Bootstrap5(app)

    login.init_app(app)
    login.user_loader(users.load_user)
    login.login_view = "login.auto_login"

    if not app.debug and not app.testing:
        pass

    return app


def create_app_multihead(config_class=config.MultiheadConfig):
    app = PluginFriendlyMultiheadFlask(__name__)
    app.jinja_env.globals.update(dict(State=data.State))
    app.config.from_object(config_class)
    app.config["head"] = collections.defaultdict(dict)

    for directory in app.config["DATA_DIRS"]:
        configure_head(app, directory)

    app.register_blueprint(login_bp)
    app.register_blueprint(neck_bp)

    Bootstrap5(app)

    login.init_app(app)
    login.user_loader(users.load_user)
    login.login_view = "login.auto_login"

    if not app.debug and not app.testing:
        pass

    return app


def configure_head(app, directory):
    config_class = simpledata.AppData
    config_class.DATADIR = pathlib.Path(directory)
    app.config["head"][directory].update(config.read_or_create_config(simpledata.AppData).__dict__)

    metadata = app.config["head"][directory].pop("META", dict())
    app.config["head"][directory]["description"] = metadata.get("description", "")
    app.config["head"][directory]["PLUGINS"] = config.parse_csv(metadata.get("plugins_csv", ""))

    plugins_dict = {name: plugins.get_plugin(name) for name in app.config["head"][directory]["PLUGINS"]}
    app.supply_with_plugins(directory, plugins_dict)
    app.store_plugins_to_config(directory)

    bp = flask.Blueprint(directory, __name__, url_prefix=f"/{directory}")

    bp.register_blueprint(main_bp)
    bp.register_blueprint(vis_bp, url_prefix="/vis")
    bp.register_blueprint(persons_bp)

    for plugin in plugins_dict.values():
        plugin_bp = plugins.get_plugin_blueprint(plugin)
        if plugin_bp:
            bp.register_blueprint(plugin_bp, url_prefix=f"/plugins")

    app.register_blueprint(bp)

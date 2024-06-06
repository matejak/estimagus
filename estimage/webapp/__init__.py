import collections
import pathlib
import os

import flask
from flask_login import LoginManager
from flask_caching import Cache
from flask_bootstrap import Bootstrap5
from jinja2 import loaders

LOGIN = LoginManager()
CACHE = Cache()


from .. import data, simpledata, plugins, PluginResolver
from . import users, config

from .neck import bp as neck_bp
from .main import bp as main_bp
from .vis import bp as vis_bp
from .login import bp as login_bp
from .persons import bp as persons_bp


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

    def _populate_template_overrides_map(self, plugins_dict, overrides_map):
        for plugin_name, plugin in plugins_dict.items():
            if not hasattr(plugin, "TEMPLATE_OVERRIDES"):
                continue
            overrides = plugin.TEMPLATE_OVERRIDES
            for overriden, overriding in overrides.items():
                template_path = self._plugin_template_location(plugin_name, overriding)
                overrides_map[overriden] = template_path

    def get_final_class(self, class_name):
        return self.get_config_option("classes").get(class_name)

    def get_config_option(self, option):
        raise NotImplementedError()

    def get_plugins_in_context(self):
        raise NotImplementedError()

    def get_correct_context_endpoint(self, endpoint):
        return endpoint

    def get_perhaps_overriden_path(self, path):
        raise NotImplementedError()


class PluginFriendlySingleheadFlask(PluginFriendlyFlask):
    def __init__(self, import_name, ** kwargs):
        super().__init__(import_name, ** kwargs)
        self._plugin_resolver = PluginResolver()
        self._plugin_resolver.add_known_extendable_classes()

        self._template_overrides_map = dict()

    def supply_with_plugins(self, plugins_dict):
        for plugin in plugins_dict.values():
            self._plugin_resolver.resolve_extension(plugin)
        self._populate_template_overrides_map(plugins_dict, self._template_overrides_map)

    def translate_path(self, template_name):
        maybe_overriden_path = self._template_overrides_map.get(template_name, template_name)
        return maybe_overriden_path

    def store_plugins_to_config(self):
        self.config["classes"] = self._plugin_resolver.class_dict

    def get_config_option(self, option):
        return self.config[option]

    def get_plugins_in_context(self):
        return self.get_config_option("PLUGINS")


class PluginFriendlyMultiheadFlask(PluginFriendlyFlask):
    NON_HEAD_BLUEPRINTS = ("login", "neck")

    def __init__(self, import_name, ** kwargs):
        super().__init__(import_name, ** kwargs)
        self._plugin_resolvers = dict()
        self._template_overrides_maps = dict()

        no_plugins = PluginResolver()
        no_plugins.add_known_extendable_classes()
        self.config["classes"] = no_plugins.class_dict

    def _new_head(self, name):
        self._plugin_resolvers[name] = PluginResolver()
        self._plugin_resolvers[name].global_symbol_prefix = name
        self._plugin_resolvers[name].add_known_extendable_classes()

        self._template_overrides_maps[name] = dict()

    def supply_with_plugins(self, head, plugins_dict):
        self._new_head(head)
        for plugin in plugins_dict.values():
            self._plugin_resolvers[head].resolve_extension(plugin)
        self._populate_template_overrides_map(plugins_dict, self._template_overrides_maps[head])

    def translate_path(self, template_name):
        if self.current_head in self.NON_HEAD_BLUEPRINTS:
            return template_name
        return self._template_overrides_maps[self.current_head].get(template_name, template_name)

    def store_plugins_to_config(self, head):
        self.config["head"][head]["classes"] = self._plugin_resolvers[head].class_dict

    @property
    def current_head(self):
        return flask.request.blueprints[-1]

    def get_config_option(self, option):
        if self.current_head in self.NON_HEAD_BLUEPRINTS:
            return self.config[option]
        return self.config["head"][self.current_head][option]

    def get_correct_context_endpoint(self, endpoint):
        if (head_name := self.current_head) in self.NON_HEAD_BLUEPRINTS:
            return super().get_correct_context_endpoint(endpoint)
        return f"{head_name}.{endpoint}"

    def get_plugins_in_context(self):
        if self.current_head in self.NON_HEAD_BLUEPRINTS:
            return dict()
        return self.get_config_option("PLUGINS")


def create_app():
    if "DATA_DIRS" in os.environ:
        app = create_app_multihead()
    else:
        app = create_app_singlehead()
    return app


def create_app_common(app):
    Bootstrap5(app)

    LOGIN.init_app(app)
    LOGIN.user_loader(users.load_user)
    LOGIN.login_view = "login.auto_login"
    # Don't display the "log in to proceed" message, as it is often more confusing than helpful
    # in connection with random logouts and autologins
    LOGIN.login_message = ""

    CACHE.init_app(app, config=app.config)

    if not app.debug and not app.testing:
        pass


def create_app_singlehead(config_class=config.Config):
    app = PluginFriendlySingleheadFlask(__name__)
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

    create_app_common(app)

    return app


def create_app_multihead(config_class=config.MultiheadConfig):
    app = PluginFriendlyMultiheadFlask(__name__)
    app.config.from_object(config_class)
    app.config["head"] = collections.defaultdict(dict)

    for directory in app.config["DATA_DIRS"]:
        configure_head(app, directory)

    app.register_blueprint(login_bp)
    app.register_blueprint(neck_bp)

    create_app_common(app)

    return app


def configure_head(app, directory):
    config_class = simpledata.AppData
    config_class.DATADIR = pathlib.Path(directory)
    head_name = config_class.DATADIR.stem
    app.config["head"][head_name]["DATA_DIR"] = config_class.DATADIR
    app.config["head"][head_name].update(config.read_or_create_config(simpledata.AppData).__dict__)

    metadata = app.config["head"][head_name].pop("META", dict())
    app.config["head"][head_name]["description"] = metadata.get("description", "")
    app.config["head"][head_name]["PLUGINS"] = config.parse_csv(metadata.get("plugins_csv", ""))

    plugins_dict = {name: plugins.get_plugin(name) for name in app.config["head"][head_name]["PLUGINS"]}
    app.supply_with_plugins(head_name, plugins_dict)
    app.store_plugins_to_config(head_name)

    bp = flask.Blueprint(head_name, __name__, url_prefix=f"/{head_name}")

    bp.register_blueprint(main_bp)
    bp.register_blueprint(vis_bp, url_prefix="/vis")
    bp.register_blueprint(persons_bp)

    for plugin in plugins_dict.values():
        plugin_bp = plugins.get_plugin_blueprint(plugin)
        if plugin_bp:
            bp.register_blueprint(plugin_bp, url_prefix=f"/plugins")

    app.register_blueprint(bp)

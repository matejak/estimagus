import pathlib

from flask import Flask
from flask_login import LoginManager
from flask_bootstrap import Bootstrap5
from jinja2 import loaders

from .. import data, simpledata
from . import users, config

from .main import bp as main_bp
from .vis import bp as vis_bp
from .login import bp as login_bp
from .persons import bp as persons_bp

from ..plugins import redhat_compliance

login = LoginManager()


class PluginFriendlyFlask(Flask):
    def __init__(self, import_name, ** kwargs):
        webapp_folder = pathlib.Path(__file__).absolute().parent
        templates_folder = webapp_folder / "templates"
        plugins_folder = webapp_folder / ".." / "plugins"

        super().__init__(import_name, ** kwargs)
        self.jinja_loader = loaders.FileSystemLoader(
            (templates_folder, plugins_folder))

        self.template_overrides_map = dict()

    def set_plugins_dict(self, plugins_dict):
        plugins_dict = dict(redhat_compliance=redhat_compliance)
        self._populate_template_overrides_map(plugins_dict)

        self.config["plugins_templates_overrides"] = self.translate_path

    def _populate_template_overrides_map(self, plugins_dict):
        for plugin_name, plugin in plugins_dict.items():
            if not hasattr(plugin, "TEMPLATE_OVERRIDES"):
                continue
            overrides = plugin.TEMPLATE_OVERRIDES
            for overriden, overriding in overrides.items():
                template_path = self._plugin_template_location(plugin_name, overriding)
                self.template_overrides_map[overriden] = template_path

    @staticmethod
    def _plugin_template_location(plugin_name, template_name):
        return str(pathlib.PurePath(plugin_name) / "templates" / template_name)

    def translate_path(self, template_name):
        maybe_overriden_path = self.template_overrides_map.get(template_name, template_name)
        return maybe_overriden_path


def create_app(config_class=config.Config):
    app = PluginFriendlyFlask(__name__)
    app.jinja_env.globals.update(dict(State=data.State))
    app.config.from_object(config_class)
    app.config.from_object(config.read_or_create_config(simpledata.AppData))

    plugins_dict = dict(redhat_compliance=redhat_compliance)
    app.set_plugins_dict(plugins_dict)

    app.register_blueprint(main_bp)
    app.register_blueprint(vis_bp, url_prefix="/vis")
    app.register_blueprint(login_bp)
    app.register_blueprint(persons_bp)
    Bootstrap5(app)

    login.init_app(app)
    login.user_loader(users.load_user)
    login.login_view = "login.login"

    if not app.debug and not app.testing:
        pass

    return app

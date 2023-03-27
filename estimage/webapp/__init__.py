from flask import Flask
from flask_login import LoginManager
from flask_bootstrap import Bootstrap5

from . import users, config
from estimage import data

from .main import bp as main_bp
from .vis import bp as vis_bp
from .login import bp as login_bp
from .persons import bp as persons_bp

login = LoginManager()


def create_app(config_class=config.Config):
    app = Flask(__name__)
    app.jinja_env.globals.update(dict(State=data.State))
    app.config.from_object(config_class)

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

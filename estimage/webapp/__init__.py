from flask import Flask
from flask_login import LoginManager
from flask_bootstrap import Bootstrap5

from . import users, config
from .main import bp as main_bp
from .main import bp as main_bp

login = LoginManager()


def create_app(config_class=config.Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    app.register_blueprint(main_bp)
    Bootstrap5(app)

    login.init_app(app)
    login.user_loader(users.load_user)
    login.login_view = "main.login"

    if not app.debug and not app.testing:
        pass

    return app

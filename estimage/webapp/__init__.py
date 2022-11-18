from flask import Flask
from flask_login import LoginManager
from flask_bootstrap import Bootstrap5

login = LoginManager()


class Config:
    SECRET_KEY = "hulava"


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    from .main import bp as main_bp
    app.register_blueprint(main_bp)
    Bootstrap5(app)

    login.init_app(app)
    login.login_view = "main.login"

    if not app.debug and not app.testing:
        pass

    return app

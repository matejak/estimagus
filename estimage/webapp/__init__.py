from flask import Flask
from flask_login import LoginManager

login = LoginManager()


class Config:
    SECRET_KEY = "hulava"


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    from .main import bp as main_bp
    app.register_blueprint(main_bp)

    login.init_app(app)
    login.login_view = "main.login"

    if not app.debug and not app.testing:
        pass

    return app

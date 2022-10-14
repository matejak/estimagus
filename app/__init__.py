from flask import Flask

app = Flask(__name__)

app.config["SECRET_KEY"] = "hulava"

from app import routes
from flask import Blueprint

bp = Blueprint('login', __name__)

from . import routes


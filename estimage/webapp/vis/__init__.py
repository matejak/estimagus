from flask import Blueprint

bp = Blueprint('vis', __name__)

from . import routes


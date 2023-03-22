from flask import Blueprint

bp = Blueprint('persons', __name__)

from . import routes


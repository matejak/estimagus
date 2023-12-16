from flask import Blueprint

bp = Blueprint('neck', __name__)

from . import routes

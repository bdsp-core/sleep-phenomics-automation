from flask import Blueprint

viewer_bp = Blueprint('viewer', __name__, url_prefix='/viewer')

from . import routes



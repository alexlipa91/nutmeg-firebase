from flask import Blueprint
from flask import current_app as app


bp = Blueprint('sportcenters', __name__, url_prefix='/sportcenters')


@bp.route("", methods=["GET"])
def get_sportcenters():
    result = {}
    for s in app.db_client.collection('sport_centers').get():
        result[s.id] = s.to_dict()

    return {"data": result}, 200

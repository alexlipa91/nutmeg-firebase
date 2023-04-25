import os
import time

import flask
import requests
from flask import Blueprint
from flask import current_app as app

from locations import get_place_location_info


bp = Blueprint('sportcenters', __name__, url_prefix='/sportcenters')


@bp.route("", methods=["GET"])
def get_sportcenters():
    of_user = flask.request.args.get("user", None)
    result = {}

    if of_user:
        collection = app.db_client.collection("users").document(of_user).collection('sportCenters')
    else:
        collection = app.db_client.collection('sport_centers')

    for s in collection.get():
        result[s.id] = s.to_dict()

    return {"data": result}, 200


@bp.route("/<sportcenter_id>", methods=["GET"])
def get_sportcenter(sportcenter_id):
    sportcenter_data = app.db_client.collection('sport_centers').document(sportcenter_id).get().to_dict()
    if not sportcenter_data:
        return {}, 404
    return {"data": sportcenter_data}, 200


@bp.route("/add", methods=["POST"])
def add_sportcenter():
    data = flask.request.get_json()

    result = get_place_location_info(data["place_id"])

    sport_center = {
        "address": result["formatted_address"],
        "name": result["name"],
        "country": result["country"],
        "city": result["city"],
        "lat": result["lat"],
        "lng": result["lng"],
        "timeZoneId": _get_timezone_id(result["lat"], result["lng"])
    }
    for k in data:
        sport_center[k] = data[k]

    app.db_client.collection("users").document(flask.g.uid).collection("sportCenters") \
        .document(data["place_id"]).set(sport_center)

    return {}, 200


def _get_timezone_id(lat, lng):
    url = "https://maps.googleapis.com/maps/api/timezone/json?location={}%2C{}&timestamp={}&key={}".format(
        lat,
        lng,
        int(time.time()),
        os.environ["GOOGLE_MAPS_API_KEY"]
    )
    response = requests.request("GET", url, headers={}, data={})

    return response.json()["timeZoneId"]

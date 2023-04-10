import time

import flask
import requests
from flask import Blueprint
from flask import current_app as app

from utils import get_secret

bp = Blueprint('sportcenters', __name__, url_prefix='/sportcenters')


@bp.route("", methods=["GET"])
def get_sportcenters():
    result = {}
    for s in app.db_client.collection('sport_centers').get():
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
    print(data)

    url = "https://maps.googleapis.com/maps/api/place/details/json?place_id={}&fields={}&key={}".format(
        data["place_id"],
        "%2C".join(["name", "formatted_address", "geometry", "utc_offset", "address_components"]),
        get_secret("placesApiKey")
    )

    response = requests.request("GET", url, headers={}, data={})
    result = response.json()["result"]

    lat = result["geometry"]["location"]["lat"]
    lng = result["geometry"]["location"]["lng"]

    country = None
    for a in result["address_components"]:
        if "country" in a["types"]:
            country = a["short_name"]

    sport_center = {
        "address": result["formatted_address"],
        "name": result["name"],
        "country": country,
        "lat": lat,
        "lng": lng,
        "timeZoneId": _get_timezone_id(lat, lng)
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
        get_secret("placesApiKey")
    )
    response = requests.request("GET", url, headers={}, data={})

    return response.json()["timeZoneId"]

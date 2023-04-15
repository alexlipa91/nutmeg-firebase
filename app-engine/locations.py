import flask
import requests
from flask import Blueprint

from utils import get_secret

bp = Blueprint('locations', __name__, url_prefix='/locations')


@bp.route("/predictions", methods=["GET"])
def get_location_predictions_from_query():
    query = flask.request.args.get("query", None)
    country = flask.request.args.get("country",
                                     flask.request.headers.get('X-Appengine-Country'))

    if country is None or country == "ZZ":
        country = "NL"

    url = 'https://maps.googleapis.com/maps/api/place/autocomplete/json?'
    req = requests.get(url + 'input=' + query + '&key=' + get_secret("placesApiKey")
                       + '&components=country:{}'.format(country)
                       + '&fields=formatted_address')
    resp = req.json()

    results = resp['predictions']
    results_formatted = []

    for r in results:
        r_formatted = {}
        for k in ('description', 'matched_substrings', 'place_id'):
            r_formatted[k] = r[k]
        results_formatted.append(r_formatted)

    return {"data": {"predictions": results_formatted}}, 200


@bp.route("/cities", methods=["GET"])
def get_city_from_query():
    query = flask.request.args.get("query", None)

    url = 'https://maps.googleapis.com/maps/api/place/autocomplete/json?'
    req = requests.get(url + 'input=' + query + '&key=' + get_secret("placesApiKey")
                       + '&types=(cities)'
                       + '&fields=formatted_address')
    resp = req.json()

    results = resp['predictions']
    results_formatted = []

    for r in results:
        r_formatted = {}
        for k in ('description', 'matched_substrings', 'place_id'):
            r_formatted[k] = r[k]
        results_formatted.append(r_formatted)

    return {"data": {"predictions": results_formatted}}, 200


@bp.route("/cities", methods=["GET"])
def get_location_details():
    data = flask.request.get_json()

    lat = data["lat"]
    lng = data["lng"]
    url = "https://maps.googleapis.com/maps/api/geocode/json?"
    response = requests.get(url
                            + "latlng={},{}".format(lat, lng)
                            + "&key={}".format(get_secret("placesApiKey"))
                            + "&result_type=locality")
    results = response.json()["results"]

    address_components = results[0]["address_components"]

    result = {}

    for a in address_components:
        if "locality" in a["types"]:
            result["city"] = a["long_name"]
        elif "country" in a["types"]:
            result["country"] = a["short_name"]

    result["lat"] = results[0]["geometry"]["location"]["lat"]
    result["lng"] = results[0]["geometry"]["location"]["lng"]

    return result


def get_place_details(place_id):
    url = "https://maps.googleapis.com/maps/api/place/details/json?place_id={}&fields={}&key={}".format(
        place_id,
        "%2C".join(["name", "formatted_address", "geometry", "utc_offset", "address_components"]),
        get_secret("placesApiKey")
    )

    response = requests.request("GET", url, headers={}, data={})
    result = response.json()["result"]

    return result

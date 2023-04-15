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

import asyncio
import os
import time

import firebase_admin
import requests
from flask_cors import cross_origin
from google.cloud.firestore import AsyncClient
from firebase_admin import firestore


firebase_admin.initialize_app()


@cross_origin(origins=["*"], allow_headers=["firebase-instance-id-token", "content-type", "authorization"])
def get_sportcenter(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    request_data = request_json["data"]

    return {"data": asyncio.run(_get_sportcenter_firestore(request_data["id"]))}, 200


@cross_origin(origins=["*"], allow_headers=["firebase-instance-id-token", "content-type", "authorization"])
def get_user_sportcenters(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    request_data = request_json["data"]

    return {"data": asyncio.run(_get_user_sportcenters(request_data["user_id"]))}, 200


async def _get_sportcenter_firestore(sportcenter_id):
    db = AsyncClient()
    sport_center_data = (await db.collection('sport_centers').document(sportcenter_id).get()).to_dict()
    return sport_center_data


async def _get_user_sportcenters(user_id):
    db = AsyncClient()
    x = await db.collection('users').document(user_id).collection("sportCenters").get()
    result = {}
    for s in x:
        result[s.id] = s.to_dict()
    return result


@cross_origin(origins=["*"], allow_headers=["firebase-instance-id-token", "content-type", "authorization"])
def get_location_predictions_from_query(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    return {"data": {"predictions": _get_location_predictions_from_query(request_json["data"]["query"])}}, 200


def _get_location_predictions_from_query(query):
    url = 'https://maps.googleapis.com/maps/api/place/autocomplete/json?'
    req = requests.get(url + 'input=' + query + '&key=' + os.environ["GOOGLE_PLACES_API_KEY"]
                       + '&components=country:NL' + '&fields=formatted_address')
    resp = req.json()

    results = resp['predictions']
    results_formatted = []

    for r in results:
        r_formatted = {}
        for k in ('description', 'matched_substrings', 'place_id'):
            r_formatted[k] = r[k]
        results_formatted.append(r_formatted)

    return results_formatted


@cross_origin(origins=["*"], allow_headers=["firebase-instance-id-token", "content-type", "authorization"])
def get_placeid_info(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    return {"data": _get_placeid_info(request_json["data"]["place_id"])}, 200


@cross_origin(origins=["*"], allow_headers=["firebase-instance-id-token", "content-type", "authorization"])
def add_user_sportcenter(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    user_id = request_json["data"]["user_id"]
    sport_center = request_json["data"]["sport_center"]

    db = firestore.client()

    db.collection("users").document(user_id).collection("sportCenters")\
        .document(sport_center["placeId"]).set(sport_center)

    return {"data": {}}, 200


@cross_origin(origins=["*"], allow_headers=["firebase-instance-id-token", "content-type", "authorization"])
def add_user_sportcenter_from_place_id(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    _add_user_sportcenter_from_place_id(
        request_json["data"]["place_id"],
        request_json["data"]["additional_info"],
        request_json["data"]["user_id"],
    )

    return {"data": {}}, 200


def _add_user_sportcenter_from_place_id(place_id, additional_info, user_id):
    url = "https://maps.googleapis.com/maps/api/place/details/json?place_id={}&fields={}&key={}".format(
        place_id,
        "%2C".join(["name", "formatted_address", "geometry", "utc_offset"]),
        os.environ["GOOGLE_PLACES_API_KEY"]
    )

    response = requests.request("GET", url, headers={}, data={})
    result = response.json()["result"]

    lat = result["geometry"]["location"]["lat"]
    lng = result["geometry"]["location"]["lng"]

    sport_center = {
        "address": result["formatted_address"],
        "name": result["name"],
        "lat": lat,
        "lng": lng,
        "timeZonId": _get_timezone_id(lat, lng)
    }
    for k in additional_info:
        sport_center[k] = additional_info[k]

    db = firestore.client()

    db.collection("users").document(user_id).collection("sportCenters") \
        .document(place_id).set(sport_center)


def _get_timezone_id(lat, lng):
    url = "https://maps.googleapis.com/maps/api/timezone/json?location={}%2C{}&timestamp={}&key={}".format(
        lat,
        lng,
        int(time.time()),
        os.environ["GOOGLE_PLACES_API_KEY"]
    )
    response = requests.request("GET", url, headers={}, data={})

    return response.json()["timeZoneId"]


def _get_placeid_info(place_id):
    url = 'https://maps.googleapis.com/maps/api/place/details/json?'

    req = requests.get(url + 'place_id=' + place_id + '&key=' + os.environ["GOOGLE_PLACES_API_KEY"]
                       + "&fields=name%2Cformatted_address%2Cgeometry%2Cutc_offset")
    resp = req.json()

    return resp['result']


if __name__ == '__main__':
    _get_timezone_id(52.3695049302915,  4.926487980291501)
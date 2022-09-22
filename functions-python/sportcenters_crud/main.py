import asyncio
import os

import firebase_admin
import requests
from flask_cors import cross_origin
from google.cloud.firestore import AsyncClient


firebase_admin.initialize_app()


@cross_origin(origins=["*"], allow_headers=["firebase-instance-id-token", "content-type", "authorization"])
def get_sportcenter(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    request_data = request_json["data"]

    return {"data": asyncio.run(_get_sportcenter_firestore(request_data["id"]))}, 200


async def _get_sportcenter_firestore(sportcenter_id):
    db = AsyncClient()
    sport_center_data = (await db.collection('sport_centers').document(sportcenter_id).get()).to_dict()
    return sport_center_data


@cross_origin(origins=["*"], allow_headers=["firebase-instance-id-token", "content-type", "authorization"])
def get_location_predictions_from_query(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    return {"data": {"predictions": _get_location_predictions_from_query(request_json["data"]["query"])}}, 200


def _get_location_predictions_from_query(query):
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json?"

    req = requests.get(url + 'query=' + query + '&key=' + os.environ["GOOGLE_PLACES_API_KEY"] + '&region=nl')
    resp = req.json()

    results = resp['results']
    results_formatted = []

    for r in results:
        r_formatted = {}
        for k in ('name', 'formatted_address', 'geometry', 'place_id'):
            r_formatted[k] = r[k]
        results_formatted.append(r_formatted)

    return results_formatted

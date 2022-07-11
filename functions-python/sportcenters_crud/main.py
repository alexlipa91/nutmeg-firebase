import asyncio

import firebase_admin
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


if __name__ == '__main__':
    print(asyncio.run(_get_sportcenter_firestore("ChIJaaYbkP8JxkcR_lUNC3ssFuU")))

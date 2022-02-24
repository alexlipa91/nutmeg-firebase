import asyncio
import datetime

import firebase_admin
from google.cloud.firestore import AsyncClient

firebase_admin.initialize_app()


def get_match_v2(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    request_data = request_json["data"]

    return {"data": asyncio.run(_get_match_firestore_v2(request_data["id"]))}, 200


def get_all_matches_v2(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    return {"data": asyncio.run(_get_all_matches_firestore_v2())}, 200


async def _get_match_firestore_v2(match_id):
    db = AsyncClient()
    match_data = (await db.collection('matches').document(match_id).get()).to_dict()
    return await _format_match_data_v2(match_data)


async def _format_match_data_v2(match_data):
    # serialize date
    match_data["dateTime"] = _serialize_date(match_data["dateTime"])
    for u in match_data.get("going", []):
        match_data["going"][u]["createdAt"] = _serialize_date(match_data["going"][u]["createdAt"])
    return match_data


async def _get_all_matches_firestore_v2():
    db = AsyncClient()
    collection = await db.collection('matches').get()

    res = {}

    for m in collection:
        res[m.id] = await _format_match_data_v2(m.to_dict())

    return res


def _serialize_date(date):
    return datetime.datetime.isoformat(date)


if __name__ == '__main__':
    print(asyncio.run(_get_match_firestore_v2("3dD9fotUuuuGySkDhU5o")))

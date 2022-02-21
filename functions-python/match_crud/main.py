import asyncio
import datetime

import dateutil.parser
import firebase_admin
from firebase_admin import firestore
from google.cloud.firestore import AsyncClient

firebase_admin.initialize_app()


def add_match(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    request_data = request_json["data"]

    return {"data": {"id": _add_match_firestore(request_data)}}, 200


def edit_match(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    request_data = request_json["data"]

    _edit_match_firestore(request.args["id"], request_data["data"])
    return {"data": {}}, 200


def get_match(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    request_data = request_json["data"]

    return {"data": asyncio.run(_get_match_firestore(request_data["id"]))}, 200


def get_all_matches(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    return {"data": asyncio.run(_get_all_matches_firestore())}, 200


def _edit_match_firestore(match_id, match_data):
    db = firestore.client()

    doc_ref = db.collection("matches").document(match_id)
    if not doc_ref.get().exists:
        raise Exception("Match {} does not exists".format(match_id))

    doc_ref.update(match_data)


def _add_match_firestore(match_data):
    assert match_data.get("sportCenterId", None) is not None, "Required field missing"
    assert match_data.get("sport", None) is not None, "Required field missing"
    assert match_data.get("pricePerPerson", None) is not None, "Required field missing"
    assert match_data.get("maxPlayers", None) is not None, "Required field missing"
    assert match_data.get("dateTime", None) is not None, "Required field missing"
    assert match_data.get("duration", None) is not None, "Required field missing"

    match_data["dateTime"] = dateutil.parser.isoparse(match_data["dateTime"])

    db = firestore.client()

    doc_ref = db.collection('matches').document()
    doc_ref.set(match_data)
    return doc_ref.id


async def _get_match_firestore(match_id):
    db = AsyncClient()
    match_data = (await db.collection('matches').document(match_id).get()).to_dict()
    return await _format_match_data(match_data)


async def _format_match_data(match_data):
    # make it backward compatible, the client used to rely on user_id field being there; also going must be present
    if "going" not in match_data:
        match_data["going"] = {}
    else:
        for u in match_data["going"]:
            match_data["going"][u]["userId"] = u
            match_data["going"][u]["createdAt"] = _serialize_date(match_data["going"][u]["createdAt"])

    # serialize date
    match_data["dateTime"] = _serialize_date(match_data["dateTime"])
    return match_data


async def _get_all_matches_firestore():
    db = AsyncClient()
    collection = await db.collection('matches').get()

    res = {}

    for m in collection:
        res[m.id] = await _format_match_data(m.to_dict())

    return res


def _serialize_date(date):
    return datetime.datetime.isoformat(date)

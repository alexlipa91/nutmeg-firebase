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

    (match_data["going"], match_data["refunded"]) = await asyncio.gather(
        _read_subscriptions(match_id, "going"),
        _read_subscriptions(match_id, "refunded")
    )

    # serialize date
    match_data["dateTime"] = _serialize_date(match_data["dateTime"])
    return match_data


async def _read_subscriptions(match_id, field_name):
    db = AsyncClient()
    res = {}

    collection = await db.collection('matches/{}/{}'.format(match_id, field_name)).get()

    for sub in collection:
        sub_dict = sub.to_dict()
        sub_dict["createdAt"] = _serialize_date(sub_dict["createdAt"])
        res[sub.id] = sub_dict

    return res


async def _get_all_matches_firestore():
    db = AsyncClient()
    collection = await db.collection('matches').get()

    res = {}

    for c in collection:
        match_data = c.to_dict()
        (match_data["going"], match_data["refunded"]) = await asyncio.gather(
            _read_subscriptions(c.id, "going"),
            _read_subscriptions(c.id, "refunded")
        )

        # serialize date
        match_data["dateTime"] = _serialize_date(match_data["dateTime"])

        res[c.id] = match_data

    return res


def _serialize_date(date):
    return datetime.datetime.isoformat(date)

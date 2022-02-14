import datetime

import dateutil.parser
import firebase_admin
from firebase_admin import firestore

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

    resp = {"data": _get_match_firestore(request_data["id"])}
    print(type(resp))

    return {"data": _get_match_firestore(request_data["id"])}, 200


def get_all_matches(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    resp = {"data": _get_all_matches_firestore()}
    print(type(resp))

    return {"data": _get_all_matches_firestore()}, 200


def _edit_match_firestore(match_id, match_data):
    db = firestore.client()

    doc_ref = db.collection("matches").document(match_id)
    if not doc_ref.get().exists:
        raise Exception("Match {} does not exists".format(match_id))

    doc_ref.update(match_data)


def _add_match_firestore(match_data):
    assert "sportCenterId" in match_data, "Required field missing"
    assert "sport" in match_data, "Required field missing"
    assert "pricePerPerson" in match_data, "Required field missing"
    assert "maxPlayers" in match_data, "Required field missing"
    assert "dateTime" in match_data, "Required field missing"
    assert "duration" in match_data, "Required field missing"

    match_data["dateTime"] = dateutil.parser.isoparse(match_data["dateTime"])

    db = firestore.client()

    doc_ref = db.collection('matches').document()
    doc_ref.set(match_data)
    return doc_ref.id


def _get_match_firestore(match_id):
    db = firestore.client()

    match_data = db.collection('matches').document(match_id).get().to_dict()

    match_data["going"] = _read_subscriptions(match_id, "going")
    match_data["refunded"] = _read_subscriptions(match_id, "refunded")

    # serialize date
    match_data["dateTime"] = _serialize_date(match_data["dateTime"])

    return match_data


def _read_subscriptions(match_id, field_name):
    db = firestore.client()
    res = {}

    for sub in db.collection('matches').document(match_id).collection(field_name).stream():
        sub_dict = sub.to_dict()
        sub_dict["createdAt"] = _serialize_date(sub_dict["createdAt"])
        res[sub.id] = sub_dict

    return res


def _get_all_matches_firestore():
    res = {}

    for id in _get_matches_id_firestore():
        res[id] = _get_match_firestore(id)
    return res


def _get_matches_id_firestore():
    db = firestore.client()
    return [ds.id for ds in db.collection('matches').select({}).get()]


def _serialize_date(date):
    return datetime.datetime.isoformat(date)

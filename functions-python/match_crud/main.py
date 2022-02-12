import datetime
import json

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

    return {"data": _get_match_firestore(request_data["id"])}, 200


def get_all_matches(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

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

    match_data["going"] = {}
    going = db.collection('matches').document(match_id).collection("going").stream()
    for doc in going:
        match_data["going"][doc.id] = doc.to_dict()

    match_data["refunded"] = {}
    going = db.collection('matches').document(match_id).collection("refunded").stream()
    for doc in going:
        match_data["refunded"][doc.id] = doc.to_dict()

    return json.dumps(match_data, default=SerializationUtils.default)


def _get_all_matches_firestore():
    res = {}

    for id in _get_matches_id_firestore():
        res[id] = _get_match_firestore(id)
    return res


def _get_matches_id_firestore():
    db = firestore.client()
    return [ds.id for ds in db.collection('matches').select({}).get()]


class SerializationUtils:
    def default(obj):
        """Default JSON serializer."""
        if isinstance(obj, datetime.datetime):
            if obj.utcoffset() is not None:
                obj = obj - obj.utcoffset()
            return datetime.datetime.isoformat(obj)
        raise TypeError('Not sure how to serialize %s' % (obj,))


# if __name__ == '__main__':
#     print(dateutil.parser.isoparse("1969-07-20T20:18:04.000Z"))
# print(_add_match_firestore({'dateTime': "1969-07-20T20:18:04.000Z"}))
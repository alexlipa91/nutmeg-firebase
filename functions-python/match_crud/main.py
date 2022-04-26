import asyncio
import datetime
import os

import dateutil.parser
import firebase_admin
import stripe
from firebase_admin import firestore
from google.cloud.firestore import AsyncClient

firebase_admin.initialize_app()


def add_match(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    request_data = request_json["data"]

    is_test = request_data.get("isTest", False)
    organizer_id = request_data["organizerId"]

    match_id = _add_match_firestore(request_data)
    _update_user_account(organizer_id, is_test, match_id)

    return {"data": {"id": match_id}}, 200


def edit_match(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    request_data = request_json["data"]

    _edit_match_firestore(request_data["id"], request_data["data"])
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

    if "dateTime" in match_data:
        match_data["dateTime"] = dateutil.parser.isoparse(match_data["dateTime"])

    doc_ref.update(match_data)


def _add_match_firestore(match_data):
    assert match_data.get("sportCenterId", None) is not None, "Required field missing"
    assert match_data.get("sportInfo", None) is not None, "Required field missing"
    assert match_data.get("pricePerPerson", None) is not None, "Required field missing"
    assert match_data.get("maxPlayers", None) is not None, "Required field missing"
    assert match_data.get("dateTime", None) is not None, "Required field missing"
    assert match_data.get("duration", None) is not None, "Required field missing"

    match_data["dateTime"] = dateutil.parser.isoparse(match_data["dateTime"])

    # fixme changed name of the field
    if "sport" not in match_data:
        match_data["sport"] = "BvwIYDpu0f3RIT4EaWBH"

    # check if organizer can receive payments and if not do not publish yet
    db = firestore.client()
    organizer_data = db.collection('users').document(match_data["organizerId"]).get().to_dict()
    field_name = "chargesEnabledOnStripeTest" if match_data["isTest"] else "chargesEnabledOnStripe"

    if organizer_data.get(field_name, False):
        # add it as draft
        match_data["unpublished_reason"] = "organizer_not_onboarded"

    # add nutmeg fee to price
    match_data["pricePerPerson"] = match_data["pricePerPerson"] + 50

    db = firestore.client()

    doc_ref = db.collection('matches').document()
    doc_ref.set(match_data)
    return doc_ref.id


async def _get_match_firestore(match_id):
    db = AsyncClient()
    match_data = (await db.collection('matches').document(match_id).get()).to_dict()
    return await _format_match_data(match_data)


async def _format_match_data(match_data):
    # make it backward compatible, the client used to rely on user_id field being there; also going must be present and refunded :(
    if "going" not in match_data:
        match_data["going"] = {}
    else:
        for u in match_data["going"]:
            match_data["going"][u]["userId"] = u
            match_data["going"][u]["createdAt"] = _serialize_date(match_data["going"][u]["createdAt"])

    match_data["refunded"] = {}

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


def _update_user_account(user_id, is_test, match_id):
    stripe.api_key = os.environ["STRIPE_PROD_KEY" if not is_test else "STRIPE_TEST_KEY"]
    organizer_id_field_name = "stripeConnectedAccountId" if not is_test else "stripeConnectedAccountTestId"
    db = firestore.client()

    user_doc_ref = db.collection('users').document(user_id)

    user_data = user_doc_ref.get().to_dict()
    if organizer_id_field_name in user_data:
        print("{} already created".format(organizer_id_field_name))
        return user_data[organizer_id_field_name]

    response = stripe.Account.create(
        type="express",
        country="NL",
        capabilities={
            "transfers": {"requested": True},
        },
        business_type="individual",
        business_profile={
            "product_description": "Football matches organized on Nutmeg for user {}".format(user_id)
        },
        metadata={
            "userId": user_id
        }
    )

    # add organizer id and increase number of organized matches
    organised_list_field_name = "organised_matches" if not is_test else "organised_test_matches"
    user_doc_ref.update({
        organizer_id_field_name: response.id,
        "{}.{}".format(organised_list_field_name, match_id): firestore.firestore.SERVER_TIMESTAMP
    })
    return response.id


# def _add_match_with_user_firestore(user):
#     d = datetime.datetime.now() + datetime.timedelta(hours=2)
#     m = {}
#     m["sportCenterId"] = "ChIJ3zv5cYsJxkcRAr4WnAOlCT4"
#     m["sport"] = "BvwIYDpu0f3RIT4EaWBH"
#     m["pricePerPerson"] = 1000
#     m["maxPlayers"] = 10
#     m["dateTime"] = d.isoformat()
#     m["duration"] = 60
#     m["going"] = {user: {"createdAt": d.now()}}
#     return _add_match_firestore(m)

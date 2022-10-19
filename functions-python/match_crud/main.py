import asyncio
import datetime
import os

import dateutil.parser
import firebase_admin
import requests
import stripe
from firebase_admin import firestore
from flask_cors import cross_origin
from google.cloud.firestore import AsyncClient
from nutmeg_utils.schedule_function import schedule_function
from nutmeg_utils.firestore_utils import _serialize_dates

firebase_admin.initialize_app()
dbSync = firestore.client()
dbAsync = AsyncClient()


@cross_origin(origins=["*"], allow_headers=["firebase-instance-id-token", "content-type", "authorization"])
def add_match(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    request_data = request_json["data"]

    is_test = request_data.get("isTest", False)
    organizer_id = request_data["organizerId"]

    match_id = _add_match_firestore(request_data)
    _update_user_account(organizer_id, is_test, match_id)

    return {"data": {"id": match_id}}, 200


@cross_origin(origins=["*"], allow_headers=["firebase-instance-id-token", "content-type", "authorization"])
def edit_match(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    request_data = request_json["data"]

    _edit_match_firestore(request_data["id"], request_data["data"])
    return {"data": {}}, 200


@cross_origin(origins=["*"], allow_headers=["firebase-instance-id-token", "content-type", "authorization"])
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
    doc_ref = dbSync.collection("matches").document(match_id)
    if not doc_ref.get().exists:
        raise Exception("Match {} does not exists".format(match_id))

    match_data["dateTime"] = dateutil.parser.isoparse(match_data["dateTime"])

    doc_ref.update(match_data)


def _add_match_firestore(match_data):
    assert match_data.get("pricePerPerson", None) is not None, "Required field missing"
    assert match_data.get("maxPlayers", None) is not None, "Required field missing"
    assert match_data.get("dateTime", None) is not None, "Required field missing"
    assert match_data.get("duration", None) is not None, "Required field missing"

    match_data["dateTime"] = dateutil.parser.isoparse(match_data["dateTime"])

    # check if organizer can receive payments and if not do not publish yet
    organizer_data = dbSync.collection('users').document(match_data["organizerId"]).get().to_dict()
    field_name = "chargesEnabledOnStripeTest" if match_data["isTest"] else "chargesEnabledOnStripe"

    if not organizer_data.get(field_name, False):
        print("{} is False on organizer account: set match as unpublished".format(field_name))
        # add it as draft
        match_data["unpublished_reason"] = "organizer_not_onboarded"

    # add nutmeg fee to price
    # if not match_data.get("feeOnOrganiser", False):
    match_data["pricePerPerson"] = match_data["pricePerPerson"] + 50
    match_data["userFee"] = 50
    # else:
    #     match_data["organiserFee"] = 50

    db = firestore.client()

    doc_ref = db.collection('matches').document()
    doc_ref.set(match_data)

    # schedule cancellation check if required
    if "cancelHoursBefore" in match_data:
        cancellation_time = match_data["dateTime"] - datetime.timedelta(hours=match_data["cancelHoursBefore"])
        schedule_function(
            "cancel_or_confirm_match_{}".format(doc_ref.id),
            "cancel_or_confirm_match",
            {"match_id": doc_ref.id},
            cancellation_time
        )
        schedule_function(
            "send_pre_cancellation_organizer_notification_{}".format(doc_ref.id),
            "send_pre_cancellation_organizer_notification",
            {"match_id": doc_ref.id},
            cancellation_time - datetime.timedelta(hours=1)
        )

    return doc_ref.id


async def _get_match_firestore(match_id):
    match_data = (await dbAsync.collection('matches').document(match_id).get()).to_dict()
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
    collection = await dbAsync.collection('matches').get()

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

    # add to created matches
    user_doc_ref = db.collection('users').document(user_id)
    organised_list_field_name = "created_matches" if not is_test else "created_test_matches"
    user_updates = {
        "{}.{}".format(organised_list_field_name, match_id): firestore.firestore.SERVER_TIMESTAMP
    }

    # check if we need to create a stripe connected account
    user_data = user_doc_ref.get().to_dict()
    if organizer_id_field_name in user_data:
        print("{} already created".format(organizer_id_field_name))
        organizer_id = user_data[organizer_id_field_name]
    else:
        response = stripe.Account.create(
            type="express",
            country="NL",
            capabilities={
                "transfers": {"requested": True},
            },
            business_type="individual",
            business_profile={
                "product_description": "Nutmeg football matches"
            },
            metadata={
                "userId": user_id
            },
            settings={
                "payouts": {
                    "debit_negative_balances": True,
                    "schedule": {
                        "interval": "manual"
                    }
                }
            }
        )
        organizer_id = response.id
        user_updates[organizer_id_field_name] = response.id

    user_doc_ref.update(user_updates)

    return organizer_id


if __name__ == '__main__':
    for _ in range(0, 20):
        print(requests.get("https://europe-central2-nutmeg-9099c.cloudfunctions.net/get_all_matches").json())
"""
gcloud functions deploy create_stripe_product \
                         --runtime python37 \
                         --trigger-event "providers/cloud.firestore/eventTypes/document.create" \
                         --trigger-resource "projects/nutmeg-9099c/databases/(default)/documents/matches/{matchId}" \
                         --region europe-central2
"""
import os
from datetime import datetime

import pytz
import stripe

import firebase_admin
from firebase_admin import firestore

firebase_admin.initialize_app()


def create_stripe_product(data, context):
    print(data)
    trigger_resource = context.resource

    print('Function triggered by change to: %s' % trigger_resource)

    match_id = data["value"]["name"].split("/")[-1]
    is_test = data["value"]["fields"]["isTest"]["booleanValue"]

    date_time = datetime.strptime(data["value"]["fields"]["dateTime"]["timestampValue"], "%Y-%m-%dT%H:%M:%SZ")

    sport_center = _get_sport_center_details(data["value"]["fields"]["sportCenterId"]["stringValue"])

    product_id = _create_stripe_product("Nutmeg Match - "
                                        + sport_center["name"]
                                        + " - " + date_time.astimezone(pytz.timezone("Europe/Amsterdam")).strftime("%a %-d %b %H:%M"),
                                        sport_center["address"], is_test)
    price_id = _create_stripe_price(data["value"]["fields"]["pricePerPerson"]["integerValue"], product_id, is_test)
    _store_in_firebase(match_id, product_id, price_id)


def _get_sport_center_details(sport_center_id):
    db = firestore.client()
    return db.collection('sport_centers').document(sport_center_id).get().to_dict()


def _create_stripe_product(name, address, is_test):
    stripe.api_key = os.environ["STRIPE_PROD_KEY" if not is_test else "STRIPE_TEST_KEY"]

    response = stripe.Product.create(
        name=name,
        description="Address: " + address
    )
    return response["id"]


def _create_stripe_price(amount, prod_id, is_test):
    stripe.api_key = os.environ["STRIPE_PROD_KEY" if not is_test else "STRIPE_TEST_KEY"]

    response = stripe.Price.create(
        nickname='Standard Price',
        unit_amount=amount,
        currency="eur",
        product=prod_id
    )
    return response["id"]


def _store_in_firebase(match_id, product_id, price_id):
    db = firestore.client()

    db.collection('matches').document(match_id).update({
        'stripeProductId': product_id,
        'stripePriceId': price_id
    })




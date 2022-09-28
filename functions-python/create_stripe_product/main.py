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
    fields = data["value"]["fields"]
    is_test = fields["isTest"]["booleanValue"]

    date_time = datetime.strptime(fields["dateTime"]["timestampValue"], "%Y-%m-%dT%H:%M:%SZ")

    if "sportCenterId" in fields:
        sport_center = _get_sport_center_details(fields["sportCenterId"]["stringValue"])
        sport_center_name = sport_center["name"]
        sport_center_address = sport_center["address"]
    else:
        sport_center_fields = fields["sportCenter"]["mapValue"]["fields"]
        sport_center_address = sport_center_fields["address"]
        sport_center_name = sport_center_fields["name"]

    product_id = _create_stripe_product("Nutmeg Match - "
                                        + sport_center_name
                                        + " - " + date_time.astimezone(pytz.timezone("Europe/Amsterdam"))
                                        .strftime("%a %-d %b %H:%M"),
                                        sport_center_address, is_test)
    price_id = _create_stripe_price(fields["pricePerPerson"]["integerValue"], product_id, is_test)
    _store_in_firebase(match_id, product_id, price_id)


def update_stripe_product(data, context):
    print(data)
    trigger_resource = context.resource

    db = firestore.client()

    path_parts = trigger_resource.split('/documents/')[1].split('/')
    collection_path = path_parts[0]
    document_id = '/'.join(path_parts[1:])

    print('Function triggered by change to: %s' % trigger_resource)
    product_id = data["value"]["fields"]["stripeProductId"]["stringValue"]
    price_id = data["oldValue"]["fields"]["stripePriceId"]["stringValue"]

    old_is_test = data["oldValue"]["fields"]["isTest"]["booleanValue"]
    old_date_time = datetime.strptime(data["oldValue"]["fields"]["dateTime"]["timestampValue"], "%Y-%m-%dT%H:%M:%SZ")
    old_sport_center = _get_sport_center_details(data["oldValue"]["fields"]["sportCenterId"]["stringValue"])
    old_price = data["oldValue"]["fields"]["pricePerPerson"]["integerValue"]

    date_time = datetime.strptime(data["value"]["fields"]["dateTime"]["timestampValue"], "%Y-%m-%dT%H:%M:%SZ")
    sport_center = _get_sport_center_details(data["value"]["fields"]["sportCenterId"]["stringValue"])
    is_test = data["value"]["fields"]["isTest"]["booleanValue"]
    price = data["value"]["fields"]["pricePerPerson"]["integerValue"]

    if old_is_test != is_test:
        raise Exception("Cannot modify product since isTest value changed")

    stripe.api_key = os.environ["STRIPE_PROD_KEY" if not is_test else "STRIPE_TEST_KEY"]
    if old_date_time != date_time or old_sport_center != sport_center:
        name = "Nutmeg Match - " + sport_center["name"] \
           + " - " + date_time.astimezone(pytz.timezone("Europe/Amsterdam")).strftime("%a %-d %b %H:%M")
        description = "Address: " + sport_center["address"]
        print("setting name: '{}' and description: '{}'".format(name, description))

        stripe.Product.modify(product_id, name=name, description=description)
    else:
        print("no changed detected for stripe product")

    if old_price != price:
        print("deactivating old price and setting new price: {}".format(price))
        stripe.Price.modify(price_id, active=False)
        new_price_id = _create_stripe_price(price, prod_id=product_id, is_test=is_test)
        db.collection(collection_path).document(document_id).update({"stripePriceId": new_price_id})
    else:
        print("no changes detected for stripe price")


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




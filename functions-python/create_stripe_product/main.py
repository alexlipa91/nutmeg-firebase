"""
gcloud functions deploy create_stripe_product \
                         --runtime python37 \
                         --trigger-event "providers/cloud.firestore/eventTypes/document.create" \
                         --trigger-resource "projects/nutmeg-9099c/databases/(default)/documents/matches/{matchId}" \
                         --region europe-central2
"""
import stripe

import firebase_admin
from firebase_admin import firestore

firebase_admin.initialize_app()


def create_stripe_product(data, context):
    print(data)
    trigger_resource = context.resource

    print('Function triggered by change to: %s' % trigger_resource)

    match_id = data["value"]["name"].split("/")[-1]

    prod = _create_stripe_product("Nutmeg Match")
    price_id = _create_stripe_price(630, prod)
    _store_in_firebase(match_id, price_id)


def _create_stripe_product(name):
    stripe.api_key = "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"
        # os.environ["STRIPE_PROD_KEY"]

    response = stripe.Product.create(
        name=name
    )
    return response["id"]


def _create_stripe_price(amount, prod_id):
    stripe.api_key = "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"
    # os.environ["STRIPE_PROD_KEY"]

    response = stripe.Price.create(
        unit_amount=amount,
        currency="eur",
        product=prod_id
    )
    return response["id"]


def _store_in_firebase(match_id, price_id):
    db = firestore.client()

    db.collection('matches').document(match_id).update({
        'stripePriceId': price_id
    })


# if __name__ == '__main__':
#     prod = _create_stripe_product("Nutmeg Match")
#     price_id = _create_stripe_price(630, prod)
#     _store_in_firebase("crFHcsL52YvzXl0LFJ28", price_id)



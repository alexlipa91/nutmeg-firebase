"""
gcloud functions deploy create_stripe_customer \
                         --runtime python37 \
                         --trigger-event "providers/cloud.firestore/eventTypes/document.create" \
                         --trigger-resource "projects/nutmeg-9099c/databases/(default)/documents/users/{userId}" \
                         --region europe-central2
"""
import os

import stripe

import firebase_admin
from firebase_admin import firestore


firebase_admin.initialize_app()


def create_stripe_customer(data, context):
    print(data)
    trigger_resource = context.resource

    print('Function triggered by change to: %s' % trigger_resource)

    user_id = data["value"]["name"].split("/")[-1]
    user_data = data["value"]["fields"]

    db = firestore.client()

    name = user_data["name"].get("stringValue", None)
    email = user_data["email"].get("stringValue", None)

    db.collection('users').document(user_id).update({
        'stripeId': _create_stripe_customer(name, email)
    })


def _create_stripe_customer(name, email):
    stripe.api_key = os.environ["STRIPE_PROD_KEY"]

    response = stripe.Customer.create(
        email=email,
        name=name
    )
    return response["id"]



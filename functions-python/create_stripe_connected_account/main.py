import firebase_admin
from firebase_admin import firestore

import os
import stripe


firebase_admin.initialize_app()


def create_stripe_connected_account(request):
    request_json = request.get_json(silent=True)
    print("args {}, body {}".format(request.args, request_json))

    request_data = request_json["data"]

    user_id = request_data["user_id"]
    is_test = request_data["is_test"]

    _create_stripe_connected_account(user_id, is_test)

    data = {'data': {}}
    return data, 200


def _create_stripe_connected_account(user_id, is_test):
    stripe.api_key = os.environ["STRIPE_PROD_KEY" if not is_test else "STRIPE_TEST_KEY"]
    organizer_id_field_name = "stripeConnectedAccountId" if not is_test else "stripeConnectedAccountTestId"
    db = firestore.client()

    user_doc_ref = db.collection('users').document(user_id)

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
    print("Account created: {}". format(response.id))
    user_doc_ref.update({organizer_id_field_name: response.id})
    return response.id

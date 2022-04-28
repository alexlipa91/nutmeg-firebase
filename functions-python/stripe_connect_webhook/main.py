import os

import firebase_admin
import stripe
from firebase_admin import firestore
from google.cloud.firestore_v1 import DELETE_FIELD


firebase_admin.initialize_app()


def stripe_connect_updated_webhook_test(request):
    _exec(request, True)


def stripe_connect_updated_webhook(request):
    _exec(request, False)


def _exec(request, is_test):
    event = None
    payload = request.data
    sig_header = request.headers['STRIPE_SIGNATURE']

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, os.environ['STRIPE_WEBHOOK_SECRET'])
    except ValueError as e:
        # Invalid payload
        raise e
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        raise e

    event_data = event["data"]["object"]

    # Handle the event
    if event["type"] == "account.updated" and event_data["charges_enabled"]:
        user_id = event_data["metadata"]["userId"]
        field_name = "chargesEnabledOnStripe" if not is_test else "chargesEnabledOnStripeTest"

        db = firestore.client()
        user_data = db.collection("users").document(user_id).get().to_dict()

        if user_data.get(field_name, False):
            print("{} is already set for user {}".format(field_name, user_id))
            return

        db.collection("users").document(user_id).update({
            field_name: True
        })
        print("user {} can now receive payments on stripe".format(user_id))

        for m in user_data["created_matches" if not is_test else "created_test_matches"].keys():
            if db.collection("matches").document(m).get(field_paths=["unpublished_reason"]).to_dict()\
                    .get("unpublished_reason", None) == "organizer_not_onboarded":
                print("removing un-publishing blocker because of organizer from match {}".format(m))
                db.collection("matches").document(m).update({
                    'unpublished_reason': DELETE_FIELD,
                })
    else:
        print("event not handled")

    return {}, 200

import os

import stripe
from nutmeg_utils.functions_client import call_function


def stripe_checkout_webhook(request):
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

    is_test = event["livemode"].lower() == "false"
    event_data = event["data"]["object"]

    # Handle the event
    if event["type"] == "checkout.session.completed":
        print("checkout successful")
        call_function("add_user_to_match", {
            "match_id": event_data["metadata"]["match_id"],
            "user_id": event_data["metadata"]["user_id"],
            "payment_intent": event_data["payment_intent"]
        })
    else:
        print("checkout not successful")

    return {}, 200

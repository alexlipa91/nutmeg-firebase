import json

import stripe
import requests


def stripe_checkout_webhook_test(request):
    _exec(request, "whsec_fcxfBL6XriWegpXd9gJ5He40ouSSmRyK")


def stripe_checkout_webhook(request):
    _exec(request, "whsec_sdXI3JvzFXiTtTqChMWxiljMepY84Htp")


def _exec(request, secret):
    event = None
    payload = request.data
    sig_header = request.headers['STRIPE_SIGNATURE']

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, secret)
    except ValueError as e:
        # Invalid payload
        raise e
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        raise e

    print(event)
    event_data = event["data"]["object"]

    # Handle the event
    if event["type"] == "checkout.session.completed":
        print("checkout successful")
        _add_user_request(event_data["metadata"]["match_id"], event_data["metadata"]["user_id"],
                          event_data["payment_intent"])
    else:
        print("checkout not successful")

    return {}, 200


def _add_user_request(match_id, user_id, payment_intent):
    data = {
        "match_id": match_id,
        "user_id": user_id,
        "payment_intent": payment_intent
    }
    r = requests.post("https://europe-central2-nutmeg-9099c.cloudfunctions.net/add_user_to_match",
                      headers={"Content-Type": "application/json"},
                      data=json.dumps({'data': data}))

    if r.status_code != 200:
        raise Exception("Failed to add user when calling function. Reason: " + r.reason)

# if __name__ == '__main__':
#     _add_user_request("test_match_id", "IwrZWBFb4LZl3Kto1V3oUKPnCni1")

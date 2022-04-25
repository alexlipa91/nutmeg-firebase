import flask
import stripe

from nutmeg_utils.functions_client import call_function


def stripe_connect_updated_webhook_test(request):
    _exec(request, "whsec_fcxfBL6XriWegpXd9gJ5He40ouSSmRyK")


def stripe_connect_updated_webhook(request):
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
    # if event["type"] == "account.updated":
    #     print("checkout successful")
    #     call_function("add_user_to_match", {
    #         "match_id": event_data["metadata"]["match_id"],
    #         "user_id": event_data["metadata"]["user_id"],
    #         "payment_intent": event_data["payment_intent"]
    #     })
    # else:
    #     print("checkout not successful")
    #
    # return {}, 200
    return {}, 200


if __name__ == '__main__':
    app.run()

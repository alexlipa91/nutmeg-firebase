import firebase_admin
import stripe
from firebase_admin import firestore


firebase_admin.initialize_app()


def stripe_connect_updated_webhook_test(request):
    _exec(request, "whsec_KGzrAzxe6TUl0i4am32VLp2GhvbyvnUj", True)


def stripe_connect_updated_webhook(request):
    _exec(request, "whsec_jEdf6MDlKWoL3KDbTDOnjyy5Fbas02vp", False)


def _exec(request, secret, is_test):
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

    event_data = event["data"]["object"]

    # Handle the event
    if event["type"] == "account.updated" and event_data["charges_enabled"]:
        user_id = event_data["metadata"]["userId"]
        field_name = "chargesEnabledOnStripe" if not is_test else "chargesEnabledOnStripeTest"

        db = firestore.client()
        db.collection("users").document(user_id).update({
            field_name: True
        })
        print("user {} can now receive payments on stripe".format(user_id))
    else:
        print("event not handled")

    return {}, 200

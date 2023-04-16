import stripe
from flask import Blueprint

from matches import add_user_to_match
from utils import get_secret

bp = Blueprint('stripe', __name__, url_prefix='/stripe')


@bp.route("/checkout_webhook", methods=["GET"])
def stripe_checkout_webhook(request):
    _exec(request)


def stripe_checkout_webhook_test(request):
    _exec(request)


def _exec(request):
    event = None
    payload = request.data
    print(payload)
    sig_header = request.headers['STRIPE_SIGNATURE']

    secret = get_secret('stripeCheckoutWebhookSecret')

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
    if event["type"] == "checkout.session.completed":
        print("checkout successful")
        add_user_to_match(
            event_data["metadata"]["match_id"],
            event_data["metadata"]["user_id"],
            event_data["payment_intent"],
            local=True
        )
    else:
        print("checkout not successful")

    return {}

import flask

import stripe
from flask import Blueprint

from matches import add_user_to_match
from utils import get_secret

bp = Blueprint('stripe', __name__, url_prefix='/stripe')


@bp.route("/checkout_webhook", methods=["POST"])
def stripe_checkout_webhook():
    is_test = flask.request.args.get("test", "false") == "true"
    event = None
    sig_header = flask.request.headers['STRIPE_SIGNATURE']

    secret = get_secret('stripeCheckoutWebhookSecret' if not is_test else 'stripeCheckoutWebhookTestSecret')

    try:
        event = stripe.Webhook.construct_event(flask.request.data, sig_header, secret)
    except ValueError as e:
        # Invalid payload
        raise e
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        raise e

    event_data = event["data"]["object"]

    # Handle the event
    if event["type"] == "checkout.session.completed":
        add_user_to_match(
            event_data["metadata"]["match_id"],
            event_data["metadata"]["user_id"],
            event_data["payment_intent"],
            local=True
        )
    else:
        print("checkout not successful")

    return {}

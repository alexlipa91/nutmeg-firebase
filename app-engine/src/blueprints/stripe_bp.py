import os

import flask

import stripe
from flask import Blueprint
from flask import current_app as app
from google.cloud.firestore_v1 import DELETE_FIELD

from src.utils import build_dynamic_link
from src.blueprints.matches import add_user_to_match

bp = Blueprint('stripe', __name__, url_prefix='/stripe')


@bp.route("/checkout_webhook", methods=["POST"])
def stripe_checkout_webhook():
    is_test = flask.request.args.get("test", "false") == "true"
    sig_header = flask.request.headers['STRIPE_SIGNATURE']

    secret = os.environ["STRIPE_CHECKOUT_WEBHOOK_SECRET" if not is_test else "STRIPE_CHECKOUT_WEBHOOK_SECRET_TEST"]

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
        )
    else:
        print("checkout not successful")

    return {}


@bp.route("/account")
def go_to_account_login_link():
    is_test = flask.request.args["is_test"].lower() == "true"
    stripe.api_key = os.environ["STRIPE_KEY_TEST" if is_test else "STRIPE_KEY"]
    field_name = "stripeConnectedAccountId" if not is_test else "stripeConnectedAccountTestId"
    account_id = app.db_client.collection('users').document(
        flask.request.args.get("user_id", "Bthm3lwFfoai8MszdAIbzEHFXbC2")).get().to_dict()[field_name]

    response = stripe.Account.create_login_link(account_id)
    return flask.redirect(response.url)


@bp.route("/account/onboard")
def go_to_onboard_connected_account():
    is_test = flask.request.args["is_test"].lower() == "true"
    stripe.api_key = os.environ["STRIPE_KEY_TEST" if is_test else "STRIPE_KEY"]
    field_name = "stripeConnectedAccountId" if not is_test else "stripeConnectedAccountTestId"

    user_id = flask.request.args["user_id"]
    match_id = flask.request.args.get("match_id")

    account_id = app.db_client.collection('users').document(user_id).get().to_dict()[field_name]

    redirect_link_path = 'http://web.nutmegapp.com'
    if match_id:
        redirect_link_path = redirect_link_path + "/match/" + match_id
    else:
        redirect_link_path = redirect_link_path + "/user"

    redirect_link = build_dynamic_link(redirect_link_path)
    refresh_link = "https://nutmeg-9099c.ew.r.appspot.com/stripe/account/onboard?is_test={}&user_id={}"\
        .format(is_test, user_id)

    if match_id:
        refresh_link = refresh_link + "&match_id=" + match_id

    response = stripe.AccountLink.create(
        account=account_id,
        refresh_url=refresh_link,
        return_url=redirect_link,
        type="account_onboarding",
        collect="currently_due",
    )
    return flask.redirect(response.url)


@bp.route("/connect_account_updated_webhook", methods=["POST"])
def stripe_connect_account_updated_webhook():
    is_test = flask.request.args.get("test", "false") == "true"
    sig_header = flask.request.headers['STRIPE_SIGNATURE']

    secret = os.environ[
        "STRIPE_CONNECT_UPDATED_WEBHOOK_SECRET" if not is_test else "STRIPE_CONNECT_UPDATED_WEBHOOK_SECRET_TEST"]

    try:
        event = stripe.Webhook.construct_event(flask.request.data, sig_header, secret)
    except ValueError as e:
        # Invalid payload
        raise e
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        raise e

    is_test = not event["livemode"]
    event_data = event["data"]["object"]

    # Handle the event
    if event["type"] == "account.updated" and event_data["charges_enabled"]:
        user_id = event_data["metadata"]["userId"]

        user_data = app.db_client.collection("users").document(user_id).get().to_dict()

        field_name = "chargesEnabledOnStripe" if not is_test else "chargesEnabledOnStripeTest"
        app.db_client.collection("users").document(user_id).update({field_name: True})
        print("user {} can now receive payments on stripe".format(user_id))

        for m in user_data["created_matches" if not is_test else "created_test_matches"].keys():
            match = app.db_client.collection("matches").document(m).get(field_paths=["unpublished_reason"])

            if match.exists and match.to_dict().get("unpublished_reason", None) == "organizer_not_onboarded":
                print("removing un-publishing blocker because of organizer from match {}".format(m))
                app.db_client.collection("matches").document(m).update({
                    'unpublished_reason': DELETE_FIELD
                })
    else:
        print("event not handled")

    return {}

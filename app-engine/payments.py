import os

import flask
import stripe

from flask import Blueprint
from utils import build_dynamic_link
from flask import current_app as app

bp = Blueprint('payments', __name__, url_prefix='/payments')


@bp.route("/checkout", methods=["GET"])
def checkout():
    request = flask.request
    match_id = request.args["match_id"]
    user_id = request.args["user_id"]
    version = request.args.get("v", 1)

    match_info = _get_match_info(match_id)
    is_test = match_info.get("isTest", False)

    if version == 1:
        session = _create_checkout_redirects_to_web(
            _get_stripe_customer_id(user_id, is_test),
            _get_stripe_connected_account_id(match_info["organizerId"], is_test),
            user_id,
            match_info["organizerId"],
            match_id,
            match_info["stripePriceId"],
            50,
            is_test)
    else:
        session = _create_checkout_session_with_deep_links(
            _get_stripe_customer_id(user_id, is_test),
            _get_stripe_connected_account_id(match_info["organizerId"], is_test),
            user_id,
            match_info["organizerId"],
            match_id,
            match_info["stripePriceId"],
            50,
            is_test)

    return flask.redirect(session.url)


def _get_match_info(match_id):
    data = app.db_client.collection('matches').document(match_id).get().to_dict()
    return data


def _get_stripe_customer_id(user_id, test_mode):
    stripe.api_key = os.environ["STRIPE_KEY_TEST" if test_mode else "STRIPE_KEY"]

    doc = app.db_client.collection('users').document(user_id)

    data = doc.get(
        field_paths={"name", "email", "stripeId", "stripeTestId"}) \
        .to_dict()

    field_name = "stripeId" if not test_mode else "stripeTestId"

    if field_name not in data:
        print("missing " + field_name + " for user " + user_id + ". Creating it...")
        response = stripe.Customer.create(
            email=data["email"],
            name=data["name"]
        )
        stripe_id = response["id"]
        doc.update({field_name: stripe_id})
        return stripe_id

    return data[field_name]


def _get_stripe_connected_account_id(organizer_id, test_mode):
    doc = app.db_client.collection('users').document(organizer_id)

    data = doc.get(
        field_paths={"stripeConnectedAccountId", "stripeConnectedAccountTestId"}) \
        .to_dict()

    return data["stripeConnectedAccountId" if not test_mode else "stripeConnectedAccountTestId"]


# application_fee_amount includes stripe fees
def _create_checkout_redirects_to_web(customer_id, connected_account_id, user_id,
                                      organizer_id, match_id, price_id, application_fee_amount,
                                      test_mode):
    stripe.api_key = os.environ["STRIPE_KEY_TEST" if test_mode else "STRIPE_KEY"]

    session = stripe.checkout.Session.create(
        success_url="https://web.nutmegapp.com/match/{}?payment_outcome={}".format(match_id, "success"),
        cancel_url="https://web.nutmegapp.com/match/{}?payment_outcome={}".format(match_id, "cancel"),
        payment_method_types=["card", "ideal"],
        line_items=[
            {"price": price_id, "quantity": 1}
        ],
        payment_intent_data={
            'application_fee_amount': application_fee_amount,
            'transfer_data': {
                'destination': connected_account_id,
            },
            'metadata': {
                'user_id': user_id,
                'match_id': match_id
            }
        },
        mode="payment",
        customer=customer_id,
        metadata={"user_id": user_id, "match_id": match_id, "organizer_id": organizer_id}
    )
    return session


def _create_checkout_session_with_deep_links(customer_id, connected_account_id, user_id,
                                             organizer_id, match_id, price_id, application_fee_amount,
                                             test_mode):
    stripe.api_key = os.environ["STRIPE_KEY_TEST" if test_mode else "STRIPE_KEY"]

    session = stripe.checkout.Session.create(
        success_url=build_dynamic_link('http://web.nutmegapp.com/match/{}?payment_outcome={}'
                                       .format(match_id, "success")),
        cancel_url=build_dynamic_link('http://web.nutmegapp.com/match/{}?payment_outcome={}'
                                      .format(match_id, "cancel")),
        payment_method_types=["card", "ideal"],
        line_items=[
            {"price": price_id, "quantity": 1}
        ],
        payment_intent_data={
            'application_fee_amount': application_fee_amount,
            'transfer_data': {
                'destination': connected_account_id,
            },
            'metadata': {
                'user_id': user_id,
                'match_id': match_id
            }
        },
        mode="payment",
        customer=customer_id,
        metadata={"user_id": user_id, "match_id": match_id, "organizer_id": organizer_id}
    )
    return session

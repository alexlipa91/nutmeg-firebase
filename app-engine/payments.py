import flask
import stripe
from firebase_admin import firestore
from firebase_dynamic_links import DynamicLinks
from flask import Blueprint
from flask_cors import cross_origin
from utils import get_secret

bp = Blueprint('payments', __name__, url_prefix='/payments')

syncDb = firestore.client()


@bp.route("/checkout", methods=["GET"])
@cross_origin(origins=["*"], allow_headers=["firebase-instance-id-token", "content-type", "authorization"])
def checkout():
    request = flask.request
    match_id = request.args["match_id"]
    user_id = request.args["user_id"]

    match_info = _get_match_info(match_id)
    is_test = match_info.get("isTest", False)

    session = _create_checkout_session_with_destination_charges_v2(
        _get_stripe_customer_id(user_id, is_test),
        _get_stripe_connected_account_id(match_info["organizerId"], is_test),
        user_id,
        match_info["organizerId"],
        match_id,
        match_info["stripePriceId"],
        50,
        is_test)
    return flask.redirect(session.url)


@bp.route("/success", methods=["GET"])
def success():
    return 200, {}


def _get_match_info(match_id):
    data = syncDb.collection('matches').document(match_id).get().to_dict()
    return data


def _get_stripe_customer_id(user_id, test_mode):
    stripe.api_key = get_secret("stripeTestKey" if test_mode else "stripeProdKey")

    doc = syncDb.collection('users').document(user_id)

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
    doc = syncDb.collection('users').document(organizer_id)

    data = doc.get(
        field_paths={"stripeConnectedAccountId", "stripeConnectedAccountTestId"}) \
        .to_dict()

    return data["stripeConnectedAccountId" if not test_mode else "stripeConnectedAccountTestId"]


# application_fee_amount includes stripe fees
def _create_checkout_session_with_destination_charges_v2(customer_id, connected_account_id, user_id,
                                                         organizer_id, match_id, price_id, application_fee_amount,
                                                         test_mode):
    stripe.api_key = get_secret("stripeTestKey" if test_mode else "stripeProdKey")

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


def _build_redirect_to_app_link_v2(match_id, outcome, redirect_address):
    api_key = get_secret("dynamicLinkApiKey")
    domain = 'nutmegapp.page.link'
    dl = DynamicLinks(api_key, domain)
    params = {
        "androidInfo": {
            "androidPackageName": 'com.nutmeg.nutmeg',
            "androidMinPackageVersionCode": '1'
        },
        "iosInfo": {
            "iosBundleId": 'com.nutmeg.app',
            "iosAppStoreId": '1592985083',
        },
        "navigationInfo": {
            "enableForcedRedirect": True,
        }
    }

    if redirect_address and redirect_address[-1] == "/":
        redirect_address = redirect_address[:-1]

    link = '{}/match/{}?payment_outcome={}'.format(
        redirect_address if redirect_address else "http://web.nutmegapp.com", match_id, outcome)
    print(link)

    short_link = dl.generate_dynamic_link(link, True, params)
    return short_link

import firebase_admin
import flask
from firebase_admin import firestore

import os
import stripe

# gcloud functions deploy create_stripe_checkout --runtime python37 --trigger-http --allow-unauthenticated --region europe-central2
from firebase_dynamic_links import DynamicLinks

firebase_admin.initialize_app()


def go_to_stripe_checkout(request):
    request_json = request.get_json(silent=True)
    print("args {}, body {}".format(request.args, request_json))

    is_test = request.args["is_test"].lower() == "true"
    match_id = request.args["match_id"]
    user_id = request.args["user_id"]

    match_info = _get_match_info(match_id)

    session = _create_checkout_session_with_destination_charges(
        _get_stripe_customer_id(user_id, is_test),
        _get_stripe_connected_account_id(match_info["organizerId"], is_test),
        user_id,
        match_info["organizerId"],
        match_id,
        match_info["stripePriceId"],
        50,
        is_test)
    return flask.redirect(session.url)


def go_to_stripe_checkout_v2(request):
    request_json = request.get_json(silent=True)
    print("args {}, body {}".format(request.args, request_json))

    is_test = request.args["is_test"].lower() == "true"
    match_id = request.args["match_id"]
    user_id = request.args["user_id"]
    is_web = request.args.get("is_web", "false").lower() == "true"

    match_info = _get_match_info(match_id)

    if is_web:
        print("http referrer is " + request.environ["HTTP_REFERER"])
    session = _create_checkout_session_with_destination_charges_v2(
        _get_stripe_customer_id(user_id, is_test),
        _get_stripe_connected_account_id(match_info["organizerId"], is_test),
        user_id,
        match_info["organizerId"],
        match_id,
        match_info["stripePriceId"],
        50,
        request.environ["HTTP_REFERER"] if is_web else None,
        is_test)
    return flask.redirect(session.url)


def _get_match_info(match_id):
    db = firestore.client()

    data = db.collection('matches').document(match_id).get().to_dict()

    return data


def _get_stripe_customer_id(user_id, test_mode):
    db = firestore.client()
    stripe.api_key = os.environ["STRIPE_TEST_KEY" if test_mode else "STRIPE_PROD_KEY"]

    doc = db.collection('users').document(user_id)

    data = doc.get(
        field_paths={"name", "email", "stripeId", "stripeTestId"})\
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
    db = firestore.client()

    doc = db.collection('users').document(organizer_id)

    data = doc.get(
        field_paths={"stripeConnectedAccountId", "stripeConnectedAccountTestId"}) \
        .to_dict()

    return data["stripeConnectedAccountId" if not test_mode else "stripeConnectedAccountTestId"]


# application_fee_amount includes stripe fees
def _create_checkout_session_with_destination_charges(customer_id, connected_account_id, user_id,
                                                      organizer_id, match_id, price_id, application_fee_amount,
                                                      test_mode):
    stripe.api_key = os.environ["STRIPE_TEST_KEY" if test_mode else "STRIPE_PROD_KEY"]

    session = stripe.checkout.Session.create(
        success_url=_build_redirect_to_app_link(match_id, "success"),
        cancel_url=_build_redirect_to_app_link(match_id, "cancel"),

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


def _create_checkout_session_with_destination_charges_v2(customer_id, connected_account_id, user_id,
                                                         organizer_id, match_id, price_id, application_fee_amount,
                                                         redirect_address, test_mode):
    stripe.api_key = os.environ["STRIPE_TEST_KEY" if test_mode else "STRIPE_PROD_KEY"]

    session = stripe.checkout.Session.create(
        success_url=_build_redirect_to_app_link_v2(match_id, "success", redirect_address),
        cancel_url=_build_redirect_to_app_link_v2(match_id, "cancel", redirect_address),

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


def _build_redirect_to_app_link(match_id, outcome):
    api_key = 'AIzaSyAjyxMFOrglJXpK6QlzJR_Mh8hNH3NcGS0'
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
        }
    }
    short_link = dl.generate_dynamic_link('http://nutmegapp.com/payment?outcome={}&match_id={}'.format(outcome, match_id),
                                          True, params)
    return short_link


def _build_redirect_to_app_link_v2(match_id, outcome, redirect_address):
    api_key = 'AIzaSyAjyxMFOrglJXpK6QlzJR_Mh8hNH3NcGS0'
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
        }
    }

    if redirect_address[-1] == "/":
        redirect_address = redirect_address[:-1]

    link = '{}/match/{}?payment_outcome={}'.format(
        redirect_address if redirect_address else "http://nutmegapp.com", match_id, outcome)

    short_link = dl.generate_dynamic_link(link, True, params)
    return short_link

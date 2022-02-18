import firebase_admin
from firebase_admin import firestore

import os
import stripe

# gcloud functions deploy create_stripe_checkout --runtime python37 --trigger-http --allow-unauthenticated --region europe-central2
from firebase_dynamic_links import DynamicLinks

firebase_admin.initialize_app()


def create_stripe_checkout(request):
    request_json = request.get_json(silent=True)
    print("args {}, body {}".format(request.args, request_json))

    request_data = request_json["data"]

    test_mode = request_data["test_mode"]
    match_id = request_data["match_id"]
    user_id = request_data["user_id"]
    credits_used = request_data.get("credits_used", 0)

    stripe.api_key = os.environ["STRIPE_TEST_KEY" if test_mode else "STRIPE_PROD_KEY"]

    match_info = _get_match_info(match_id)

    session = _create_checkout_session(
        _get_stripe_customer_id(user_id, test_mode),
        user_id,
        match_id,
        match_info["pricePerPerson"],
        match_info["stripeProductId"],
        match_info["stripePriceId"],
        credits_used,
        test_mode)

    data = {'data': {'session_id': session.id, 'url': session.url}}
    return data, 200


def _get_match_info(match_id):
    db = firestore.client()

    data = db.collection('matches').document(match_id).get(
        field_paths={"pricePerPerson", "stripeProductId"}) \
        .to_dict()

    return data


def _get_stripe_customer_id(user_id, test_mode):
    db = firestore.client()

    data = db.collection('users').document(user_id).get(
        field_paths={"stripeId", "stripeTestId"})\
        .to_dict()

    return data["stripeTestId" if test_mode else "stripeId"]


def _create_checkout_session(customer_id, user_id, match_id, price_per_person, product_id, price_id, credits_used, test_mode):
    stripe.api_key = os.environ["STRIPE_TEST_KEY" if test_mode else "STRIPE_PROD_KEY"]

    if credits_used == 0:
        line_item = {
            "price": price_id,
        }
    else:
        line_item = {
            'price_data': {
                "unit_amount": price_per_person - credits_used,
                "product": product_id,
                "currency": "eur"
            },
        }
    line_item["quantity"] = 1

    session = stripe.checkout.Session.create(
        success_url=_build_redirect_to_app_link(match_id, "success"),
        cancel_url=_build_redirect_to_app_link(match_id, "cancel"),

        payment_method_types=["card", "ideal"],
        line_items=[line_item],
        mode="payment",
        customer=customer_id,
        metadata={"user_id": user_id, "match_id": match_id, "credits_used": 0}
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


# if __name__ == '__main__':
#     print(_create_checkout_session("cus_L69uzD5yMZXVAn", "IwrZWBFb4LZl3Kto1V3oUKPnCni1",
#                              "0fn2zd8IjTDgoYtC1C6Z", 100, "prod_LAsIddc0zISbSd",
#                              "price_1KUWXsGRb87bTNwHkctOMs7l", 0, True))



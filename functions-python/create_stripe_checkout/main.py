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

    price_id = request_data["price_id"]
    test_mode = request_data["test_mode"]
    match_id = request_data["match_id"]
    user_id = request_data["user_id"]

    stripe.api_key = os.environ["STRIPE_TEST_KEY" if test_mode else "STRIPE_PROD_KEY"]

    session = _create_checkout_session(_get_stripe_customer_id(user_id, test_mode),
                                       user_id, match_id, price_id, test_mode)
    data = {'data': {'session_id': session.id, 'url': session.url}}
    return data, 200


def _get_stripe_customer_id(user_id, test_mode):
    db = firestore.client()

    data = db.collection('users').document(user_id).get(
        field_paths={"stripeId", "stripeTestId"})\
        .to_dict()

    return data["stripeTestId" if test_mode else "stripeId"]


def _create_checkout_session(customer_id, user_id, match_id, price_id, test_mode):
    stripe.api_key = os.environ["STRIPE_TEST_KEY" if test_mode else "STRIPE_PROD_KEY"]
    # "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"

    session = stripe.checkout.Session.create(
        success_url=_build_redirect_to_app_link(match_id),
        cancel_url="https://www.google.com",

        payment_method_types=["card", "ideal"],
        line_items=[
            {
                "price": price_id,
                "quantity": 1
            }
        ],
        mode="payment",
        customer=customer_id,
        # discounts=[{
        #     "coupon": "cZLa83ZZ"
        # }],
        # allow_promotion_codes=True,
        metadata={"user_id": user_id, "match_id": match_id}
    )
    return session


def _build_redirect_to_app_link(match_id):
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
    short_link = dl.generate_dynamic_link('http://nutmegapp.com/payment?outcome=success&match_id={}'.format(match_id),
                                          True, params)
    return short_link


if __name__ == '__main__':
    print(_build_redirect_to_app_link("test_match_id"))
    # cus = _get_stripe_customer_id("IwrZWBFb4LZl3Kto1V3oUKPnCni1", False)
    # print(_create_checkout_session(cus, "", "test_match_id", "price_1KRPNeGRb87bTNwH991CaYMa", False))


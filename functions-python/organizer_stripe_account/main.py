import os

import stripe

import firebase_admin
from firebase_admin import firestore

firebase_admin.initialize_app()


def create_stripe_connected_account(request):
    request_json = request.get_json(silent=True)
    print("data {}".format(request_json))

    request_data = request_json["data"]

    user_id = request_data["user_id"]
    is_test = request_data["is_test"]

    account_id = _create_stripe_connected_account(user_id, is_test=is_test)

    return {"data": {"account_id": account_id}}, 200


def _create_stripe_connected_account(user_id, is_test):
    stripe.api_key = os.environ["STRIPE_PROD_KEY" if not is_test else "STRIPE_TEST_KEY"]

    response = stripe.Account.create(
        type="custom",
        country="NL",
        capabilities={
            "transfers": {"requested": True},
        },
        business_type="individual",
        business_profile={
            "product_description": "Football matches organized on Nutmeg for user {}".format(user_id)
        },
        metadata={
            "userId": user_id
        }
    )

    db = firestore.client()
    field_name = "stripeConnectedAccountId" if not is_test else "stripeConnectedAccountTestId"
    db.collection('users').document(user_id).update({
        field_name: response.id
    })
    return response.id


def onboard_account(request):
    request_json = request.get_json(silent=True)
    print("data {}".format(request_json))

    request_data = request_json["data"]

    account_id = request_data["account_id"]
    is_test = request_data["is_test"]

    url = _onboard_account(account_id, is_test=is_test)

    return {"data": {"url": url}}, 200


def _onboard_account(stripe_account_id, is_test=False):
    stripe.api_key = os.environ["STRIPE_PROD_KEY" if not is_test else "STRIPE_TEST_KEY"]

    response = stripe.AccountLink.create(
        account=stripe_account_id,
        # todo add redirects
        refresh_url="https://example.com/reauth",
        return_url="https://example.com/return",
        type="account_onboarding",
        collect="currently_due",
    )
    return response.url


# if __name__ == '__main__':
    # print(_create_stripe_connected_account("IwrZWBFb4LZl3Kto1V3oUKPnCni1", is_test=True))
    # print(_onboard_account("acct_1Kh9wQ2fjkOIw12U", is_test=True))



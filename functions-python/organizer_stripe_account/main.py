import os

import flask
import stripe

import firebase_admin
from firebase_admin import firestore
from firebase_dynamic_links import DynamicLinks

firebase_admin.initialize_app()


def is_account_onboarded(request):
    request_json = request.get_json(silent=True)
    print("data {}".format(request_json))
    request_data = request_json["data"]

    user_id = request_data["user_id"]
    is_test = request_data["is_test"]

    account_id = _get_account_id(user_id, is_test)
    is_complete = _is_account_complete(account_id, is_test)

    return {"data": {"is_complete": is_complete}}, 200


def go_to_onboard_connected_account(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    is_test = request.args["is_test"].lower() == "true"
    user_id = request.args["id"]

    account_id = _get_account_id(user_id, is_test=is_test)
    return flask.redirect(_onboard_account_url(account_id, user_id, is_test=is_test))


def go_to_account_login_link(request):
    print("args {}".format(request.args))

    is_test = request.args["is_test"].lower() == "true"
    stripe.api_key = os.environ["STRIPE_PROD_KEY" if not is_test else "STRIPE_TEST_KEY"]
    response = stripe.Account.create_login_link(_get_account_id(request.args["user_id"], is_test))
    print("redirecting to {}".format(response.url))

    return flask.redirect(response.url)


def _get_account_id(user_id, is_test):
    db = firestore.client()
    field_name = "stripeConnectedAccountId" if not is_test else "stripeConnectedAccountTestId"
    return db.collection('users').document(user_id).get().to_dict()[field_name]


def _is_account_complete(account_id, is_test):
    stripe.api_key = os.environ["STRIPE_PROD_KEY" if not is_test else "STRIPE_TEST_KEY"]
    return len(stripe.Account.retrieve(account_id)["requirements"]["currently_due"]) == 0


def _onboard_account_url(stripe_account_id, user_id, is_test=False):
    stripe.api_key = os.environ["STRIPE_PROD_KEY" if not is_test else "STRIPE_TEST_KEY"]

    redirect_link = _build_redirect_to_app_link()
    refresh_link = "https://europe-central2-nutmeg-9099c.cloudfunctions.net/refresh_onboard_url?is_test={}&id={}"\
        .format(is_test, user_id)

    response = stripe.AccountLink.create(
        account=stripe_account_id,
        # fixme add a proper refresh url
        refresh_url=refresh_link,
        return_url=redirect_link,
        type="account_onboarding",
        collect="currently_due",
    )
    return response.url


def _build_redirect_to_app_link():
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
    short_link = dl.generate_dynamic_link('https://nutmegapp.com/onboardOrganizer',
                                          True, params)
    return short_link


def _create_transfer_for_payment(payment_id, fee, connect_account_id, match_id, is_test):
    stripe.api_key = os.environ["STRIPE_PROD_KEY" if not is_test else "STRIPE_TEST_KEY"]
    payment = stripe.PaymentIntent.retrieve(payment_id)
    charge = payment["charges"]["data"][0]["id"]
    amount = payment["amount"]

    transfer = stripe.Transfer.create(
        source_transaction=charge,
        amount=amount - fee,
        currency="eur",
        destination=connect_account_id,
        transfer_group=match_id,
    )
    return transfer.id


if __name__ == '__main__':
    stripe.api_key = os.environ["STRIPE_PROD_KEY" if not True else "STRIPE_TEST_KEY"]
    # acc = stripe.Account.retrieve("acct_1KsVKiGfLz0eleaC")
    # print(acc)
    # print(_create_stripe_connected_account("IwrZWBFb4LZl3Kto1V3oUKPnCni1", is_test=True))
    # print(_onboard_account_url("acct_1Kh9wQ2fjkOIw12U", is_test=True))
    #
    # print(stripe.Account.create_login_link("acct_1KsZKNGfOYri6GmK"))

    # response = stripe.AccountLink.create(
    #     account="acct_1KsahYGbk3pXbt2E",
    #     fixme add a proper refresh url
        # refresh_url="https://www.google.com",
        # return_url="https://www.google.com",
        # type="account_onboarding",
        # collect="currently_due",
    # )
    # print(response)
    # )
    # print(response.url)
    go_to_account_login_link("IwrZWBFb4LZl3Kto1V3oUKPnCni1")


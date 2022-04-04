import os

import stripe

import firebase_admin
from firebase_admin import firestore
from firebase_dynamic_links import DynamicLinks

firebase_admin.initialize_app()


def onboard_account(request):
    request_json = request.get_json(silent=True)
    print("data {}".format(request_json))
    request_data = request_json["data"]

    user_id = request_data["user_id"]
    is_test = request_data["is_test"]

    account_id = _get_account_id(user_id, is_test)
    are_charges_enabled = _is_account_complete(account_id, is_test)

    if are_charges_enabled:
        data = {"enabled": True}
    else:
        url = _onboard_account(account_id, is_test=is_test)
        data = {"enabled": False, "url": url}

    return {"data": data}, 200


def _get_account_id(user_id, is_test):
    db = firestore.client()
    field_name = "stripeConnectedAccountId" if not is_test else "stripeConnectedAccountTestId"
    return db.collection('users').document(user_id).get().to_dict()[field_name]


def _is_account_complete(account_id, is_test):
    stripe.api_key = os.environ["STRIPE_PROD_KEY" if not is_test else "STRIPE_TEST_KEY"]
    return len(stripe.Account.retrieve(account_id)["requirements"]["currently_due"]) == 0


def _onboard_account(stripe_account_id, is_test=False):
    stripe.api_key = os.environ["STRIPE_PROD_KEY" if not is_test else "STRIPE_TEST_KEY"]

    redirect_link = _build_redirect_to_app_link()

    response = stripe.AccountLink.create(
        account=stripe_account_id,
        refresh_url=redirect_link,
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
    short_link = dl.generate_dynamic_link('https://nutmegapp.com/somewhere',
                                          True, params)
    return short_link



# if __name__ == '__main__':
    # print(_create_stripe_connected_account("IwrZWBFb4LZl3Kto1V3oUKPnCni1", is_test=True))
    # print(_onboard_account("acct_1Kh9wQ2fjkOIw12U", is_test=True))



import firebase_admin
from firebase_admin import firestore
from firebase_dynamic_links import DynamicLinks

firebase_admin.initialize_app()


def create_match_link(data, context):
    print(data)
    trigger_resource = context.resource

    print('Function triggered by change to: %s' % trigger_resource)

    match_id = data["value"]["name"].split("/")[-1]

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
        },
        "navigationInfo": {
            "enableForcedRedirect": True,
        }
    }

    link = 'http://web.nutmegapp.com/match/{}'.format(match_id)

    short_link = dl.generate_dynamic_link(link, True, params)

    db = firestore.client()
    db.collection('matches').document(match_id).update({
        'dynamicLink': short_link
    })



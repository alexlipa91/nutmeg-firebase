import os

import stripe
from google.cloud import tasks_v2

"""
gcloud functions deploy clean_up_match \
                         --runtime python37 \
                         --trigger-event "providers/cloud.firestore/eventTypes/document.delete" \
                         --trigger-resource "projects/nutmeg-9099c/databases/(default)/documents/matches/{matchId}" \
                         --region europe-central2
"""
def clean_up_match(data, context):
    trigger_resource = context.resource
    print('Function triggered by change to: %s' % trigger_resource)
    print(data)

    match_id = data["oldValue"]["name"].split("/")[-1]

    product_id = data["oldValue"]["fields"]["stripeProductId"]["stringValue"]
    is_test = data["oldValue"]["fields"]["isTest"]["booleanValue"]

    _clean_up_match(match_id, product_id, is_test)


def _clean_up_match(match_id, stripe_product_id, is_test):
    for t in ["close_rating_round_", "send_prematch_notification_for_"]:
        _delete_task(t + match_id)

    stripe.api_key = os.environ["STRIPE_PROD_KEY" if not is_test else "STRIPE_TEST_KEY"]
    stripe.Product.delete(stripe_product_id)


def _delete_task(task_name):
    client = tasks_v2.CloudTasksClient()

    project = 'nutmeg-9099c'
    queue = 'match-notifications'
    location = 'europe-west1'

    task_path = client.task_path(project, location, queue, task_name)
    client.delete_task(name=task_path)


# if __name__ == '__main__':
#     _delete_task("abc_ZAEd7UF1ULPJyruQdUEi")
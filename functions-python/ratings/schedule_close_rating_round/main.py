from datetime import datetime, timedelta
from nutmeg_utils.schedule_function import schedule_function

"""
gcloud functions deploy schedule_close_rating_round \
                         --runtime python37 \
                         --trigger-event "providers/cloud.firestore/eventTypes/document.create" \
                         --trigger-resource "projects/nutmeg-9099c/databases/(default)/documents/matches/{matchId}" \
                         --region europe-central2
"""
def schedule_close_rating_round(data, context):
    trigger_resource = context.resource
    print('Function triggered by change to: %s' % trigger_resource)

    match_id = data["value"]["name"].split("/")[-1]
    date_time = datetime.strptime(data["value"]["fields"]["dateTime"]["timestampValue"], "%Y-%m-%dT%H:%M:%SZ")
    duration = int(data["value"]["fields"]["duration"]["integerValue"])

    schedule_function(
        task_name="close_rating_round_{}".format(match_id),
        function_name="close_rating_round",
        function_payload={"match_id": match_id},
        date_time_to_execute=date_time + timedelta(minutes=duration) + timedelta(days=1),
    )

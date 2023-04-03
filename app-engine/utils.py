from datetime import datetime

import google.api_core.datetime_helpers
from google.cloud import secretmanager


def _serialize_dates(data):
    for k in data:
        if type(data[k]) == dict:
            data[k] = _serialize_dates(data[k])
        elif type(data[k]) == google.api_core.datetime_helpers.DatetimeWithNanoseconds:
            data[k] = datetime.isoformat(data[k])
    return data


secretManagerClient = secretmanager.SecretManagerServiceClient()


def get_secret(name):
    return secretManagerClient.access_secret_version(
        request={"name": "projects/956073807168/secrets/{}/versions/latest".format(name)}
    ).payload.data.decode('utf-8')

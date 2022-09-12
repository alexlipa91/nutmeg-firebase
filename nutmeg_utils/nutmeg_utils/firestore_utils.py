from datetime import datetime

import google.api_core.datetime_helpers


def _serialize_dates(data):
    for k in data:
        if type(data[k] == dict):
            data[k] = _serialize_dates(data[k])
        elif type(data[k]) == google.api_core.datetime_helpers.DatetimeWithNanoseconds:
            data[k] = datetime.isoformat(data[k])
    return data

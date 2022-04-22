import json
import requests


def call_function(name, params):
    r = requests.post("https://europe-central2-nutmeg-9099c.cloudfunctions.net/{}".format(name),
                      headers={"Content-Type": "application/json"},
                      data=json.dumps({'data': params}))

    if r.status_code != 200:
        raise Exception("Function '{}' with params '{}' failed. Reason: {}".format(name, params, r.reason))
    return r.json()["data"]

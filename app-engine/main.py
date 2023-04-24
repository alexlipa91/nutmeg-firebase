import os

import firebase_admin
import flask
from firebase_admin import firestore, auth
from flask import request
from flask_cors import CORS

import feedback
import matches
import payments
import sportcenters
import locations
import stats
import stripe_bp
import users


# If `entrypoint` is not defined in app.yaml, App Engine will look for an app
# called `app` in `main.py`.
app = flask.Flask(__name__)

firebase_admin.initialize_app()
app.db_client = firestore.client()

app.register_blueprint(matches.bp)
app.register_blueprint(payments.bp)
app.register_blueprint(users.bp)
app.register_blueprint(sportcenters.bp)
app.register_blueprint(stats.bp)
app.register_blueprint(locations.bp)
app.register_blueprint(stripe_bp.bp)
app.register_blueprint(feedback.bp)


CORS(app)


@app.before_request
def before_request_callback():
    if "Authorization" in request.headers:
        decoded_token = auth.verify_id_token(request.headers["Authorization"].split(" ")[1])
        flask.g.uid = decoded_token['uid']
    else:
        flask.g.uid = None


@app.route("/routes", methods=["GET"])
def routes():
    return ['%s' % rule for rule in app.url_map.iter_rules()], 200


@app.route("/_ah/warmup", methods=["GET"])
def warmup():
    return {}, 200


if __name__ == "__main__":
    # Used when running locally only. When deploying to Google App
    # Engine, a webserver process such as Gunicorn will serve the app. This
    # can be configured by adding an `entrypoint` to app.yaml.
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/Users/alessandrolipa/IdeaProjects/nutmeg-firebase/nutmeg-9099c-bf73c9d6b62a.json"
    app.run(host="localhost", port=8080, debug=True)

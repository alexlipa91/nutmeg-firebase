import firebase_admin
import flask
from flask import request
from flask_cors import CORS

# this needs to happen before blueprint imports
firebase_admin.initialize_app()

import matches
import payments
import users


# If `entrypoint` is not defined in app.yaml, App Engine will look for an app
# called `app` in `main.py`.
app = flask.Flask(__name__)
app.register_blueprint(matches.bp)
app.register_blueprint(payments.bp)
app.register_blueprint(users.bp)

CORS(app)


@app.before_request
def after_request_callback():
    path = request.path
    method = request.method
    args = request.args

    log = "{} [{}] - args: {}".format(path, method, args)

    if method == "POST":
        log = log + " body: {}".format(request.get_json())

    print(log)


if __name__ == "__main__":
    # Used when running locally only. When deploying to Google App
    # Engine, a webserver process such as Gunicorn will serve the app. This
    # can be configured by adding an `entrypoint` to app.yaml.
    app.run(host="localhost", port=8080, debug=True)

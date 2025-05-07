import json
import logging

import flask
import google.cloud.logging
from firebase_admin import auth
from flask import request
from flask_cors import CORS
from google.cloud.logging.handlers import CloudLoggingHandler
import os
from src.blueprints import (
    feedback,
    stats,
    sportcenters,
    locations,
    users,
    stripe_bp,
    matches,
    payments,
    leaderboard,
)


class UserIdFilter(logging.Filter):
    def filter(self, record):
        # Add user_id as a custom attribute for structured logging
        record.user_id = getattr(flask.g, "uid", "anonymous")
        return True


def _setup_logging():
    client = google.cloud.logging.Client()
    handler = CloudLoggingHandler(client)
    handler.addFilter(UserIdFilter())
    logging.getLogger().setLevel(logging.INFO)
    logging.getLogger().addHandler(handler)


def _create_app(db, log_to_gcloud=True):
    app = flask.Flask(__name__)

    logging.info(
        "Starting app GAE_INSTANCE: {}, GAE_VERSION: {}".format(
            os.environ.get("GAE_INSTANCE", "unknown"),
            os.environ.get("GAE_VERSION", "unknown"),
        )
    )
    app.db_client = db

    app.register_blueprint(matches.bp)
    app.register_blueprint(matches.bp_v2)
    app.register_blueprint(payments.bp)
    app.register_blueprint(users.bp)
    app.register_blueprint(sportcenters.bp)
    app.register_blueprint(stats.bp)
    app.register_blueprint(locations.bp)
    app.register_blueprint(stripe_bp.bp)
    app.register_blueprint(feedback.bp)
    app.register_blueprint(leaderboard.bp)

    if log_to_gcloud:
        _setup_logging()

    CORS(app)

    @app.before_request
    def before_request_callback():
        if "Authorization" in request.headers:
            decoded_token = auth.verify_id_token(
                request.headers["Authorization"].split(" ")[1]
            )
            flask.g.uid = decoded_token["uid"]
        else:
            flask.g.uid = None

        structured_log = {
            "client-version": "{}".format(
                request.headers.get("App-Version", "unknown")
            ),
            "user-id": flask.g.uid,
        }
        if "X-Cloud-Trace-Context" in request.headers:
            structured_log["logging.googleapis.com/trace"] = request.headers[
                "X-Cloud-Trace-Context"
            ]
        logging.info(json.dumps(structured_log))

    @app.route("/routes", methods=["GET"])
    def routes():
        return ["%s" % rule for rule in app.url_map.iter_rules()], 200

    @app.route("/_ah/warmup", methods=["GET"])
    def warmup():
        return {}, 200

    return app

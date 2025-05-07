import json
import logging
import sys

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
from google.cloud.logging_v2.handlers import StructuredLogHandler


class UserIdFilter(logging.Filter):
    def filter(self, record):
        # Add user_id as a custom attribute for structured logging
        record.user_id = getattr(flask.g, "uid", "anonymous")
        return True


def _create_app(db):
    app = flask.Flask(__name__)
    
    # Setup basic logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger()
    # Replace default handler with structured one
    handler = StructuredLogHandler()
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)

    logging.info("Starting app")
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

    @app.route("/routes", methods=["GET"])
    def routes():
        return ["%s" % rule for rule in app.url_map.iter_rules()], 200

    @app.route("/_ah/warmup", methods=["GET"])
    def warmup():
        return {}, 200

    return app

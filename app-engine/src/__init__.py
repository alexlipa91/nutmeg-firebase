import base64
import logging
from firebase_admin import firestore

import flask
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


def _create_app():
    logging.info("Starting app")

    app: flask.Flask = flask.Flask(__name__)
    db: firestore.client = firestore.client()
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

        if request.method == "POST":
            try:
                body = request.get_data()
                if body:
                    encoded = base64.b64encode(body).decode("utf-8")
                    logging.info(f"Request body (base64): {encoded}, userId: {flask.g.uid}, path: {request.path}")
            except Exception as e:
                logging.error(f"Error logging request body: {e}")

    @app.route("/routes", methods=["GET"])
    def routes():
        return ["%s" % rule for rule in app.url_map.iter_rules()], 200

    @app.route("/_ah/warmup", methods=["GET"])
    def warmup():
        return {}, 200

    return app

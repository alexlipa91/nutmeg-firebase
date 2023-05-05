import flask
from firebase_admin import auth
from flask import request
from flask_cors import CORS

from src.blueprints import feedback, stats, sportcenters, locations, users, stripe_bp, matches, payments


def _create_app(db):
    app = flask.Flask(__name__)

    print("initializing")
    app.db_client = db

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

    return app

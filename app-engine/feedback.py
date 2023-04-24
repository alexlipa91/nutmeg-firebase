import flask
from firebase_admin import firestore
from flask import Blueprint
from flask import current_app as app


bp = Blueprint('feedback', __name__, url_prefix='/feedback')


@bp.route("", methods=["POST"])
def add_feedback():
    feedback_text = flask.request.get_json()["text"]

    doc = app.db_client.collection("feedback").document()
    doc.set({
        "text": feedback_text,
        "createdAt": firestore.firestore.SERVER_TIMESTAMP,
        "user": flask.g.uid
    })

    return {"data": {}}
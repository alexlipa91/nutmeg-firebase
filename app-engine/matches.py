import traceback
from datetime import datetime, timezone, timedelta
from enum import Enum

import flask
from firebase_admin import firestore
from flask import Blueprint
from utils import _serialize_dates


bp = Blueprint('matches', __name__, url_prefix='/matches')

syncDb = firestore.client()


# todo deprecate
@bp.route("/", methods=["POST"])
# @cross_origin(origins=["*"], allow_headers=["firebase-instance-id-token", "content-type", "authorization"])
def matches():
    request_json = flask.request.get_json(silent=True)
    print("args {}, data {}".format(flask.request.args, request_json))

    # when can have values: 'future', 'all'
    when = request_json.get("when", None)
    with_user = request_json.get("with_user", None)
    organized_by = request_json.get("organized_by", None)

    result = _get_matches_firestore_v2(when=when, with_user=with_user, organized_by=organized_by)

    return {"data": result}, 200


@bp.route("", methods=["GET"])
def get_matches():
    request_json = flask.request.get_json(silent=True)
    print("args {}, data {}".format(flask.request.args, request_json))

    # when can have values: 'future', 'all'
    when = flask.request.args.get("when", None)
    with_user = flask.request.args.get("with_user", None)
    organized_by = flask.request.args.get("organized_by", None)

    result = _get_matches_firestore_v2(when=when, with_user=with_user, organized_by=organized_by)

    return {"data": result}, 200


@bp.route("/<match_id>", methods=["GET"])
def get_match(match_id):
    request_json = flask.request.get_json(silent=True)
    print("args {}, data {}".format(flask.request.args, request_json))

    match_data = syncDb.collection('matches').document(match_id).get().to_dict()

    if not match_data:
        return {}, 404
    return {"data": _format_match_data_v2(match_data)}, 200


class MatchStatus(Enum):
    CANCELLED = "cancelled"  # match has been canceled (cancelation can triggered both before or after match start time)
    RATED = "rated"  # all players have rated and POTM has been determined
    TO_RATE = "to_rate"  # match has been played and now is in rating window; users can rate
    PLAYING = "playing"  # we are in between match start and end time
    PRE_PLAYING = "pre_playing"  # we are before match start time and match has been confirmed (automatic cancellation didn't happen)
    OPEN = "open"  # match is in the future and is open for users to join
    UNPUBLISHED = "unpublished"  # match created but not visible to others


def _get_matches_firestore_v2(when="all", with_user=None, organized_by=None):
    query = syncDb.collection('matches')

    if when == "future":
        query = query.where('dateTime', '>', datetime.utcnow())
    if with_user:
        field_path = u"going.`{}`".format(with_user)
        query = query.where(field_path, "!=", "undefined")
    if organized_by:
        query = query.where('organizerId', "==", organized_by)

    res = {}

    for m in query.stream():
        try:
            data = _format_match_data_v2(m.to_dict())
            res[m.id] = data
        except Exception as e:
            print("Failed to read match data with id '{}".format(m.id))
            traceback.print_exc()

    return res


def _format_match_data_v2(match_data):
    # add status
    match_data["status"] = _get_status(match_data).value

    # serialize dates
    match_data = _serialize_dates(match_data)

    return match_data


def _get_status(match_data):
    if match_data.get("unpublished_reason", None):
        return MatchStatus.UNPUBLISHED

    if match_data.get("cancelledAt", None):
        return MatchStatus.CANCELLED
    if match_data.get("scoresComputedAt", None):
        return MatchStatus.RATED

    now = datetime.now(timezone.utc)
    start = match_data["dateTime"]
    cannot_leave_at = start - timedelta(hours=match_data.get("cancelHoursBefore", 0))
    end = start + timedelta(minutes=match_data["duration"])

    # cannot_leave_at   |   start   |   end

    if now > end:
        return MatchStatus.TO_RATE
    if now > start:
        return MatchStatus.PLAYING
    if now > cannot_leave_at:
        return MatchStatus.PRE_PLAYING
    return MatchStatus.OPEN


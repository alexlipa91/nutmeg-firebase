import asyncio
import datetime
import traceback
from enum import Enum

import firebase_admin
from flask_cors import cross_origin
from google.cloud.firestore import AsyncClient
from firebase_admin import firestore
from nutmeg_utils import firestore_utils


firebase_admin.initialize_app()


class MatchStatus(Enum):
    CANCELLED = "cancelled"             # match has been canceled (cancelation can triggered both before or after match start time)
    RATED = "rated"                     # all players have rated and POTM has been determined 
    TO_RATE = "to_rate"                 # match has been played and now is in rating window; users can rate 
    PLAYING = "playing"                 # we are in between match start and end time  
    PRE_PLAYING = "pre_playing"         # we are before match start time and match has been confirmed (automatic cancellation didn't happen)
    OPEN = "open"                       # match is in the future and is open for users to join
    UNPUBLISHED = "unpublished"         # match created but not visible to others


@cross_origin(origins=["*"], allow_headers=["firebase-instance-id-token", "content-type", "authorization"])
def get_match_v2(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    request_data = request_json["data"]

    return {"data": asyncio.run(_get_match_firestore_v2(request_data["id"]))}, 200


@cross_origin(origins=["*"], allow_headers=["firebase-instance-id-token", "content-type", "authorization"])
def get_all_matches_v2(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    # when can have values: 'future', 'all'
    when = request_json.get("data", {}).get("when", None)
    with_user = request_json.get("data", {}).get("with_user", None)
    organized_by = request_json.get("data", {}).get("organized_by", None)

    result = asyncio.run(_get_matches_firestore_v2(when=when, with_user=with_user,
                                                   organized_by=organized_by))

    return {"data": result}, 200


async def _get_match_firestore_v2(match_id):
    db = AsyncClient()
    match_data = (await db.collection('matches').document(match_id).get()).to_dict()
    return await _format_match_data_v2(match_data)


async def _format_match_data_v2(match_data):
    # add status
    match_data["status"] = _get_status(match_data).value

    # serialize dates
    match_data = firestore_utils._serialize_dates(match_data)

    return match_data


async def _get_matches_firestore_v2(when="all", with_user=None, organized_by=None):
    db = AsyncClient()
    query = db.collection('matches')

    if when == "future":
        query = query.where('dateTime', '>', datetime.datetime.utcnow())
    if with_user:
        field_path = u"going.`{}`".format(with_user)
        query = query.where(field_path, "!=", "undefined")
    if organized_by:
        query = query.where('organizerId', "==", organized_by)

    res = {}

    async for m in query.stream():
        try:
            data = await _format_match_data_v2(m.to_dict())
            res[m.id] = data
        except Exception as e:
            print("Failed to read match data with id '{}".format(m.id))
            traceback.print_exc()

    return res


def _get_status(match_data):
    if match_data.get("unpublished_reason", None):
        return MatchStatus.UNPUBLISHED

    if match_data.get("cancelledAt", None):
        return MatchStatus.CANCELLED
    if match_data.get("scoresComputedAt", None):
        return MatchStatus.RATED

    now = datetime.datetime.now(datetime.timezone.utc)
    start = match_data["dateTime"]
    cannot_leave_at = start - datetime.timedelta(hours=match_data.get("cancelHoursBefore", 0))
    end = start + datetime.timedelta(minutes=match_data["duration"])

    # cannot_leave_at   |   start   |   end

    if now > end:
        return MatchStatus.TO_RATE
    if now > start:
        return MatchStatus.PLAYING
    if now > cannot_leave_at:
        return MatchStatus.PRE_PLAYING
    return MatchStatus.OPEN


def delete_test():
    db = firestore.client()
    res = db.collection(u'matches').where("isTest", "==",  True).get()
    print(res)


def _serialize_date(date):
    return datetime.datetime.isoformat(date)


if __name__ == '__main__':
    res = asyncio.run(_get_matches_firestore_v2(
        # organized_by="bQHD0EM265V6GuSZuy1uQPHzb602"
        # when="future",
        # exclude_unpublished=True
    ))
    print(res)
    print(len(res))

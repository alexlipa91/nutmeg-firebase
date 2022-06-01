import asyncio
import datetime
import traceback
from enum import Enum

import firebase_admin
from google.cloud.firestore import AsyncClient
from firebase_admin import firestore


firebase_admin.initialize_app()


class MatchStatus(Enum):
    CANCELLED = "cancelled"             # match has been canceled (cancelation can triggered both before or after match start time)
    RATED = "rated"                     # all players have rated and POTM has been determined 
    TO_RATE = "to_rate"                 # match has been played and now is in rating window; users can rate 
    PLAYING = "playing"                 # we are in between match start and end time  
    PRE_PLAYING = "pre_playing"         # we are before match start time and match has been confirmed (automatic cancellation didn't happen)
    OPEN = "open"                       # match is in the future and is open for users to join
    UNPUBLISHED = "unpublished"         # match created but not visible to others


def get_match_v2(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    request_data = request_json["data"]

    return {"data": asyncio.run(_get_match_firestore_v2(request_data["id"]))}, 200


def get_all_matches_v2(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    return {"data": asyncio.run(_get_all_matches_firestore_v2())}, 200


async def _get_match_firestore_v2(match_id):
    db = AsyncClient()
    match_data = (await db.collection('matches').document(match_id).get()).to_dict()
    return await _format_match_data_v2(match_data)


async def _format_match_data_v2(match_data):
    # add status
    match_data["status"] = _get_status(match_data).value

    # serialize dates
    match_data["dateTime"] = _serialize_date(match_data["dateTime"])
    if match_data.get("cancelledAt", None):
        match_data["cancelledAt"] = _serialize_date(match_data["cancelledAt"])
    if match_data.get("scoresComputedAt", None):
        match_data["scoresComputedAt"] = _serialize_date(match_data["scoresComputedAt"])

    for u in match_data.get("going", []):
        match_data["going"][u]["createdAt"] = _serialize_date(match_data["going"][u]["createdAt"])
    return match_data


async def _get_all_matches_firestore_v2():
    db = AsyncClient()
    collection = await db.collection('matches').get()

    res = {}

    for m in collection:
        try:
            data = await _format_match_data_v2(m.to_dict())
            res[m.id] = data
        except Exception:
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
    print(asyncio.run(_get_match_firestore_v2("61MIUi1Anm1xzIBDpVzt")))

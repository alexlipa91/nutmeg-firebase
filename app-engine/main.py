import asyncio
import datetime
import traceback
from enum import Enum

from flask import Flask
from google.cloud.firestore_v1 import AsyncClient

app = Flask(__name__)


@app.route('/')
def hello():
    return {"data": asyncio.run(_get_all_matches_firestore_v2())}, 200


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


def _get_status(match_data):
    if match_data.get("cancelledAt", None):
        return MatchStatus.CANCELLED
    if match_data.get("scoresComputedAt", None):
        return MatchStatus.RATED

    now = datetime.datetime.now(datetime.timezone.utc)
    start = match_data["dateTime"]
    cannot_leave_at = start - datetime.timedelta(hours=1)
    end = start + datetime.timedelta(minutes=match_data["duration"])

    # cannot_leave_at   |   start   |   end

    if now > end:
        return MatchStatus.TO_RATE
    if now > start:
        return MatchStatus.PLAYING
    if now > cannot_leave_at:
        return MatchStatus.PRE_PLAYING
    if len(match_data.get("going", [])) == match_data["maxPlayers"]:
        return MatchStatus.FULL
    return MatchStatus.OPEN


def _serialize_date(date):
    return datetime.datetime.isoformat(date)


class MatchStatus(Enum):
    CANCELLED = "cancelled"
    RATED = "rated"
    TO_RATE = "to_rate"
    PLAYING = "playing"
    PRE_PLAYING = "pre_playing"
    FULL = "full"
    OPEN = "open"


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080, debug=True)
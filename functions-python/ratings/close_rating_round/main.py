import asyncio
import datetime

from firebase_admin import firestore, messaging
from google.cloud.firestore import AsyncClient
from decimal import Decimal
import firebase_admin


firebase_admin.initialize_app()


def close_rating_round(request):
    request_json = request.get_json(silent=True)
    print("data {}".format(request_json))

    request_data = request_json["data"]

    # FIXME disable ratings
    # return {"reason": "disabled"}, 500

    asyncio.run(_close_rating_round_firestore(request_data["match_id"]))

    return {"data": {}}, 200


async def _close_rating_round_firestore(match_id, send_notification=True):
    db = AsyncClient()

    timestamp = datetime.datetime.utcnow()

    match_doc = await db.collection("matches").document(match_id).get()
    match_data = match_doc.to_dict()
    if match_data["cancelledAt"]:
        raise Exception("Match is canceled")

    ratings_doc = await db.collection("ratings").document(match_id).get()
    if not ratings_doc.exists:
        print("No ratings for this match")
        # mark match as rated and store man_of_the_match
        await db.collection("matches").document(match_id).set({"scoresComputedAt": timestamp}, merge=True)
        return

    scores = ratings_doc.to_dict()["scores"]

    # do calculations
    final_scores = {}
    for u in scores:
        only_positive = list(filter(lambda s: s > 0, scores[u].values()))
        if len(only_positive) == 0:
            final_scores[u] = 0
        else:
            s = Decimal(sum(only_positive) / len(only_positive))
            final_scores[u] = float(round(s, 2))

    # who has the biggest dick in the match?        
    man_of_the_match, man_of_the_match_score = max(final_scores.items(), key=lambda x: x[1])
    print("final scores {}; man of the match: {}".format(final_scores, man_of_the_match))

    if "isTest" not in match_data or not match_data["isTest"]:
        # store score for users
        for user, score in final_scores.items():
            await db.collection("users").document(user).set({"scoreMatches": {match_id: score}}, merge=True)

        # store man of the match info in user doc
        await db.collection("users").document(man_of_the_match).update({"manOfTheMatch": firestore.firestore.ArrayUnion([match_id])})

    # mark match as rated and store man_of_the_match
    await db.collection("matches").document(match_id).set({"scoresComputedAt": timestamp,
                                                           "manOfTheMatch": {man_of_the_match: man_of_the_match_score}},
                                                          merge=True)
    if send_notification:
        _send_close_voting_notification(match_id, set(match_data["going"].keys()),
                                        man_of_the_match, match_data["sportCenterId"])


def _send_close_voting_notification(match_id, going_users, motm, sport_center_id):
    db = firestore.client()

    sport_center = db.collection('sport_centers').document(sport_center_id).get().to_dict()["name"]

    going_users.remove(motm)

    _send_notification_to_users(
        title="Match stats are available!",
        body="Check out the stats from the match at {}".format(sport_center),
        users=list(going_users),
        data={
            "click_action": "FLUTTER_NOTIFICATION_CLICK",
            "match_id": match_id,
        }
    )

    _send_notification_to_users(
        title="Congratulations! " + u"\U0001F3C6",
        body="You won the Player of the Match award for the {} match".format(sport_center),
        users=[motm],
        data={
            "click_action": "FLUTTER_NOTIFICATION_CLICK",
            "match_id": match_id,
            "event": "potm",
        }
    )


def _send_notification_to_users(title, body, data, users):
    db = firestore.client()

    tokens = []
    for user_id in users:
        user_tokens = db.collection('users').document(user_id).get(field_paths={"tokens"}).to_dict()["tokens"]
        tokens.extend(user_tokens)
    _send_notification_to_tokens(title, body, data, tokens)


def _send_notification_to_tokens(title, body, data, tokens):
    message = messaging.MulticastMessage(
        notification=messaging.Notification(
            title=title,
            body=body
        ),
        data=data,
        tokens=tokens,
    )
    response = messaging.send_multicast(message)
    print('Successfully sent {} messages'.format(response.success_count))
    if response.failure_count > 0:
        [print(r.exception) for r in response.responses if r.exception]


if __name__ == '__main__':
    print(asyncio.run(_close_rating_round_firestore("gAYBoHYPUmX1GMfCajou", send_notification=True)))

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


async def _close_rating_round_firestore(match_id):
    db = AsyncClient()

    timestamp = datetime.datetime.utcnow()

    match_doc = await db.collection("matches").document(match_id).get()
    match_data = match_doc.to_dict()
    if match_data["cancelledAt"]:
        raise Exception("Match is canceled")

    ratings_doc = await db.collection("ratings").document(match_id).get()
    scores = ratings_doc.to_dict()["scores"]

    if not ratings_doc.exists:
        raise Exception("No ratings for this match")

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

    # store score for users
    for user, score in final_scores.items():
        await db.collection("users").document(user).set({"scoreMatches": {match_id: man_of_the_match_score}}, merge=True)

    # store man of the match info in user doc
    await db.collection("users").document(man_of_the_match).update({"manOfTheMatch": firestore.firestore.ArrayUnion([match_id])})

    # mark match as rated and store man_of_the_match
    await db.collection("matches").document(match_id).set({"scoresComputedAt": timestamp,
                                                           "manOfTheMatch": {man_of_the_match: man_of_the_match_score}},
                                                          merge=True)

    _send_close_voting_notification(match_id, man_of_the_match, man_of_the_match_score, match_data["sportCenterId"])


def _send_close_voting_notification(match_id, motm, score, sport_center_id):
    db = firestore.client()

    sport_center = db.collection('sport_centers').document(sport_center_id).get().to_dict()["name"]

    _send_notification_to_users(
        title="Congratulations! " + u"\U0001F3C6",
        body="You were rated best player of the match at {}".format(sport_center),
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
    print(asyncio.run(_close_rating_round_firestore("FjSpAqpJX7q6wi4jyjlO")))

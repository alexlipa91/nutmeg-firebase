import asyncio
import datetime

from firebase_admin import firestore
from google.cloud.firestore import AsyncClient
from decimal import Decimal


def close_rating_round(request):
    request_json = request.get_json(silent=True)
    print("data {}".format(request_json))

    request_data = request_json["data"]

    asyncio.run(_close_rating_round_firestore(request_data["match_id"]))

    return {"data": {}}, 200


async def _close_rating_round_firestore(match_id):
    db = AsyncClient()

    timestamp = datetime.datetime.utcnow()

    ratings_doc = await db.collection("ratings").document(match_id).get()
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


if __name__ == '__main__':
    print(asyncio.run(_close_rating_round_firestore("ZAEd7UF1ULPJyruQdUEi")))

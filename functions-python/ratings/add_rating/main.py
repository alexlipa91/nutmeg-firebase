import asyncio

import firebase_admin
from flask_cors import cross_origin
from google.cloud.firestore_v1 import AsyncClient

firebase_admin.initialize_app()


def _get_db():
    return AsyncClient()


@cross_origin(origins=["*"], allow_headers=["firebase-instance-id-token"])
def add_rating(request):
    request_json = request.get_json(silent=True)
    print("data {}".format(request_json))

    request_data = request_json["data"]

    asyncio.run(_add_rating_firestore(request_data["user_id"],
                                      request_data["match_id"],
                                      request_data["user_rated_id"],
                                      request_data["score"]))

    return {"data": {}}, 200

# `user_id` gives rating to `user_rated_id`
# data is stored in this way:   `user_rated_id` : { `user_id` : score }
async def _add_rating_firestore(user_id, match_id, user_rated_id, score):
    db = _get_db()

    ratings_doc_ref = db.collection("ratings").document(match_id)
    ratings_doc = await ratings_doc_ref.get()

    ratings_data = ratings_doc.to_dict()

    if ratings_data:
        scores = ratings_data.get("scores", {})
        user_scores = scores.get(user_rated_id, {})

        if user_id in user_scores:
            raise Exception("{} already reviewed {} for match {}".format(user_id, user_rated_id, match_id))

    await ratings_doc_ref.set({"scores": {user_rated_id: {user_id: score}}}, merge=True)


if __name__ == '__main__':
    asyncio.run(_add_rating_firestore("d", "m", "a", -1))
    asyncio.run(_add_rating_firestore("e", "m", "a", -1))
    asyncio.run(_add_rating_firestore("x", "m", "a", 3))
    asyncio.run(_add_rating_firestore("y", "m", "a", 4))
    asyncio.run(_add_rating_firestore("z", "m", "a", 3))

    asyncio.run(_add_rating_firestore("z", "m", "b", 1))
    asyncio.run(_add_rating_firestore("x", "m", "b", 3))


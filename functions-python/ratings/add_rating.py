import asyncio

from google.cloud.firestore import AsyncClient


def add_rating_impl(request):
    request_json = request.get_json(silent=True)
    print("data {}".format(request.args, request_json))

    request_data = request_json["data"]

    asyncio.run(_add_rating_firestore(request_data["user_id"],
                                      request_data["match_id"],
                                      request_data["user_rated_id"],
                                      request_data["score"]))

    return {"data": {}}, 200


async def _add_rating_firestore(user_id, match_id, user_reviewed_id, score):
    db = AsyncClient()

    ratings_doc_ref = db.collection("ratings").document(match_id)
    review = await ratings_doc_ref.get()

    if review.exists and user_reviewed_id in review.to_dict().get("scores", {}).get(user_id, None):
        raise Exception("{} already reviewed {} for match {}".format(user_id, user_reviewed_id, match_id))

    await ratings_doc_ref.set(
        {"scores": {user_id: {user_reviewed_id: score}}}, merge=True
    )

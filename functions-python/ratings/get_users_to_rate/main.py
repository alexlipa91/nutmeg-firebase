import asyncio

from google.cloud.firestore import AsyncClient


def get_users_to_rate(request):
    request_json = request.get_json(silent=True)
    print("data {}".format(request.args, request_json))

    request_data = request_json["data"]

    users = asyncio.run(_get_users_to_rate_firestore(request_data["user_id"], request_data["match_id"]))
    print(users)

    return {"data": {"users": list(users)}}, 200


async def _get_users_to_rate_firestore(user_id, match_id):
    db = AsyncClient()

    ratings_doc_ref = db.collection("ratings").document(match_id)

    # get going users
    doc = await db.collection("matches").document(match_id).get(field_paths=["going"])
    going_users = set(doc.to_dict().get("going", {}).keys())

    # remove the person giving the rate
    if user_id in going_users:
        going_users.remove(user_id)

    doc = await ratings_doc_ref.get(field_paths=["scores"])

    if doc.exists:
        rated_users = set(doc.to_dict().get("scores", {}).get(user_id, {}).keys())
    else:
        return going_users

    to_rate = set(going_users)
    for rated in rated_users:
        if rated in to_rate:
            to_rate.remove(rated)

    print("users going: {}\tusers rated {}, users still to rate {}".format(going_users, rated_users, to_rate))

    return to_rate

if __name__ == '__main__':
    print(asyncio.run(_get_users_to_rate_firestore("IwrZWBFb4LZl3Kto1V3oUKPnCni1",
                                             "ZAEd7UF1ULPJyruQdUEi")))
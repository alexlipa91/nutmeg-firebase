import asyncio

from google.cloud.firestore import AsyncClient


def get_users_to_rate(request):
    request_json = request.get_json(silent=True)
    print("data {}".format(request_json))

    request_data = request_json["data"]

    users = asyncio.run(_get_users_to_rate_firestore(request_data["user_id"], request_data["match_id"]))

    return {"data": {"users": list(users)}}, 200


async def _get_users_to_rate_firestore(user_id, match_id):
    db = AsyncClient()

    ratings_doc = await db.collection("ratings").document(match_id).get()

    # get going users (except current user)
    doc = await db.collection("matches").document(match_id).get(field_paths=["going"])
    going_users = set(doc.to_dict().get("going", {}).keys())
    if user_id in going_users:
        going_users.remove(user_id)

    if not ratings_doc.exists:
        return going_users

    rated_users = list()
    scores = ratings_doc.to_dict()["scores"]

    if doc.exists:
        for user_receiving, users_giver in scores.items():
            for user_giver in users_giver:
                if user_giver == user_id:
                    rated_users.append(user_receiving)
                    break
    else:
        return going_users

    to_rate = set(going_users)
    for rated in rated_users:
        if rated in to_rate:
            to_rate.remove(rated)

    print("users going: {}\tusers rated {}, users still to rate {}".format(len(going_users), len(rated_users), len(to_rate)))

    return to_rate

if __name__ == '__main__':
    print(asyncio.run(_get_users_to_rate_firestore("IwrZWBFb4LZl3Kto1V3oUKPnCni1",
                                             "3dD9fotUuuuGySkDhU5o")))
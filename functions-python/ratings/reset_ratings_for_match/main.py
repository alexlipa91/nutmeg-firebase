import asyncio

from firebase_admin import firestore
from google.cloud.firestore import AsyncClient


def reset_ratings_for_match(request):
    request_json = request.get_json(silent=True)
    print("data {}".format(request_json))

    request_data = request_json["data"]

    asyncio.run(_reset_ratings_for_match(request_data["match_id"]))

    return {"data": {}}, 200


async def _reset_ratings_for_match(match_id):
    db = AsyncClient()

    await db.collection("ratings").document(match_id).delete()

    match_doc = db.collection("matches").document(match_id)
    match_data = (await match_doc.get()).to_dict()

    if "manOfTheMatch" in match_data:
        potms = match_data["manOfTheMatch"].keys()

        await match_doc.update({
            "manOfTheMatch": firestore.firestore.DELETE_FIELD,
            "scoresComputedAt": firestore.firestore.DELETE_FIELD
        })

        for potm in potms:
            await db.collection("users").document(potm).update({
                "manOfTheMatch": firestore.firestore.ArrayRemove([match_id])
            })

    users_going = (await match_doc.get()).to_dict()["going"].keys()

    for u in users_going:
        try:
            await db.collection("users").document(u).update({
                "scoreMatches.{}".format(match_id): firestore.firestore.DELETE_FIELD
            })
        except:
            print("Failed to update {} user document".format(u))

if __name__ == '__main__':
    asyncio.run(_reset_ratings_for_match("EKPi6qHMI2du2sHykRlG"))

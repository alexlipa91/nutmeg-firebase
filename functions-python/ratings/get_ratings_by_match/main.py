import asyncio

import firebase_admin
from flask_cors import cross_origin
from google.cloud.firestore_v1 import AsyncClient

firebase_admin.initialize_app()


def _get_db():
    return AsyncClient()


@cross_origin(origins=["*"], allow_headers=["firebase-instance-id-token", "content-type", "authorization"])
def get_ratings_by_match_v3(request):
    request_json = request.get_json(silent=True)
    print("data {}".format(request_json))

    request_data = request_json["data"]

    resp = asyncio.run(_get_ratings_by_match_v3(request_data["match_id"]))

    return {"data": resp}, 200


async def _get_ratings_by_match(match_id):
    db = _get_db()

    ratings_doc_ref = db.collection("ratings").document(match_id)
    ratings_doc = await ratings_doc_ref.get()

    if not ratings_doc.exists:
        return {}

    ratings_data = ratings_doc.to_dict()

    response = [(user, list(scores.values())) for user, scores in ratings_data["scores"].items()]
    return dict(response)


async def _get_ratings_by_match_v2(match_id):
    db = _get_db()

    ratings_doc_ref = db.collection("ratings").document(match_id)
    ratings_doc = await ratings_doc_ref.get()

    if not ratings_doc.exists:
        return {}

    ratings_data = ratings_doc.to_dict()
    return ratings_data["scores"]


async def _get_ratings_by_match_v3(match_id):
    db = _get_db()

    ratings_doc_ref = db.collection("ratings").document(match_id)
    ratings_doc = await ratings_doc_ref.get()

    if not ratings_doc.exists:
        return {}

    ratings_data = ratings_doc.to_dict()
    return ratings_data


if __name__ == '__main__':
    print(asyncio.run(_get_ratings_by_match_v3("4u4zPZ6EGTcAeKOW6j9q")))

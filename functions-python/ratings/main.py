import firebase_admin
from firebase_admin import firestore

firebase_admin.initialize_app()


def add_rating(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    request_data = request_json["data"]

    _add_rating_firestore(request_data["user_id"],
                          request_data["match_id"],
                          request_data["user_reviewed_id"],
                          request_data["score"])

    return {"data": {}}, 200


def _add_rating_firestore(user_id, match_id, user_reviewed_id, score):
    db = firestore.client()

    review_doc_ref = db.collection("ratings").document(match_id)
    review = review_doc_ref.get()

    if review.exists and user_reviewed_id in review.to_dict().get(user_id, {}):
        raise Exception("{} already reviewed {} for match {}".format(user_id, user_reviewed_id, match_id))

    review_doc_ref.set(
        {user_id: {user_reviewed_id: score}}, merge=True
    )


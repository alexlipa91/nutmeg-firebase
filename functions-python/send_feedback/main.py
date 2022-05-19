import firebase_admin
from firebase_admin import firestore

firebase_admin.initialize_app()


def send_feedback(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    request_data = request_json["data"]
    feedback_text = request_data["text"]

    db = firestore.client()
    doc = db.collection("feedback").document()
    doc.set({
        "text": feedback_text,
        "createdAt": firestore.firestore.SERVER_TIMESTAMP
    })

    return {"data": {}}, 200

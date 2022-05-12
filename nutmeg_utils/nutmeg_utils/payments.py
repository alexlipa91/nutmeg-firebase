from firebase_admin import firestore


def get_payment_intent(match_id, user_id):
    db = firestore.client()

    trans = db.collection('matches').document(match_id).collection("transactions").get()

    user_trans = []
    for t in trans:
        t_data = t.to_dict()
        if t_data["userId"] == user_id:
            user_trans.append(t_data)

    # sort by most recent first
    user_trans.sort(key=lambda x: x["createdAt"], reverse=True)

    last_trans = user_trans[0]

    if last_trans["type"] != "joined":
        raise Exception("Expected a 'joined' transaction but not found")

    return last_trans["paymentIntent"]

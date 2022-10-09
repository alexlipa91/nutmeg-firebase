from firebase_admin import firestore


def get_sport_center(match_data):
    if "sportCenterId" in match_data:
        db = firestore.client()
        return db.collection('sport_centers').document(match_data["sportCenterId"]).get().to_dict()
    return match_data["sportCenter"]

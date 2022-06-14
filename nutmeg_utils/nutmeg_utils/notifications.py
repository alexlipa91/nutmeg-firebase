from firebase_admin import firestore, messaging


def send_notification_to_users(title, body, data, users):
    db = firestore.client()

    # normal send
    tokens = set()
    for user_id in users:
        user_tokens = db.collection('users').document(user_id).get(field_paths={"tokens"}).to_dict()["tokens"]
        for t in user_tokens:
            tokens.add(t)
    _send_notification_to_tokens(title, body, data, list(tokens))

    # forward to admins
    admins = ["IwrZWBFb4LZl3Kto1V3oUKPnCni1", "bQHD0EM265V6GuSZuy1uQPHzb602"]
    admins_to_forward = set()
    [admins_to_forward.add(a) for a in admins if a not in users]

    tokens = set()
    for user_id in admins_to_forward:
        admins_tokens = db.collection('users').document(user_id).get(field_paths={"tokens"}).to_dict()["tokens"]
        for t in admins_tokens:
            tokens.add(t)
    _send_notification_to_tokens("[admin] {}".format(title), body, data, list(tokens))


def _send_notification_to_tokens(title, body, data, tokens):
    message = messaging.MulticastMessage(
        notification=messaging.Notification(
            title=title,
            body=body
        ),
        data=data,
        tokens=tokens,
    )
    response = messaging.send_multicast(message)
    print('Sent: {}. Failed: {}'.format(response.success_count, response.failure_count))
const functions = require("firebase-functions");
const admin = require('firebase-admin');

exports.insertFakeData = functions.https.onRequest((req, res) => {
    insertSubscriptions()
        .then((a) => res.status(200).send(a))
        .catch((e) => res.status(500).send(e))
});

const insertSubscriptions = async function () {
    const matchId = "12345";
    const collectionRef = admin.firestore().collection("matches/" + matchId + "/subscriptions");
    await collectionRef.add({
        "userId": "a",
        "createdAt": new Date("2013-09-05 15:34:00"),
        "status": "going"
    })
    await collectionRef.add({
        "userId": "a",
        "createdAt": new Date("2013-09-04 15:34:00"),
        "status": "refunded",
    })
    await collectionRef.add({
        "userId": "a",
        "createdAt": new Date("2013-09-03 15:34:00"),
        "status": "going",
    })
    await collectionRef.add({
        "userId": "b",
        "createdAt": new Date("2013-09-05 15:34:00"),
        "status": "refunded"
    })
    await collectionRef.add({
        "userId": "b",
        "createdAt": new Date("2013-09-05 14:34:00"),
        "status": "going"
    })
    await admin.firestore().doc("users/a").set({"tokens": ["token-a-1", "tokens-a-2"]});
    await admin.firestore().doc("users/b").set({"tokens": ["token-b-1", "token-b-2"]});
}
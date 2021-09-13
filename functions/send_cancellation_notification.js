const functions = require("firebase-functions");
const admin = require('firebase-admin');

exports.sendCancellationNotification = functions.https.onRequest((req, res) => {
    let matchId = req.body.matchId
    console.log("fetching subs for match: " + matchId)

    runFunction(matchId)
        .then(() => res.status(200).send())
        .catch((e) => res.status(500).send(e))
});

const runFunction = async function (matchId) {
    let subs = Array.from(await getLatestSubscriptionsPerUser(matchId));
    console.log("found " + subs.length + " subscriptions");
    let goingUsers = subs.filter(s => s.status === "going").map(s => s.userId);
    console.log(goingUsers);
    let tokens = (await Promise.all(goingUsers.map(async (u) => await getUserTokens(u)))).flat();
    await sendNotificationToTokens(tokens, matchId);
}

const getLatestSubscriptionsPerUser = async function (matchId) {
    const qs = await admin.firestore().collection("matches/" + matchId + "/subscriptions").get();
    const documentsData = qs.docs.map(doc => doc.data());

    const latestSubs = new Map();
    let subscriptions;
    let current;
    for (let i = 0; i < documentsData.length; i++) {
        subscriptions = documentsData[i];
        current = latestSubs.get(subscriptions.userId);
        if (current == null || subscriptions.createdAt > current.createdAt) {
            latestSubs.set(subscriptions.userId, subscriptions);
        }
    }
    return latestSubs.values();
}

const getUserTokens = async function (userId) {
    const ds = await admin.firestore().doc("users/" + userId).get();
    return ds.data().tokens
}

const sendNotificationToTokens = async function (tokens, matchId) {
    console.log("sending notifications to " + tokens.length + " devices");
    console.log(tokens)
    await admin.messaging().sendMulticast({
        tokens: tokens,
        notification: {
            title: "Match Cancellation!",
            body: "Unfortunately match " + matchId + " has been cancelled. We are processing your refund."
        },
    });
}
const functions = require("firebase-functions");
const admin = require('firebase-admin');
const Sugar = require('sugar')


exports.sendCancellationNotification = functions.https.onRequest((req, res) => {
    let matchId = req.body.matchId
    console.log("fetching subs for match: " + matchId)

    runFunction(matchId)
        .then(() => {
            console.log("success")
            res.status(200).send()
        })
        .catch((e) => {
            console.log("finished with error " + e)
            res.status(500).send(e.toString())
        })
});

const runFunction = async function (matchId) {
    let subs = Array.from(await getLatestSubscriptionsPerUser(matchId));
    let goingUsers = subs.filter(s => s.status === "going").map(s => s.userId);
    console.log("found " + goingUsers.length + " going users");
    const tokens = (await Promise.all(goingUsers.map(async (u) => await getUserTokens(u)))).flat();
    const matchInfo = await getMatchInfo(matchId)
    return await sendNotificationToTokens(tokens, matchInfo.dateTime, matchInfo.sportcenter);
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
    const tokens = ds.data().tokens
    if (typeof tokens == "undefined") {
        return []
    }
    return tokens
}

const sendNotificationToTokens = async function (tokens, datetime, sportcenter) {
    Sugar.extend();
    console.log("sending notifications to " + tokens.length + " tokens");

    const date = Sugar.Date.create(datetime.toMillis())
    const dateToString = Sugar.Date.format(date, "{dd}/{MM}/{yyyy} {H}:{mm}");

    return await admin.messaging().sendMulticast({
        tokens: tokens,
        notification: {
            title: "Match Cancellation!",
            // fixme figure out how to format the date
            body: "Unfortunately your match planned for " + dateToString
                + " at " + sportcenter + " has been cancelled.\n"
                + "We are sorry for the inconvenience. We are processing your refund."
        },
    });
}

const getMatchInfo = async function(matchId) {
    const match = await admin.firestore().doc("matches/" + matchId).get();
    const sportCenter = await admin.firestore().doc("sport_centers/" + match.data().sportCenter).get();
    return {
        "dateTime" : match.data().dateTime,
        "sportcenter": sportCenter.data().name
    }
}
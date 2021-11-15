const functions = require("firebase-functions");
const admin = require('firebase-admin');


exports.sendGenericNotification = functions.https.onRequest((req, res) => {
    console.log(req.body)
    runFunction(req.body.title, req.body.body, req.body.tokens, req.body.topic)
        .then(() => {
            console.log("success")
            res.status(200).send()
        })
        .catch((e) => {
            console.log("finished with error " + e)
            res.status(500).send(e.toString())
        })
});

const runFunction = async function (title, body, tokens, topic) {
    if (topic != null) {
        return await sendNotificationToTopic(title, body, topic)
    } else {
        const allUsers = await getAllUsers();
        if (tokens == null) {
            tokens = (await Promise.all(allUsers.map(async (u) => await getUserTokens(u)))).flat();
        }
        return await sendNotificationToTokens(tokens, title, body);
    }
}

const getAllUsers = async function () {
    const qs = await admin.firestore().collection("users").get();
    return qs.docs.map(doc => doc.id);
}

const getUserTokens = async function (userId) {
    const ds = await admin.firestore().doc("users/" + userId).get();
    const tokens = ds.data().tokens
    if (typeof tokens == "undefined") {
        return []
    }
    return tokens
}

const sendNotificationToTokens = async function (tokens, title, body) {
    console.log("sending notifications to " + tokens.length + " tokens");
    console.log("title: " + title + "; body: " + body);

    return await admin.messaging().sendMulticast({
        tokens: tokens,
        notification: {
            title: title,
            body: body
        },
    });
}

const sendNotificationToTopic = async function (title, body, topic) {
    console.log("sending notifications to nutmeg-generic");
    console.log("title: " + title + "; body: " + body);

    return await admin.messaging().sendToTopic(topic,
        {
            notification: {
                title: title,
                body: body
            }
        }
    );
}
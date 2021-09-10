const functions = require("firebase-functions");

// The Firebase Admin SDK to access Firestore.
const admin = require('firebase-admin');
admin.initializeApp();

exports.schedulePreMatchNotification = functions.firestore
    .document('matches/{matchId}')
    .onWrite((change, context) => {
        const matchTs = change.after.data()["dateTime"].toMillis();
        const match = context.params.matchId;

        const notificationTs = matchTs - 2 * 60 * 60 * 1000;

        return createHttpTaskWithToken(payload = JSON.stringify({matchId: match}),
            date = new Date(notificationTs))
    });


const createHttpTaskWithToken = async function (
    payload, // The task HTTP request body
    date, // Int
    project = 'nutmeg-9099c', // Your GCP Project id
    queue = 'match-notifications', // Name of your Queue
    location = 'europe-west1', // The GCP region of your queue
    url = 'https://us-central1-nutmeg-9099c.cloudfunctions.net/listFruit', // The full url path that the request will be sent to
    email = 'nutmeg-9099c@appspot.gserviceaccount.com', // Cloud IAM service accountended date to schedule task
) {
    console.log("scheduling notifications of functions: " + url + " with payload " + payload + " at time " + date)

    // Imports the Google Cloud Tasks library.
    const {v2beta3} = require('@google-cloud/tasks');

    // Instantiates a client.
    const client = new v2beta3.CloudTasksClient();

    // Construct the fully qualified queue name.
    const parent = client.queuePath(project, location, queue);

    // Convert message to buffer.
    const convertedPayload = JSON.stringify(payload);
    const body = Buffer.from(convertedPayload).toString('base64');

    const task = {
        httpRequest: {
            httpMethod: 'POST',
            url,
            oidcToken: {
                serviceAccountEmail: email,
                audience: new URL(url).origin,
            },
            headers: {
                'Content-Type': 'application/json',
            },
            body,
        },
    };

    const convertedDate = new Date(date);
    const currentDate = new Date();

    // Schedule time can not be in the past.
    if (convertedDate < currentDate) {
        console.error('Scheduled date in the past.');
    } else if (convertedDate > currentDate) {
        const date_diff_in_seconds = (convertedDate.getTime() - currentDate.getTime()) / 1000;
        // Restrict schedule time to the 30 day maximum.
        if (date_diff_in_seconds > MAX_SCHEDULE_LIMIT) {
            console.error('Schedule time is over 30 day maximum.');
        }
        // Construct future date in Unix time.
        const date_in_seconds =
            Math.min(date_diff_in_seconds, MAX_SCHEDULE_LIMIT) + Date.now() / 1000;
        // Add schedule time to request in Unix time using Timestamp structure.
        // https://googleapis.dev/nodejs/tasks/latest/google.protobuf.html#.Timestamp
        task.scheduleTime = {
            seconds: date_in_seconds,
        };
    }

    try {
        // Send create task request.
        const [response] = await client.createTask({parent, task});
        console.log(`Created task ${response.name}`);
        return response.name;
    } catch (error) {
        // Construct error for Stackdriver Error Reporting
        console.error(Error(error.message));
    }
};

const schedulePrematchNofification = require('./schedule_prematch_notification');
const sendCancellationNotification = require('./send_cancellation_notification');
const insertFakeData = require('./insert_fake_data');
const admin = require("firebase-admin");

admin.initializeApp();

exports.schedulePrematchNofification = schedulePrematchNofification.schedulePreMatchNotification;
exports.sendCancellationNotification = sendCancellationNotification.sendCancellationNotification;
exports.insertFakeData = insertFakeData.insertFakeData;
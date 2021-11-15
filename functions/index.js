const schedulePrematchNofification = require('./schedule_prematch_notification');
const sendCancellationNotification = require('./send_cancellation_notification');
const sendGenericNotification = require('./send_generic_notification');
const insertFakeData = require('./insert_fake_data');
const admin = require("firebase-admin");

admin.initializeApp();

exports.schedulePrematchNofification = schedulePrematchNofification.schedulePreMatchNotification;
exports.sendCancellationNotification = sendCancellationNotification.sendCancellationNotification;
exports.sendGenericNotification = sendGenericNotification.sendGenericNotification;

exports.insertFakeData = insertFakeData.insertFakeData;
import os
import random
import traceback
from collections import namedtuple
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import List, Dict

import dateutil.parser
import firebase_admin
import pytz
import stripe
from google.cloud import tasks_v2

from src.blueprints import sportcenters

import flask
import geopy.distance
from firebase_admin import firestore
from flask import Blueprint, Flask

from statistics.stats_utils import UserUpdates
from src.blueprints.users import _get_user_firestore
from src.utils import _serialize_dates, build_dynamic_link, send_notification_to_users, \
    schedule_app_engine_call, update_leaderboard
from flask import current_app as app

bp = Blueprint('matches', __name__, url_prefix='/matches')
tz = pytz.timezone('Europe/Amsterdam')


# todo deprecate
@bp.route("/", methods=["POST"])
def matches():
    request_json = flask.request.get_json(silent=True)

    # when can have values: 'future', 'all'
    when = request_json.get("when", None)
    with_user = request_json.get("with_user", None)
    organized_by = request_json.get("organized_by", None)

    result = _get_matches_firestore(when=when, with_user=with_user, organized_by=organized_by, version=1)

    return {"data": result}, 200


@bp.route("", methods=["GET"])
def get_matches():
    # when can have values: 'future', 'past'
    when = flask.request.args.get("when", None)
    with_user = flask.request.args.get("with_user", None)
    organized_by = flask.request.args.get("organized_by", None)
    lat = flask.request.args.get("lat", None)
    lng = flask.request.args.get("lng", None)
    radius_km = flask.request.args.get("radius_km", None)
    version = int(flask.request.args.get("version", 1))
    user_id = flask.g.uid

    if lat == "null":
        app.logger.error("received null as lat, fallback to Ams")
        lat = 52.3676
    if lng == "null":
        app.logger.error("received null as lng, fallback to Ams")
        lng = 4.9041

    result = _get_matches_firestore(user_location=(lat, lng), when=when, with_user=with_user,
                                    organized_by=organized_by, radius_km=radius_km, user_id=user_id,
                                    version=version)

    return {"data": result}, 200


@bp.route("/<match_id>", methods=["GET", "POST"])
def get_match(match_id, is_local=False):
    if is_local:
        return app.db_client.collection('matches').document(match_id).get().to_dict()

    if flask.request.method == "GET":
        match_data = app.db_client.collection('matches').document(match_id).get().to_dict()
        version = 2 if is_local else int(flask.request.args.get("version", 1))

        if not match_data:
            return {}, 404
        return {"data": _format_match_data_v2(match_id, match_data, version,
                                              add_organizer_info=match_data.get("organizerId", None) == flask.g.uid)}
    elif flask.request.method == "POST":
        data = flask.request.get_json()
        data["dateTime"] = datetime.strptime(data['dateTime'], "%Y-%m-%dT%H:%M:%S.%fZ")
        app.db_client.collection("matches").document(match_id).update(data)
        return {}, 200


@bp.route("/<match_id>/ratings", methods=["GET"])
def get_ratings(match_id):
    ratings_data = app.db_client.collection("ratings").document(match_id).get().to_dict()
    if not ratings_data:
        return {}, 200
    match_stats = MatchStats(
        match_id,
        None,
        [],
        ratings_data.get("scores", {}),
        ratings_data.get("skills", {})
    )
    if not match_stats:
        return {}, 200
    resp = {
        "scores": match_stats.user_scores,
        "potms": match_stats.potms
    }
    return {"data": resp}, 200


@bp.route("/<match_id>/ratings/add", methods=["POST"])
def add_rating(match_id):
    request_data = flask.request.get_json()

    app.db_client.collection("ratings").document(match_id).set(
        {"scores": {request_data["user_rated_id"]: {request_data["user_id"]: request_data["score"]}},
         "skills": {request_data["user_rated_id"]: {request_data["user_id"]: request_data.get("skills", [])}}},
        merge=True)
    return {}


@bp.route("/<match_id>/ratings/add_multi", methods=["POST"])
def add_rating_multi(match_id):
    request_data = flask.request.get_json()
    update = {"scores": {}}
    for receiver in request_data:
        update["scores"][receiver] = {flask.g.uid: request_data[receiver]}
    print(update)
    app.db_client.collection("ratings").document(match_id).set(update, merge=True)
    return {}


@bp.route("/<match_id>/ratings/to_vote", methods=["GET"])
def get_still_to_vote(match_id):
    all_going = app.db_client.collection("matches").document(match_id).get().to_dict().get("going", {}).keys()
    received_dict = app.db_client.collection("ratings").document(match_id).get().to_dict()
    received = received_dict.get("scores", {}) if received_dict else {}

    user_id = flask.g.uid
    to_vote = set()

    for u in all_going:
        received_by_u = received.get(u, {}).keys()
        if u != user_id and user_id not in received_by_u:
            to_vote.add(u)

    return {"data": {"users": list(to_vote)}}, 200


@bp.route("", methods=["POST"])
def create_match():
    request_json = flask.request.get_json(silent=True)

    is_test = request_json.get("isTest", False)
    organizer_id = request_json["organizerId"]

    match_id = _add_match_firestore(request_json)

    match_with_payments = "price" in request_json

    _update_user_account(organizer_id, is_test, match_id, match_with_payments)

    return {"data": {"id": match_id}}, 200


@bp.route("/<match_id>/teams/<algorithm>", methods=["GET"])
def get_teams(match_id, algorithm="balanced"):
    going = list(app.db_client.collection('matches').document(match_id).get().to_dict().get("going", {}).keys())
    scores = {}

    for u in going:
        scores[u] = _get_user_firestore(u).get("avg_score", 3)

    teams = [[], []]
    teams_total_score = [0, 0]

    if algorithm == "random":
        random.shuffle(going)
        index = len(going) // 2
        teams[0] = going[0:index]
        teams[1] = going[index:]
        for i, team in enumerate(teams):
            for u in team:
                teams_total_score[i] += scores[u]
    elif algorithm == "balanced":
        users_sorted_by_score = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        i = 0
        while i < len(users_sorted_by_score):
            if teams_total_score[0] <= teams_total_score[1]:
                next_team_to_assign = 0
            else:
                next_team_to_assign = 1
            teams[next_team_to_assign].append(users_sorted_by_score[i][0])
            teams_total_score[next_team_to_assign] += users_sorted_by_score[i][1]
            i = i + 1
            if i < len(users_sorted_by_score):
                teams[not next_team_to_assign].append(users_sorted_by_score[i][0])
                teams_total_score[not next_team_to_assign] += users_sorted_by_score[i][1]
            i = i + 1

    assert len(going) == len(teams[0]) + len(teams[1])

    # write to db
    match_updates = {
        "teams.balanced.weights.a": teams_total_score[0],
        "teams.balanced.weights.b": teams_total_score[1],
        "teams.balanced.players.a": teams[0],
        "teams.balanced.players.b": teams[1],
    }
    app.db_client.collection("matches").document(match_id).update(match_updates)

    print("teams: {}, total scores: {}".format(teams, teams_total_score))
    return {}


@bp.route("/<match_id>/users/add", methods=["POST"])
def add_user_to_match(match_id, user_id=None, payment_intent=None, local=False):
    if not local:
        # remote call, get from request
        data = flask.request.get_json(silent=True)

        user_id = data["user_id"]
        payment_intent = data.get("payment_intent", None)

    transactions_doc_ref = app.db_client.collection('matches').document(match_id).collection("transactions").document()
    user_stat_doc_ref = app.db_client.collection("users").document(user_id).collection("stats").document("match_votes")
    match_doc_ref = app.db_client.collection('matches').document(match_id)

    _add_user_to_match_firestore_transaction(app.db_client.transaction(),
                                             transactions_doc_ref,
                                             user_stat_doc_ref,
                                             match_doc_ref,
                                             payment_intent, user_id, match_id)

    # recompute teams
    get_teams(match_id)

    return {"data": {}}, 200


@bp.route("/<match_id>/users/remove", methods=["POST"])
def remove_user_from_match(match_id):
    user_id = flask.g.uid
    _remove_user_from_match_firestore(match_id, user_id)

    # recompute teams
    get_teams(match_id)

    return {"data": {}}, 200


@bp.route("/<match_id>/cancel", methods=["GET"])
def cancel_match(match_id, trigger="manual"):
    match_doc_ref = app.db_client.collection('matches').document(match_id)

    match_data = match_doc_ref.get().to_dict()

    if match_data.get("cancelledAt", None):
        raise Exception("Match has already been cancelled")

    users_stats_docs = {}
    for u in match_data.get("going", {}).keys():
        users_stats_docs[u] = app.db_client.collection("users").document(u).collection("stats").document("match_votes")

    _cancel_match_firestore_transactional(app.db_client.transaction(), match_doc_ref, users_stats_docs,
                                          match_id, match_data["isTest"], trigger)
    return {}


@bp.route("/<match_id>/confirm", methods=["GET"])
def confirm_match(match_id):
    match_data = app.db_client.collection('matches').document(match_id).get().to_dict()

    if len(match_data.get("going", {}).keys()) < match_data["minPlayers"]:
        print("canceling match")
        cancel_match(match_id, "automatic")
    else:
        print("confirming match")
        app.db_client.collection('matches').document(match_id).update({"confirmedAt": datetime.now()})

    return {}, 200


@bp.route("/<match_id>/tasks/prematch", methods=["GET"])
def run_prematch_tasks(match_id):
    match = app.db_client.collection("matches").document(match_id).get().to_dict()
    if not match or match.get("cancelledAt", None) is not None:
        print("match not existing or cancelled...skipping")
        return {"status": "skipped", "reason": "cancelled"}

    users = match.get("going", {}).keys()
    sport_center = match["sportCenter"]
    date_time_local = match["dateTime"].astimezone(pytz.timezone(sport_center["timeZoneId"]))

    send_notification_to_users(db=app.db_client,
                               title="Ready for the match? " + u"\u26BD\uFE0F",
                               body="Your match today is at {} at {}. Tap here to check your team!".format(
                                   date_time_local.strftime("%H:%M"),
                                   sport_center["name"]),
                               users=users,
                               data={
                                   "click_action": "FLUTTER_NOTIFICATION_CLICK",
                                   "route": "/match/" + match_id,
                                   "match_id": match_id
                               })
    return {"status": "success"}


@bp.route("/<match_id>/tasks/precancellation", methods=["GET"])
def run_precancellation_tasks(match_id):
    match = app.db_client.collection("matches").document(match_id).get().to_dict()

    if not match or "cancelledAt" in match:
        print("match has been cancelled or removed from the db...skipping")
        return {"status": "skipped", "reason": "removed"}

    organizer_id = match["organizerId"]
    num_going = len(match.get("going", {}))
    min_players = match["minPlayers"]

    if num_going < min_players:
        send_notification_to_users(
            db=app.db_client,
            title="Your match might be canceled in 1 hour!",
            body="Currently only {} players out of {} have joined your match.".format(num_going, min_players),
            users=[organizer_id],
            data={
                "click_action": "FLUTTER_NOTIFICATION_CLICK",
                "route": "/match/" + match_id,
                "match_id": match_id
            }
        )
        return {"status": "success"}

    return {"status": "skipped", "reason": "enough_players"}


@bp.route("/<match_id>/tasks/postmatch", methods=["GET"])
def run_post_match_tasks(match_id):
    match_data = app.db_client.collection("matches").document(match_id).get().to_dict()

    if not match_data:
        print("match deleted...skipping")
        return {"status": "skipped", "reason": "deleted"}
    if match_data.get("cancelledAt", None) is not None:
        print("match cancelled...skipping")
        return {"status": "skipped", "reason": "cancelled"}

    going_users = match_data.get("going", {}).keys()
    organiser_id = match_data.get("organizerId", None)

    send_notification_to_users(
        db=app.db_client,
        title="Rate players! " + u"\u2B50\uFE0F",
        body="You have 24h to rate the players of today's match.",
        users=going_users,
        data={
            "click_action": "FLUTTER_NOTIFICATION_CLICK",
            "route": "/match/" + match_id,
            "match_id": match_id
        }
    )

    if organiser_id:
        send_notification_to_users(
            db=app.db_client,
            title="Add match result! " + u"\u2B50\uFE0F",
            body="Add the final score for your match.",
            users=organiser_id,
            data={
                "click_action": "FLUTTER_NOTIFICATION_CLICK",
                "route": "/match/" + match_id,
                "match_id": match_id
            }
        )

    # payout
    schedule_app_engine_call(
        task_name="payout_organizer_for_match_{}_attempt_number_{}".format(match_id, 1),
        endpoint="matches/{}/tasks/payout?attempt={}".format(match_id, 1),
        date_time_to_execute=datetime.now() + timedelta(days=3)
    )
    return {"status": "success"}


@bp.route("/<match_id>/tasks/payout", methods=["GET"])
def create_organizer_payout(match_id):
    # attempt = flask.request.args.get("attempt", 1)
    attempt = 1
    match_data = app.db_client.collection("matches").document(match_id).get().to_dict()

    if not match_data:
        print("Cannot find match...skipping")
        return {"status": "skipped", "reason": "deleted"}

    if "payout_id" in match_data:
        print("Already paid out")
        return {"status": "skipped", "reason": "deleted"}

    amount = _get_stripe_price_amount(match_data, "base") * len(match_data.get("going", {}))
    if amount == 0:
        print("Nothing to payout...skipping")
        return {"status": "skipped", "reason": "no_players"}

    is_test = match_data["isTest"]
    organizer_account = app.db_client.collection("users").document(match_data["organizerId"]).get().to_dict()[
        "stripeConnectedAccountTestId" if is_test else "stripeConnectedAccountId"
    ]
    stripe.api_key = os.environ["STRIPE_KEY" if not is_test else "STRIPE_KEY_TEST"]

    # check if enough balance
    balance = stripe.Balance.retrieve(stripe_account=organizer_account)
    available_amount = balance['available'][0]['amount']

    print("trying to payout: {}, current balance {}".format(amount, available_amount))

    if available_amount >= amount:
        payout = stripe.Payout.create(
            amount=amount,
            currency='eur',
            stripe_account=organizer_account,
            metadata={"match_id": match_id, "attempt": attempt},
        )
        print("payout of {} created: {}".format(amount, payout.id))
        app.db_client.collection("matches").document(match_id).update({
            "paid_out_at": firestore.firestore.SERVER_TIMESTAMP,
            "payout_id": payout.id
        })
        send_notification_to_users(db=app.db_client,
                                   title="Your money is on the way! " + u"\U0001F4B5",
                                   body="The amount of € {:.2f} for the match on {} is on its way to your bank account"
                                   .format(amount / 100, datetime.strftime(match_data["dateTime"], "%B %-d, %Y")),
                                   data={
                                       "click_action": "FLUTTER_NOTIFICATION_CLICK",
                                       "route": "/match/" + match_id,
                                       "match_id": match_id
                                   },
                                   users=[match_data["organizerId"]])
        return {"status": "success"}
    else:
        print("not enough balance...retry in 24 hours")
        schedule_app_engine_call(
            task_name="payout_organizer_for_match_{}_attempt_number_{}".format(match_id, attempt + 1),
            endpoint="matches/{}/payout?attempt={}".format(match_id, attempt + 1),
            date_time_to_execute=datetime.now() + timedelta(days=1)
        )
        return {"status": "retry", "reason": "not_enough_balance"}


@firestore.transactional
def _cancel_match_firestore_transactional(transaction, match_doc_ref, users_stats_docs, match_id, is_test, trigger):
    stripe.api_key = os.environ["STRIPE_KEY_TEST" if is_test else "STRIPE_KEY"]

    match = get_match(match_id, is_local=True)
    to_refund = None
    if "price" in match:
        to_refund = match["price"]["basePrice"] + match["price"].get("userFee", 0)

    transaction.update(match_doc_ref, {
        "cancelledAt": datetime.now(),
        "cancelledReason": trigger
    })

    going = match.get("going", {})
    for u in going:
        # remove match in user list (if present)
        transaction.update(users_stats_docs[u], {
            u'joinedMatches.' + match_id: firestore.DELETE_FIELD
        })

        # refund
        if to_refund and "payment_intent" in going[u]:
            payment_intent = going[u]["payment_intent"]
            refund_amount = to_refund
            refund_id = None
            try:
                refund = stripe.Refund.create(payment_intent=payment_intent,
                                              amount=refund_amount,
                                              reverse_transfer=True,
                                              refund_application_fee=True)
                refund_id = refund.id
            except Exception as e:
                app.logger.error("Failed to send refund to {}".format(u))
                traceback.print_exc()

            # record transaction
            transaction_doc_ref = app.db_client.collection("matches").document(match_id).collection(
                "transactions").document()
            transaction.set(transaction_doc_ref,
                            {"type": trigger.lower() + "_cancellation", "userId": u, "createdAt": datetime.now(),
                             "paymentIntent": payment_intent,
                             "refund_id": refund_id, "moneyRefunded": refund_amount})

    user_info_message = "Your match at {} has been cancelled!".format(match["sportCenter"]["name"])
    if to_refund:
        user_info_message = user_info_message \
                            + " € {:.2f} have been refunded on your payment method".format(to_refund / 100)

    send_notification_to_users(db=app.db_client,
                               title="Match cancelled!",
                               body=user_info_message,
                               data={
                                   "click_action": "FLUTTER_NOTIFICATION_CLICK",
                                   "route": "/match/" + match_id,
                                   "match_id": match_id
                               },
                               users=list(going.keys()))

    org_info_message = "Your match at {} has been {} as you requested!".format(
        match["sportCenter"]["name"],
        "cancelled" if trigger == "manual" else "automatically cancelled")
    if to_refund:
        org_info_message = org_info_message + " All players have been refunded € {:.2f}".format(to_refund / 100)

    send_notification_to_users(db=app.db_client,
                               title="Match cancelled!",
                               body=org_info_message,
                               data={
                                   "click_action": "FLUTTER_NOTIFICATION_CLICK",
                                   "route": "/match/" + match_id,
                                   "match_id": match_id
                               },
                               users=[match["organizerId"]])


Updates = namedtuple("Updates", "match_updates users_updates users_match_stats_updates")


@bp.route("/<match_id>/stats/freeze", methods=["POST"])
def freeze_match_stats(match_id, notify=True, only_for_user=None):
    # only_for_user can be used to apply match stats only to a certain user
    match_data = get_match(match_id, is_local=True)
    updates, error = _freeze_match_stats(match_id, match_data)

    if only_for_user:
        updates = {
            only_for_user: updates[only_for_user]
        }
        print("Reducing updates to {}".format(updates))

    if error:
        return {"error": error}

    match_doc_ref = app.db_client.collection("matches").document(match_id)
    users_doc_ref = {u: app.db_client.collection("users").document(u) for u in updates}

    # write to db
    _close_rating_round_transaction(app.db_client.transaction(),
                                    match_data["dateTime"].strftime("%Y%m"),
                                    updates,
                                    match_doc_ref,
                                    users_doc_ref)
    if notify:
        _send_close_voting_notification(match_doc_ref.id,
                                        list(match_data.get("going", {}).keys()),
                                        [u for u in updates if updates[u].num_potms == 1],
                                        match_data.get("sportCenter", None))

    return {}


def _freeze_match_stats(match_id, match_data):
    if not match_data:
        return None, "not_found"
    if datetime.now(dateutil.tz.UTC) < match_data["dateTime"] + timedelta(days=1):
        return None, "too_early"
    if match_data.get("cancelledAt", None):
        return None, "cancelled"
    if match_data.get("isTest", False):
        return None, "test"

    # ratings
    ratings_doc = app.db_client.collection("ratings").document(match_id).get()
    match_stats = MatchStats(
        match_id,
        match_data.get("dateTime"),
        match_data.get("going", {}),
        ratings_doc.to_dict().get("scores", {}) if ratings_doc.to_dict() else {},
        ratings_doc.to_dict().get("skills", {}) if ratings_doc.to_dict() else {},
    )

    # score
    user_won = []
    user_draw = []
    user_lost = []
    if "score" in match_data and len(match_data["score"]) == 2:
        score_delta = match_data["score"][0] - match_data["score"][1]
        team_logic = "manual" if match_data.get("hasManualTeams", False) else "balanced"
        teams = match_data["teams"][team_logic]["players"]

        if score_delta > 0:
            user_won = teams['a']
            user_lost = teams['b']
        elif score_delta == 0:
            user_draw = teams['a'] + teams['b']
        else:
            user_won = teams['b']
            user_lost = teams['a']

    user_updates = {}

    # create updates
    for u in match_data.get("going", {}).keys():
        user_updates[u] = UserUpdates.from_single_game(
            date=match_data["dateTime"],
            score=match_stats.user_scores.get(u, None),
            wdl="w" if u in user_won else "d" if u in user_draw else "l" if u in user_lost else None,
            is_potm=u in match_stats.potms
        )

    return user_updates, None


@bp.route("/<match_id>/dynamicLink", methods=["GET"])
def test_dynamic_link(match_id):
    return flask.redirect(build_dynamic_link('http://web.nutmegapp.com/match/{}'.format(match_id)))


@firestore.transactional
def _close_rating_round_transaction(transaction,
                                    yearmonth,
                                    user_updates: Dict[str, UserUpdates],
                                    match_doc_ref,
                                    users_docs_ref):
    for u in user_updates:
        transaction.set(users_docs_ref[u], user_updates[u].to_user_document_update(), merge=True)

    for leaderboard in ["abs", yearmonth]:
        print("updating leaderboard {}".format(leaderboard))
        update_leaderboard(app, leaderboard, [match_doc_ref.id],
                           {u: user_updates[u].to_leaderboard_document_update() for u in user_updates})

    transaction.set(match_doc_ref, {"scoresComputedAt": firestore.firestore.SERVER_TIMESTAMP}, merge=True)


def _send_close_voting_notification(match_id, going_users, potms, sport_center):
    for p in potms:
        going_users.remove(p)

    sport_center_name = sport_center.get("name", "")

    send_notification_to_users(
        app.db_client,
        title="Match stats are available!",
        body="Check out the stats for the{} match".format(" " + sport_center_name),
        users=list(going_users),
        data={
            "click_action": "FLUTTER_NOTIFICATION_CLICK",
            "route": "/match/" + match_id,
            "match_id": match_id,
        }
    )

    send_notification_to_users(
        app.db_client,
        title="Congratulations! " + u"\U0001F3C6",
        body="You won the Player of the Match award for the{} match".format(" " + sport_center_name),
        users=list(potms),
        data={
            "click_action": "FLUTTER_NOTIFICATION_CLICK",
            "match_id": match_id,
            "route": "/match/" + match_id,
            "event": "potm",
        }
    )


def _remove_user_from_match_firestore(match_id, user_id):
    db = firestore.client()

    transactions_doc_ref = db.collection('matches').document(match_id).collection("transactions").document()
    user_stat_doc_ref = db.collection("users").document(user_id).collection("stats").document("match_votes")
    match_doc_ref = db.collection('matches').document(match_id)

    _remove_user_from_match_stripe_refund_firestore_transaction(db.transaction(), match_doc_ref, user_stat_doc_ref,
                                                                transactions_doc_ref, user_id, match_id)


@firestore.transactional
def _remove_user_from_match_stripe_refund_firestore_transaction(transaction, match_doc_ref, user_stat_doc_ref,
                                                                transaction_doc_ref, user_id, match_id):
    timestamp = datetime.now(tz)

    match = match_doc_ref.get(transaction=transaction).to_dict()
    payment_intent = match["going"][user_id].get("payment_intent", None)

    if not match.get("going", {}).get(user_id, None):
        raise Exception("User is not part of the match")

    # if match["dateTime"] - timedelta(hours=24) > datetime.now(utcnow):
    #     raise Exception("Cannot leave 12 hours before")

    # remove if user is in going
    transaction.update(match_doc_ref, {
        u'going.' + user_id: firestore.DELETE_FIELD
    })

    # remove match in user list
    transaction.update(user_stat_doc_ref, {
        u'joinedMatches.' + match_id: firestore.DELETE_FIELD
    })

    transaction_log = {"type": "user_left", "userId": user_id, "createdAt": timestamp}

    if payment_intent:
        # issue_refund
        stripe.api_key = os.environ["STRIPE_KEY_TEST" if match["isTest"] else "STRIPE_KEY"]
        refund_amount = _get_stripe_price_amount(match, "base")
        refund = stripe.Refund.create(payment_intent=payment_intent, amount=refund_amount, reverse_transfer=True)
        transaction_log["paymentIntent"] = payment_intent
        transaction_log["refund_id"] = refund.id
        transaction_log["moneyRefunded"] = refund_amount

    # record transaction
    transaction.set(transaction_doc_ref, transaction_log)


@firestore.transactional
def _add_user_to_match_firestore_transaction(transaction, transactions_doc_ref, user_stat_doc_ref,
                                             match_doc_ref, payment_intent, user_id, match_id):
    timestamp = datetime.now(tz)

    match = match_doc_ref.get(transaction=transaction).to_dict()

    if match.get("going", {}).get(user_id, None):
        print("User already going")
        return

    # add user to list of going
    transaction.set(match_doc_ref, {"going": {user_id: {"createdAt": timestamp, "payment_intent": payment_intent}}},
                    merge=True)

    # add match to user
    if not match["isTest"]:
        transaction.set(user_stat_doc_ref, {"joinedMatches": {match_id: match["dateTime"]}}, merge=True)

    # record transaction
    transaction.set(transactions_doc_ref, {"type": "joined", "userId": user_id, "createdAt": timestamp,
                                           "paymentIntent": payment_intent})


class MatchStatus(Enum):
    CANCELLED = "cancelled"  # match has been canceled (cancelation can triggered both before or after match start time)
    RATED = "rated"  # all players have rated and POTM has been determined
    TO_RATE = "to_rate"  # match has been played and now is in rating window; users can rate
    PLAYING = "playing"  # we are in between match start and end time
    PRE_PLAYING = "pre_playing"  # we are before match start time and match has been confirmed (automatic cancellation didn't happen)
    OPEN = "open"  # match is in the future and is open for users to join
    UNPUBLISHED = "unpublished"  # match created but not visible to others


def _get_matches_firestore(user_location=None, when=None, with_user=None, organized_by=None,
                           radius_km=None, user_id=None, version=1):
    sport_centers_cache = {}

    query = app.db_client.collection('matches')

    if with_user:
        field_path = u"going.`{}`".format(with_user)
        query = query.where(field_path, "!=", "undefined")
    if organized_by:
        query = query.where('organizerId', "==", organized_by)

    res = {}

    for m in query.stream():
        try:
            raw_data = m.to_dict()

            # time filter
            now = datetime.now(tz=pytz.UTC)
            is_outside_time_range = (
                    when == "future" and raw_data["dateTime"] < now or
                    when == "past" and raw_data["dateTime"] > now
            )

            data = _format_match_data_v2(m.id, raw_data, version)

            # location filter
            outside_radius = False
            if radius_km:
                radius_km = float(radius_km)
                if "sportCenter" in data:
                    match_location = (data["sportCenter"]["lat"], data["sportCenter"]["lng"])
                else:
                    sp = sport_centers_cache.get(data["sportCenterId"],
                                                 sportcenters.get_sportcenter(data["sportCenterId"])[0]["data"])
                    sport_centers_cache[data["sportCenterId"]] = sp
                    match_location = (sp["lat"], sp["lng"])

                distance = geopy.distance.geodesic(user_location, match_location).km
                outside_radius = distance > radius_km

            # status filter
            skip_status = organized_by is None and data["status"] == "unpublished"

            # test filter
            is_admin = user_id is not None and user_id in ["IwrZWBFb4LZl3Kto1V3oUKPnCni1",
                                                           "bQHD0EM265V6GuSZuy1uQPHzb602"]
            is_test = data.get("isTest", False)
            hide_test_match = is_test and not is_admin

            # private match
            hide_private_match = with_user is None and organized_by is None and data.get("isPrivate", False)

            if not (skip_status or outside_radius or is_outside_time_range or hide_test_match or hide_private_match):
                res[m.id] = data

        except Exception as e:
            print("Failed to read match data with id '{}".format(m.id))
            traceback.print_exc()

    return res


def _format_match_data_v2(match_id, match_data, version, add_organizer_info=False):
    # add status
    match_data["status"] = _get_status(match_data).value

    # serialize dates
    match_data = _serialize_dates(match_data)

    if version > 1:
        if "sportCenterId" in match_data:
            sportcenter = sportcenters.get_sportcenter(match_data["sportCenterId"])[0]["data"]
            sportcenter["placeId"] = match_data["sportCenterId"]
            match_data["sportCenter"] = sportcenter

    if add_organizer_info:
        try:
            if "payout_id" in match_data:
                stripe.api_key = os.environ["STRIPE_KEY_TEST" if match_data["isTest"] else "STRIPE_KEY"]
                field_name = "stripeConnectedAccountId" if not match_data["isTest"] else "stripeConnectedAccountTestId"
                stripe_connected_account_id = app.db_client.collection("users").document(match_data["organizerId"]) \
                    .get(field_paths={field_name}).to_dict()[field_name]
                info = stripe.Payout.retrieve(match_data["payout_id"], stripe_account=stripe_connected_account_id)
                match_data["payout"] = {
                    "status": info.status,
                    "amount": info.amount,
                    "arrival_date": info.arrival_date
                }
        except Exception as e:
            app.logger.error("Failed to get payout info {} for match {}".format(e, match_id))

    # todo support legacy
    if "pricePerPerson" in match_data:
        match_data["price"] = {
            "basePrice": match_data["pricePerPerson"] - match_data.get("userFee", 50),
            "userFee": match_data.get("userFee", 50)
        }

    return match_data


def _get_status(match_data):
    if match_data.get("unpublished_reason", None):
        return MatchStatus.UNPUBLISHED

    if match_data.get("cancelledAt", None):
        return MatchStatus.CANCELLED

    now = datetime.now(timezone.utc)
    start = match_data["dateTime"]
    cannot_leave_at = start - timedelta(hours=match_data.get("cancelHoursBefore", 0))
    end = start + timedelta(minutes=match_data.get("duration", 60))
    rating_window_over = end + timedelta(days=1)

    # cannot_leave_at  |  start  |  end  |  rating_window_over
    if now > rating_window_over:
        return MatchStatus.RATED
    if now > end:
        return MatchStatus.TO_RATE
    if now > start:
        return MatchStatus.PLAYING
    if now > cannot_leave_at:
        return MatchStatus.PRE_PLAYING
    return MatchStatus.OPEN


def _add_match_firestore(match_data):
    assert match_data.get("maxPlayers", None) is not None, "Required field missing"
    assert match_data.get("dateTime", None) is not None, "Required field missing"
    assert match_data.get("duration", None) is not None, "Required field missing"

    match_data["dateTime"] = dateutil.parser.isoparse(match_data["dateTime"])
    match_data["createdAt"] = firestore.firestore.SERVER_TIMESTAMP

    if "price" in match_data:
        # check if organizer can receive payments and if not do not publish yet
        organizer_data = app.db_client.collection('users').document(match_data["organizerId"]).get().to_dict()

        if organizer_data.get("stripe_status", "") != "onboarded":
            print("{} is False on organizer account: set match as unpublished")
            # add it as draft
            match_data["unpublished_reason"] = "organizer_not_onboarded"

        # create stripe object
        stripe.api_key = os.environ["STRIPE_KEY_TEST" if match_data["isTest"] else "STRIPE_KEY"]
        response = stripe.Product.create(
            name="Nutmeg Match - {} - {}".format(match_data["sportCenter"]["name"], match_data["dateTime"]),
            description="Address: " + match_data["sportCenter"]["address"]
        )
        match_data["stripeProductId"] = response["id"]
        response = stripe.Price.create(
            nickname='Standard Price',
            unit_amount=_get_stripe_price_amount(match_data, "full"),
            currency="eur",
            product=match_data["stripeProductId"]
        )
        match_data["stripePriceId"] = response.id

    doc_ref = app.db_client.collection('matches').document()
    doc_ref.set(match_data)

    # POST CREATION
    # dynamic link
    dynamic_link = build_dynamic_link('http://web.nutmegapp.com/match/{}'.format(doc_ref.id))

    app.db_client.collection("matches").document(doc_ref.id).update({
        'dynamicLink': dynamic_link,
    })

    # schedule cancellation check if required
    if "cancelHoursBefore" in match_data:
        cancellation_time = match_data["dateTime"] - timedelta(hours=match_data["cancelHoursBefore"])
        schedule_app_engine_call(
            task_name="cancel_or_confirm_match_{}".format(doc_ref.id),
            endpoint="matches/{}/confirm".format(doc_ref.id),
            date_time_to_execute=cancellation_time
        )
        schedule_app_engine_call(
            task_name="send_pre_cancellation_organizer_notification_{}".format(doc_ref.id),
            endpoint="matches/{}/tasks/precancellation".format(doc_ref.id),
            date_time_to_execute=cancellation_time - timedelta(hours=1)
        )

    # schedule close rating round
    schedule_app_engine_call(
        task_name="close_rating_round_{}".format(doc_ref.id),
        endpoint="matches/{}/stats/freeze".format(doc_ref.id),
        method=tasks_v2.HttpMethod.POST,
        date_time_to_execute=match_data["dateTime"] + timedelta(minutes=int(match_data["duration"])) + timedelta(
            days=1),
        function_payload={}
    )
    # schedule notifications
    schedule_app_engine_call(
        task_name="send_prematch_notification_{}".format(doc_ref.id),
        endpoint="matches/{}/tasks/prematch".format(doc_ref.id),
        date_time_to_execute=match_data["dateTime"] - timedelta(hours=1)
    )
    schedule_app_engine_call(
        task_name="run_post_match_tasks_{}".format(doc_ref.id),
        endpoint="matches/{}/tasks/postmatch".format(doc_ref.id),
        date_time_to_execute=match_data["dateTime"] + timedelta(minutes=int(match_data["duration"])) + timedelta(
            hours=1)
    )

    return doc_ref.id


def _get_stripe_price_amount(match_data, type):
    base_price = 0
    full_price = 0
    if "pricePerPerson" in match_data:
        base_price = match_data["pricePerPerson"]
        full_price = base_price + 50
    elif "price" in match_data:
        base_price = match_data["price"]["basePrice"]
        full_price = match_data["price"]["basePrice"] + match_data["price"]["userFee"]
    return base_price if type == "base" else full_price


def delete_tests():
    for m in app.db_client.collection("matches").where("isTest", "==", True).get():
        app.db_client.collection("matches").document(m.id).delete()


def _update_user_account(user_id, is_test, match_id, manage_payments):
    stripe.api_key = os.environ["STRIPE_KEY_TEST" if is_test else "STRIPE_KEY"]
    organizer_id_field_name = "stripeConnectedAccountId" if not is_test else "stripeConnectedAccountTestId"

    # add to created matches
    user_doc_ref = app.db_client.collection('users').document(user_id)
    organised_list_field_name = "created_matches" if not is_test else "created_test_matches"
    user_updates = {
        "{}.{}".format(organised_list_field_name, match_id): firestore.firestore.SERVER_TIMESTAMP
    }

    if manage_payments:
        # check if we need to create a stripe connected account
        user_data = user_doc_ref.get().to_dict()
        if organizer_id_field_name in user_data:
            print("{} already created".format(organizer_id_field_name))
        else:
            response = stripe.Account.create(
                type="express",
                country="NL",
                capabilities={
                    "transfers": {"requested": True},
                },
                business_type="individual",
                business_profile={
                    "product_description": "Nutmeg football matches"
                },
                metadata={
                    "userId": user_id
                },
                settings={
                    "payouts": {
                        "debit_negative_balances": True,
                        "schedule": {
                            "interval": "manual"
                        }
                    }
                }
            )
            user_updates[organizer_id_field_name] = response.id
            user_updates["stripe_status"] = "needs_onboarding"

    user_doc_ref.update(user_updates)


class MatchStats:

    def __init__(self,
                 match_id,
                 date,
                 going: List[str],
                 raw_scores: Dict[str, Dict[str, float]],
                 skills_scores: Dict[str, Dict[str, List[str]]]):
        self.id = match_id
        self.date = date
        self.going = going
        self.raw_scores = raw_scores
        self.raw_skill_scores = skills_scores

        self.user_scores = self.compute_user_scores()
        self.potms = self.compute_potms()
        self.user_skills = self.compute_user_skills()

    def compute_user_scores(self) -> Dict[str, float]:
        user_scores = {}
        for u in self.raw_scores:
            positive_scores = [v for v in self.raw_scores[u].values() if v > 0]
            if len(positive_scores) > 1:
                user_scores[u] = sum(positive_scores) / len(positive_scores)
        return user_scores

    def compute_user_skills(self) -> Dict[str, Dict[str, int]]:
        user_skill_scores = {}

        for u in self.raw_skill_scores:
            if len(self.raw_scores[u]) > 1:
                for _, skills in self.raw_skill_scores[u].items():
                    for s in skills:
                        if u not in user_skill_scores:
                            user_skill_scores[u] = {}
                        user_skill_scores[u][s] = user_skill_scores[u].get(s, 0) + 1

        return user_skill_scores

    def compute_potms(self) -> List[str]:
        if len(self.user_scores) == 0:
            return []
        sorted_user_scores = sorted(self.user_scores.items(), reverse=True, key=lambda x: x[1])
        potm_score = sorted_user_scores[0][1]
        potms = [x[0] for x in sorted_user_scores if x[1] == potm_score]
        # for now, one POTM
        if len(potms) > 1:
            return []
        return potms

    def __repr__(self):
        return "{}\n{}\n{}".format(str(self.user_scores), str(self.potms), str(self.user_skills))


if __name__ == '__main__':
    firebase_admin.initialize_app()
    app = Flask()
    app.db_client = firestore.client()

    with app.app_context():
        # add_user_to_match("0OsielJQ2ZCBIDatvB8h", user_id="5NeACflel8NNpGnNR3W2ikbPbtB2", local=True)
        print(freeze_match_stats("vbNkQCrS9imPXz9CgOuv"))

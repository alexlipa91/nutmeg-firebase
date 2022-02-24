import firebase_admin

from add_rating import add_rating_impl
from get_users_to_rate import get_users_to_rate_impl

firebase_admin.initialize_app()


def add_rating(request): add_rating_impl(request)


def get_users_to_rate(request): get_users_to_rate_impl(request)

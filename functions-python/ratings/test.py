# from unittest.mock import Mock
#
# from mockfirestore import MockFirestore
#
# import main
# import mock


# def test_add_rating():
#     db = MockFirestore()
#     main._get_db = mock.Mock(return_value=db)
#
#     data = {'data': {"user_id": "a", "match_id": "m", "user_rated_id": "b", "score": 2}}
#     req = Mock(get_json=Mock(return_value=data), args=data)
#
#     # Call tested function
#     assert main.add_rating(req)


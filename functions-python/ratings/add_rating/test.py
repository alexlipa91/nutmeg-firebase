# import unittest
# from unittest.mock import Mock
#
# from mockfirestore import MockFirestore
#
# import main
# import mock
#
#
# class MyTestCase(unittest.TestCase):
#
#     def test_add_rating(self):
#         db = MockFirestore()
#         main._get_db = mock.Mock(return_value=db)
#
#         data = {'data': {"user_id": "a", "match_id": "m", "user_rated_id": "b", "score": 2}}
#         req = Mock(get_json=Mock(return_value=data), args=data)
#         main.add_rating(req)
#
#         assert db.collection("ratings").document("m").get().to_dict() == {'scores': {'a': {'b': 2}}}
#
#         data = {'data': {"user_id": "a", "match_id": "m", "user_rated_id": "c", "score": 3}}
#         req = Mock(get_json=Mock(return_value=data), args=data)
#         main.add_rating(req)
#
#         assert db.collection("ratings").document("m").get().to_dict() == {'scores': {'a': {'b': 2, 'c': 3} } }
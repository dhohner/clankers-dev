import unittest

from shop.user_service import describe_user, fetch_user_profile, list_user_emails


class FetchUserProfileTest(unittest.TestCase):
    def test_full_name(self):
        raw = {"id": 1, "first_name": " Ada ", "last_name": "Lovelace", "birthday": "1815-12-10"}
        self.assertEqual(
            fetch_user_profile(raw),
            {"id": 1, "display_name": "Ada Lovelace", "birthday": "1815-12-10"},
        )

    def test_missing_names(self):
        raw = {"id": 2, "first_name": "  ", "last_name": None}
        self.assertEqual(
            fetch_user_profile(raw),
            {"id": 2, "display_name": "Anonymous", "birthday": None},
        )

    def test_nickname_wins(self):
        raw = {"id": 3, "first_name": "Grace", "last_name": "Hopper", "nickname": " Amazing Grace "}
        self.assertEqual(fetch_user_profile(raw)["display_name"], "Amazing Grace")

    def test_blank_nickname_is_ignored(self):
        raw = {"id": 4, "first_name": "Grace", "nickname": "  "}
        self.assertEqual(fetch_user_profile(raw)["display_name"], "Grace")


class UserHelpersTest(unittest.TestCase):
    def test_list_user_emails(self):
        self.assertEqual(list_user_emails([{"email": "a@example.com"}, {}]), ["a@example.com"])

    def test_describe_user(self):
        self.assertEqual(describe_user({"active": True, "admin": True}), "active admin")
        self.assertEqual(describe_user({"active": False}), "inactive user")

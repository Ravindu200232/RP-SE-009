"""Accounts, sessions, ownership and each person's deployment accounts.

One machine, many people. What these check is that nothing crosses between
them: a session is a hash rather than a usable token, a project's owner never
moves, something nobody owns is only the admin's, and a saved GitHub or Vercel
token is unreadable in the database it is stored in.

The store runs against an in-memory stand-in for MongoDB, so the suite needs no
database, and the encryption key comes from the environment rather than the
machine's key file.
"""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cryptography.fernet import Fernet
from pymongo.errors import DuplicateKeyError

from test import _support                                            # noqa: F401
from server_modules.services import auth_db, secret_box


class FakeCollection:
    """The slice of a pymongo collection this store actually uses."""

    def __init__(self):
        self.docs = []
        self.unique = set()

    def create_index(self, field, unique=False):
        if unique:
            self.unique.add(field)

    @staticmethod
    def _matches(doc, query):
        return all(doc.get(key) == value for key, value in (query or {}).items())

    def find_one(self, query=None):
        return next((dict(doc) for doc in self.docs if self._matches(doc, query)), None)

    def find(self, query=None):
        return [dict(doc) for doc in self.docs if self._matches(doc, query)]

    def count_documents(self, query=None):
        return len(self.find(query))

    def insert_one(self, doc):
        for field in self.unique:
            if field in doc and any(other.get(field) == doc[field] for other in self.docs):
                raise DuplicateKeyError(f"duplicate {field}")
        self.docs.append(dict(doc))

    def update_one(self, query, update, upsert=False):
        doc = next((doc for doc in self.docs if self._matches(doc, query)), None)
        if doc is None:
            if not upsert:
                return
            doc = dict(query)
            self.docs.append(doc)
        doc.update(update.get("$set") or {})
        for key in update.get("$unset") or {}:
            doc.pop(key, None)

    def delete_one(self, query):
        for index, doc in enumerate(self.docs):
            if self._matches(doc, query):
                self.docs.pop(index)
                return

    def delete_many(self, query):
        self.docs = [doc for doc in self.docs if not self._matches(doc, query)]


class FakeDb:
    def __init__(self):
        self.collections = {}

    def __getitem__(self, name):
        return self.collections.setdefault(name, FakeCollection())

    def __getattr__(self, name):
        if name.startswith("_") or name == "collections":
            raise AttributeError(name)
        return self[name]


class AuthStoreTestCase(unittest.TestCase):
    def setUp(self):
        self.db = FakeDb()
        auth_db.use_db(self.db)
        self.addCleanup(auth_db.use_db, None)
        # A key of this run's own: the machine's key file is never touched.
        environment = mock.patch.dict(
            os.environ, {"AGENTFORGE_SECRET_KEY": Fernet.generate_key().decode()})
        environment.start()
        os.environ.pop("AGENTFORGE_ADMIN_EMAILS", None)
        self.addCleanup(environment.stop)
        secret_box.reset()
        self.addCleanup(secret_box.reset)

    def signup(self, username="ravindu", password="a-good-password"):
        return auth_db.signup_user(username, f"{username}@example.com", password, username)


class SignUpTests(AuthStoreTestCase):
    def test_signing_up_signs_in_and_the_password_is_not_stored(self):
        result = self.signup()
        self.assertTrue(result["ok"])
        self.assertEqual(auth_db.get_user_by_token(result["token"])["username"], "ravindu")
        stored = self.db.users.find_one({"username": "ravindu"})
        self.assertNotIn("a-good-password", str(stored))

    def test_a_short_password_is_refused(self):
        self.assertIn("password", self.signup(password="short").get("error", "").lower())
        self.assertIsNone(self.db.users.find_one({"username": "ravindu"}))

    def test_a_name_or_address_is_only_registered_once(self):
        self.signup()
        again = auth_db.signup_user("ravindu", "other@example.com", "a-good-password")
        self.assertIn("error", again)

    def test_the_first_account_adopts_what_was_here_before_accounts(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "shop").mkdir()
            with mock.patch.object(auth_db, "projects_dir", Path(folder)):
                first = self.signup()
            second = self.signup("dinuka")
        self.assertEqual(auth_db.owner_of("project", "shop"), first["user"]["id"])
        self.assertFalse(auth_db.owns(second["user"], "project", "shop"))


class SignInTests(AuthStoreTestCase):
    def test_the_wrong_password_says_nothing_about_which_half_was_wrong(self):
        self.signup()
        missing = auth_db.login_user("nobody", "a-good-password")
        wrong = auth_db.login_user("ravindu", "not-the-password")
        self.assertEqual(missing["error"], wrong["error"])

    def test_guessing_stops_being_answered(self):
        self.signup()
        for _ in range(auth_db.MAX_FAILURES):
            auth_db.login_user("ravindu", "not-the-password")
        refused = auth_db.login_user("ravindu", "a-good-password")
        self.assertIn("wait", refused.get("error", "").lower())

    def test_a_session_is_kept_as_a_hash_and_ends_on_sign_out(self):
        token = self.signup()["token"]
        session = self.db.sessions.find_one({})
        self.assertNotIn(token, str(session))
        auth_db.logout_user(token)
        self.assertIsNone(auth_db.get_user_by_token(token))

    def test_an_expired_session_signs_nobody_in(self):
        token = self.signup()["token"]
        auth_db._user_cache.clear()
        self.db.sessions.update_one({}, {"$set": {"expires_at": auth_db._now()}})
        self.assertIsNone(auth_db.get_user_by_token(token))


class OwnershipTests(AuthStoreTestCase):
    def test_what_one_person_builds_is_not_another_persons(self):
        mine = self.signup()["user"]
        theirs = self.signup("dinuka")["user"]
        self.assertTrue(auth_db.claim("project", "shop", mine["id"]))
        self.assertTrue(auth_db.owns(mine, "project", "shop"))
        self.assertFalse(auth_db.owns(theirs, "project", "shop"))

    def test_a_claim_never_moves_a_project_to_someone_else(self):
        mine = self.signup()["user"]
        theirs = self.signup("dinuka")["user"]
        auth_db.claim("project", "shop", mine["id"])
        self.assertFalse(auth_db.claim("project", "shop", theirs["id"]))
        self.assertEqual(auth_db.owner_of("project", "shop"), mine["id"])

    def test_what_nobody_owns_is_the_admins_alone(self):
        admin = self.signup()["user"]
        other = self.signup("dinuka")["user"]
        self.assertTrue(admin["admin"])
        self.assertFalse(other["admin"])
        self.assertTrue(auth_db.owns(admin, "project", "from-before"))
        self.assertFalse(auth_db.owns(other, "project", "from-before"))

    def test_a_deleted_project_lets_the_name_be_claimed_again(self):
        mine = self.signup()["user"]
        theirs = self.signup("dinuka")["user"]
        auth_db.claim("project", "shop", mine["id"])
        auth_db.release("project", "shop")
        self.assertTrue(auth_db.claim("project", "shop", theirs["id"]))

    def test_the_named_admin_wins_over_the_first_account(self):
        first = self.signup()["user"]
        second = self.signup("dinuka")["user"]
        with mock.patch.dict(os.environ, {"AGENTFORGE_ADMIN_EMAILS": "dinuka@example.com"}):
            auth_db._user_cache.clear()
            self.assertFalse(auth_db._is_admin({"_id": first["id"], "email": first["email"]}))
            self.assertTrue(auth_db._is_admin({"_id": second["id"], "email": second["email"]}))


class DeploymentAccountTests(AuthStoreTestCase):
    def test_a_token_comes_back_but_is_unreadable_in_the_database(self):
        me = self.signup()["user"]
        auth_db.save_user_settings(me["id"], {"github_token": "ghp_secret_value",
                                              "aws_profile": "af-1-console"})
        self.assertEqual(auth_db.user_settings(me["id"])["github_token"], "ghp_secret_value")
        stored = self.db.user_credentials.find_one({"user_id": me["id"]})
        self.assertNotIn("ghp_secret_value", str(stored))
        self.assertEqual(stored["plain"]["aws_profile"], "af-1-console")

    def test_one_persons_accounts_are_never_anothers(self):
        mine = self.signup()["user"]
        theirs = self.signup("dinuka")["user"]
        auth_db.save_user_settings(mine["id"], {"vercel_token": "mine"})
        self.assertEqual(auth_db.deploy_secrets(theirs["id"]),
                         {"github_token": "", "vercel_token": ""})
        self.assertEqual(auth_db.deploy_secrets(mine["id"])["vercel_token"], "mine")

    def test_saving_one_account_leaves_the_others_alone(self):
        me = self.signup()["user"]
        auth_db.save_user_settings(me["id"], {"github_token": "gh", "vercel_token": "vc"})
        auth_db.save_user_settings(me["id"], {"vercel_token": ""})
        saved = auth_db.user_settings(me["id"])
        self.assertEqual(saved["github_token"], "gh")
        self.assertEqual(saved["vercel_token"], "")

    def test_a_secret_sealed_with_another_key_reads_as_nothing(self):
        me = self.signup()["user"]
        auth_db.save_user_settings(me["id"], {"github_token": "gh"})
        with mock.patch.dict(os.environ,
                             {"AGENTFORGE_SECRET_KEY": Fernet.generate_key().decode()}):
            secret_box.reset()
            self.assertEqual(auth_db.user_settings(me["id"])["github_token"], "")


if __name__ == "__main__":
    unittest.main()

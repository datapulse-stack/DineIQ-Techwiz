"""security tests: password hashing, auth rejection, and role permissions."""
import auth


def test_passwords_are_hashed_not_plaintext(tmp_path, monkeypatch):
    # point the auth module at a throwaway db so we don't touch the real one
    monkeypatch.setattr(auth, "DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setattr(auth, "SECRET_PATH", tmp_path / "secret.key")
    auth.init_db()
    ok, _ = auth.create_user("Tester", "tester@dineiq.local", "s3cret!", "Analyst")
    assert ok
    user = auth.authenticate("tester@dineiq.local", "s3cret!")
    assert user is not None
    assert user["password_hash"] != "s3cret!", "password stored in plaintext!"


def test_wrong_password_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, "DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setattr(auth, "SECRET_PATH", tmp_path / "secret.key")
    auth.init_db()
    auth.create_user("Tester", "t2@dineiq.local", "right-pass", "Analyst")
    assert auth.authenticate("t2@dineiq.local", "wrong-pass") is None


def test_role_permissions():
    # analyst can view but not export or administer
    assert auth.can("Analyst", "view")
    assert not auth.can("Analyst", "export")
    assert not auth.can("Analyst", "admin")
    # manager can export, not administer
    assert auth.can("Manager", "export")
    assert not auth.can("Manager", "admin")
    # admin can do everything
    assert auth.can("Admin", "admin")


def test_password_reset_changes_hash(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, "DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setattr(auth, "SECRET_PATH", tmp_path / "secret.key")
    auth.init_db()
    auth.create_user("Tester", "t3@dineiq.local", "old-pass", "Manager")
    assert auth.authenticate("t3@dineiq.local", "old-pass")
    auth.set_password("t3@dineiq.local", "new-pass")
    assert auth.authenticate("t3@dineiq.local", "old-pass") is None
    assert auth.authenticate("t3@dineiq.local", "new-pass")

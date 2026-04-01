import json
import os
import pytest

from imap2gmail.imapreader import ImapMessageID, ImapMessageIDList, ImapCredentials


# --- ImapMessageID ---

class TestImapMessageID:
    def test_init(self):
        msg = ImapMessageID("INBOX", 42)
        assert msg._folder == "INBOX"
        assert msg._id == 42

    def test_json_serialize(self):
        msg = ImapMessageID("Sent", 7)
        result = msg.json_serialize()
        assert result == {"folder": "Sent", "id": 7}

    def test_iter(self):
        msg = ImapMessageID("Drafts", 3)
        as_dict = dict(msg)
        assert as_dict == {"folder": "Drafts", "id": 3}


# --- ImapMessageIDList ---

class TestImapMessageIDList:
    def test_empty_by_default(self):
        lst = ImapMessageIDList()
        assert lst._foldersidslist == {}

    def test_set_folders(self):
        lst = ImapMessageIDList()
        lst.setFolders(["INBOX", "Sent"])
        assert "INBOX" in lst._foldersidslist
        assert "Sent" in lst._foldersidslist
        assert lst._foldersidslist["INBOX"] == []

    def test_set_folders_preserves_existing(self):
        lst = ImapMessageIDList()
        lst._foldersidslist["INBOX"] = [1, 2]
        lst.setFolders(["INBOX", "Sent"])
        assert lst._foldersidslist["INBOX"] == [1, 2]
        assert lst._foldersidslist["Sent"] == []

    def test_contains_true(self):
        lst = ImapMessageIDList()
        lst._foldersidslist["INBOX"] = [1, 2, 3]
        assert lst.contains(ImapMessageID("INBOX", 2)) is True

    def test_contains_false_wrong_id(self):
        lst = ImapMessageIDList()
        lst._foldersidslist["INBOX"] = [1, 2, 3]
        assert lst.contains(ImapMessageID("INBOX", 99)) is False

    def test_contains_false_wrong_folder(self):
        lst = ImapMessageIDList()
        lst._foldersidslist["INBOX"] = [1, 2, 3]
        assert lst.contains(ImapMessageID("Sent", 1)) is False

    def test_contains_empty_list(self):
        lst = ImapMessageIDList()
        assert lst.contains(ImapMessageID("INBOX", 1)) is False

    def test_write_and_load_roundtrip(self, tmp_path):
        filepath = str(tmp_path / "cache.json")

        lst = ImapMessageIDList()
        lst._foldersidslist = {
            "INBOX": [1, 2, 3],
            "Sent": [10, 20],
        }
        lst.writeJSonFile(filepath)

        loaded = ImapMessageIDList()
        loaded.loadJsonFile(filepath)

        assert loaded.contains(ImapMessageID("INBOX", 1))
        assert loaded.contains(ImapMessageID("INBOX", 2))
        assert loaded.contains(ImapMessageID("INBOX", 3))
        assert loaded.contains(ImapMessageID("Sent", 10))
        assert loaded.contains(ImapMessageID("Sent", 20))
        assert not loaded.contains(ImapMessageID("INBOX", 99))

    def test_load_nonexistent_file(self, tmp_path):
        filepath = str(tmp_path / "does_not_exist.json")
        lst = ImapMessageIDList()
        lst.loadJsonFile(filepath)
        assert lst._foldersidslist == {}

    def test_load_invalid_json(self, tmp_path):
        filepath = str(tmp_path / "bad.json")
        with open(filepath, 'w') as f:
            f.write("not valid json{{{")
        lst = ImapMessageIDList()
        lst.loadJsonFile(filepath)
        assert lst._foldersidslist == {}

    def test_write_empty_list(self, tmp_path):
        filepath = str(tmp_path / "empty.json")
        lst = ImapMessageIDList()
        lst.writeJSonFile(filepath)

        with open(filepath) as f:
            data = json.load(f)
        assert data == []


# --- ImapCredentials ---

class TestImapCredentials:
    def test_defaults(self):
        creds = ImapCredentials()
        assert creds._host == ''
        assert creds._user == ''
        assert creds._password == ''

    def test_isOK_false_on_default(self):
        creds = ImapCredentials()
        assert creds.isOK() is False

    def test_load_valid_file(self, tmp_path):
        filepath = str(tmp_path / "creds.json")
        data = {"host": "imap.example.com", "user": "alice", "password": "s3cret"}
        with open(filepath, 'w') as f:
            json.dump(data, f)

        creds = ImapCredentials()
        result = creds.loadJsonFile(filepath)
        assert result is True
        assert creds._host == "imap.example.com"
        assert creds._user == "alice"
        assert creds._password == "s3cret"
        assert creds.isOK() is True

    def test_load_missing_file(self, tmp_path):
        filepath = str(tmp_path / "missing.json")
        creds = ImapCredentials()
        result = creds.loadJsonFile(filepath)
        assert result is False
        assert creds.isOK() is False

    def test_isOK_false_with_empty_host(self, tmp_path):
        filepath = str(tmp_path / "creds.json")
        data = {"host": "", "user": "alice", "password": "s3cret"}
        with open(filepath, 'w') as f:
            json.dump(data, f)

        creds = ImapCredentials()
        creds.loadJsonFile(filepath)
        assert creds.isOK() is False

    def test_isOK_false_with_empty_password(self, tmp_path):
        filepath = str(tmp_path / "creds.json")
        data = {"host": "imap.example.com", "user": "alice", "password": ""}
        with open(filepath, 'w') as f:
            json.dump(data, f)

        creds = ImapCredentials()
        creds.loadJsonFile(filepath)
        assert creds.isOK() is False

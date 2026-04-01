import os
import stat
import pytest

from imap2gmail.gmailimapimporter import GMailLabel, GMailLabels, GMailImapImporter


# --- GMailLabel ---

class TestGMailLabel:
    def test_init(self):
        label = GMailLabel("Inbox", "INBOX", "INBOX_ID")
        assert label._name == "Inbox"
        assert label._IMAPfolder == "INBOX"
        assert label._GMailID == "INBOX_ID"


# --- GMailLabels ---

class TestGMailLabels:
    def _make_labels(self):
        labels = GMailLabels()
        labels._labels = [
            GMailLabel("INBOX", "INBOX", "id_inbox"),
            GMailLabel("Sent Mail", "Sent", "id_sent"),
            GMailLabel("Work", "Work", "id_work"),
        ]
        return labels

    def test_find_by_folder_exact(self):
        labels = self._make_labels()
        result = labels.findLabelForImapFolder("Sent")
        assert result._GMailID == "id_sent"

    def test_find_by_folder_case_insensitive(self):
        labels = self._make_labels()
        result = labels.findLabelForImapFolder("inbox")
        assert result._GMailID == "id_inbox"

    def test_find_by_name_case_insensitive(self):
        labels = self._make_labels()
        result = labels.findLabelForImapFolder("sent mail")
        assert result._GMailID == "id_sent"

    def test_find_not_found(self):
        labels = self._make_labels()
        result = labels.findLabelForImapFolder("Nonexistent")
        assert result is None

    def test_empty_labels(self):
        labels = GMailLabels()
        assert labels.findLabelForImapFolder("INBOX") is None


# --- GMailImapImporter._cleanFolderName ---

class TestCleanFolderName:
    def test_dots_to_slashes(self):
        assert GMailImapImporter._cleanFolderName("INBOX.Subfolder") == "INBOX/Subfolder"

    def test_multiple_dots(self):
        assert GMailImapImporter._cleanFolderName("A.B.C") == "A/B/C"

    def test_strips_whitespace(self):
        assert GMailImapImporter._cleanFolderName("  INBOX  ") == "INBOX"

    def test_collapses_multiple_spaces(self):
        assert GMailImapImporter._cleanFolderName("My   Folder") == "My Folder"

    def test_tabs_and_newlines(self):
        assert GMailImapImporter._cleanFolderName("My\t\nFolder") == "My Folder"

    def test_plain_name(self):
        assert GMailImapImporter._cleanFolderName("INBOX") == "INBOX"

    def test_empty_string(self):
        assert GMailImapImporter._cleanFolderName("") == ""

    def test_combined(self):
        assert GMailImapImporter._cleanFolderName("  A.B  . C  ") == "A/B / C"


# --- GMailImapImporter._writeToken ---

class TestWriteToken:
    def test_token_file_permissions(self, tmp_path, monkeypatch):
        token_path = str(tmp_path / "gmail_token.json")
        monkeypatch.setattr(GMailImapImporter, 'TOKENFILE', token_path)

        importer = GMailImapImporter()

        # Create a minimal mock for _creds
        class FakeCreds:
            def to_json(self):
                return '{"token": "fake"}'

        importer._creds = FakeCreds()
        importer._writeToken()

        assert os.path.exists(token_path)
        file_stat = os.stat(token_path)
        mode = stat.S_IMODE(file_stat.st_mode)
        assert mode == 0o600

    def test_token_file_content(self, tmp_path, monkeypatch):
        token_path = str(tmp_path / "gmail_token.json")
        monkeypatch.setattr(GMailImapImporter, 'TOKENFILE', token_path)

        importer = GMailImapImporter()

        class FakeCreds:
            def to_json(self):
                return '{"token": "test123"}'

        importer._creds = FakeCreds()
        importer._writeToken()

        with open(token_path) as f:
            assert f.read() == '{"token": "test123"}'

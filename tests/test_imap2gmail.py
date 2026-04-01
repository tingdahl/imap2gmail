import os
import stat
import pytest

from imap2gmail.imap2gmail import checkFileAccess


class TestCheckFileAccess:
    def test_none_filename_returns_true(self):
        assert checkFileAccess(None, True) is True
        assert checkFileAccess(None, False) is True

    def test_read_existing_readable_file(self, tmp_path):
        f = tmp_path / "readable.txt"
        f.write_text("hello")
        assert checkFileAccess(str(f), True) is True

    def test_read_nonexistent_file(self, tmp_path):
        f = str(tmp_path / "missing.txt")
        assert checkFileAccess(f, True) is False

    def test_read_unreadable_file(self, tmp_path):
        f = tmp_path / "noperm.txt"
        f.write_text("hello")
        f.chmod(0o000)
        try:
            assert checkFileAccess(str(f), True) is False
        finally:
            f.chmod(0o644)

    def test_write_existing_writable_file(self, tmp_path):
        f = tmp_path / "writable.txt"
        f.write_text("hello")
        assert checkFileAccess(str(f), False) is True

    def test_write_existing_readonly_file(self, tmp_path):
        f = tmp_path / "readonly.txt"
        f.write_text("hello")
        f.chmod(stat.S_IRUSR)
        try:
            assert checkFileAccess(str(f), False) is False
        finally:
            f.chmod(0o644)

    def test_write_new_file_in_writable_dir(self, tmp_path):
        f = str(tmp_path / "newfile.txt")
        assert checkFileAccess(f, False) is True

    def test_write_new_file_in_readonly_dir(self, tmp_path):
        readonly_dir = tmp_path / "nowrite"
        readonly_dir.mkdir()
        readonly_dir.chmod(stat.S_IRUSR | stat.S_IXUSR)
        f = str(readonly_dir / "newfile.txt")
        try:
            assert checkFileAccess(f, False) is False
        finally:
            readonly_dir.chmod(0o755)

    def test_write_new_file_empty_dirname(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert checkFileAccess("newfile.txt", False) is True

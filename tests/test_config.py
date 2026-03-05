"""Tests for credential storage."""

import json
import os
import stat

import pytest

from mmchat.config import clear_config, get_credentials, load_config, save_config


@pytest.fixture(autouse=True)
def tmp_config(tmp_path, monkeypatch):
    """Use a temp dir for config in all tests."""
    config_path = tmp_path / "config.json"
    monkeypatch.setenv("MM_CONFIG_PATH", str(config_path))
    # Clear any MM env vars that might interfere
    monkeypatch.delenv("MATTERMOST_URL", raising=False)
    monkeypatch.delenv("MATTERMOST_TOKEN", raising=False)
    monkeypatch.delenv("MATTERMOST_TEAM", raising=False)
    return config_path


class TestSaveLoad:
    def test_save_and_load(self, tmp_config):
        save_config("https://mm.test", "password", "tok123", "myteam")
        config = load_config()
        assert config["url"] == "https://mm.test"
        assert config["auth_method"] == "password"
        assert config["token"] == "tok123"
        assert config["team"] == "myteam"

    def test_file_permissions(self, tmp_config):
        save_config("https://mm.test", "password", "tok123")
        mode = os.stat(tmp_config).st_mode
        assert stat.S_IMODE(mode) == 0o600

    def test_dir_permissions(self, tmp_config):
        # Use a nested path to test dir creation
        nested = tmp_config.parent / "sub" / "config.json"
        os.environ["MM_CONFIG_PATH"] = str(nested)
        save_config("https://mm.test", "password", "tok123")
        # Parent dir should be 700
        dir_mode = os.stat(nested.parent).st_mode
        assert stat.S_IMODE(dir_mode) == 0o700

    def test_no_team(self, tmp_config):
        save_config("https://mm.test", "token", "pat123")
        config = load_config()
        assert "team" not in config

    def test_load_missing_file(self, tmp_config):
        config = load_config()
        assert config == {}


class TestClear:
    def test_clear(self, tmp_config):
        save_config("https://mm.test", "password", "tok123")
        assert tmp_config.exists()
        clear_config()
        assert not tmp_config.exists()

    def test_clear_missing(self, tmp_config):
        # Should not raise
        clear_config()


class TestGetCredentials:
    def test_from_config(self, tmp_config):
        save_config("https://mm.test", "password", "tok123")
        creds = get_credentials()
        assert creds["url"] == "https://mm.test"
        assert creds["token"] == "tok123"

    def test_env_override(self, tmp_config, monkeypatch):
        save_config("https://mm.test", "password", "tok123")
        monkeypatch.setenv("MATTERMOST_URL", "https://env.test")
        monkeypatch.setenv("MATTERMOST_TOKEN", "envtok")
        creds = get_credentials()
        assert creds["url"] == "https://env.test"
        assert creds["token"] == "envtok"
        assert creds["auth_method"] == "env"

    def test_partial_env_override(self, tmp_config, monkeypatch):
        save_config("https://mm.test", "password", "tok123")
        monkeypatch.setenv("MATTERMOST_TOKEN", "envtok")
        creds = get_credentials()
        # URL from config, token from env
        assert creds["url"] == "https://mm.test"
        assert creds["token"] == "envtok"

    def test_no_creds_raises(self, tmp_config):
        from mmchat.config import ConfigError

        with pytest.raises(ConfigError, match="Not authenticated"):
            get_credentials()

    def test_env_team(self, tmp_config, monkeypatch):
        monkeypatch.setenv("MATTERMOST_URL", "https://env.test")
        monkeypatch.setenv("MATTERMOST_TOKEN", "envtok")
        monkeypatch.setenv("MATTERMOST_TEAM", "myteam")
        creds = get_credentials()
        assert creds["team"] == "myteam"

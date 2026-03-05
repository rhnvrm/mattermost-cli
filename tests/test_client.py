"""Tests for client URL parsing and team resolution."""

from mmchat.client import create_driver, Team, get_teams


class TestCreateDriver:
    def test_full_url(self):
        d = create_driver("https://chat.example.com", "tok123")
        assert d.options["scheme"] == "https"
        assert d.options["url"] == "chat.example.com"
        assert d.options["port"] == 443

    def test_http_url(self):
        d = create_driver("http://localhost:8065", "tok123")
        assert d.options["scheme"] == "http"
        assert d.options["url"] == "localhost"
        assert d.options["port"] == 8065

    def test_no_scheme(self):
        d = create_driver("chat.example.com", "tok123")
        assert d.options["scheme"] == "https"
        assert d.options["url"] == "chat.example.com"
        assert d.options["port"] == 443

    def test_custom_port(self):
        d = create_driver("https://mm.internal:9443", "tok123")
        assert d.options["port"] == 9443

    def test_http_default_port(self):
        d = create_driver("http://localhost", "tok123")
        assert d.options["port"] == 80

    def test_token_set(self):
        d = create_driver("https://mm.test", "mytoken")
        assert d.options["token"] == "mytoken"

    def test_password_options(self):
        d = create_driver("https://mm.test", "", login_id="user", password="pass", mfa_token="123456")
        assert d.options["login_id"] == "user"
        assert d.options["password"] == "pass"
        assert d.options["mfa_token"] == "123456"

    def test_debug_always_false(self):
        d = create_driver("https://mm.test", "tok")
        assert d.options["debug"] is False


class TestFormatters:
    """Test formatter output shapes."""

    def test_channels_md_empty(self):
        from mmchat.formatters import format_channels_md

        assert format_channels_md([]) == "No channels found."

    def test_channels_md_output(self):
        from mmchat.formatters import format_channels_md

        channels = [
            {"id": "c1", "display_name": "general", "name": "general", "type": "O", "team_name": "Tech"},
            {"id": "c2", "display_name": "@bob", "name": "dm123", "type": "D", "team_name": "Tech"},
        ]
        result = format_channels_md(channels)
        assert "| general | Public | Tech |" in result
        assert "| @bob | DM | Tech |" in result

    def test_channels_json_format(self):
        import json
        from mmchat.formatters import format_channels_json

        channels = [
            {"id": "c1", "display_name": "general", "name": "general", "type": "O",
             "team_name": "Tech", "purpose": "General chat", "header": ""},
        ]
        result = json.loads(format_channels_json(channels))
        assert result[0]["name"] == "general"
        assert result[0]["type"] == "Public"
        assert result[0]["purpose"] == "General chat"
        assert "header" not in result[0]  # empty header excluded

    def test_unread_md_empty(self):
        from mmchat.formatters import format_unread_md

        assert format_unread_md([]) == "No unread messages."

    def test_unread_json_iso_timestamp(self):
        import json
        from mmchat.formatters import format_unread_json

        unreads = [
            {"channel_id": "c1", "display_name": "general", "type": "O",
             "unread": 5, "mentions": 2, "team_name": "Tech", "last_post_at": 1772490600000},
        ]
        result = json.loads(format_unread_json(unreads))
        assert result[0]["channel"] == "general"
        assert result[0]["last_post_at"].endswith("Z")
        assert "T" in result[0]["last_post_at"]

    def test_unread_md_mentions_bold(self):
        from mmchat.formatters import format_unread_md

        unreads = [
            {"display_name": "general", "unread": 5, "mentions": 2, "team_name": "Tech"},
        ]
        result = format_unread_md(unreads)
        assert "**2**" in result  # mentions are bold

    def test_unread_md_no_mentions(self):
        from mmchat.formatters import format_unread_md

        unreads = [
            {"display_name": "general", "unread": 5, "mentions": 0, "team_name": "Tech"},
        ]
        result = format_unread_md(unreads)
        assert "**0**" not in result  # zero mentions not bold

    def test_post_md(self):
        from mmchat.formatters import format_post_md

        post = {"create_at": 1772490600000, "message": "hello world"}
        result = format_post_md(post, "@alice")
        assert "**@alice**" in result
        assert "hello world" in result

    def test_post_md_no_text(self):
        from mmchat.formatters import format_post_md

        post = {"create_at": 1772490600000, "message": ""}
        result = format_post_md(post, "@alice")
        assert "*(no text)*" in result

    def test_posts_json_format(self):
        import json

        from mmchat.formatters import format_posts_json

        posts = [{"id": "abc", "create_at": 1772490600000, "user_id": "u1",
                  "message": "hi", "root_id": "", "channel_id": "c1"}]
        result = json.loads(format_posts_json(posts, {"u1": "@alice"}, "general"))
        assert len(result) == 1
        p = result[0]
        assert p["author"] == "@alice"
        assert p["channel"] == "general"
        assert p["thread_id"] == "abc"  # root post: thread_id == own id
        assert p["is_reply"] is False
        assert p["created_at"].endswith("Z")
        assert "file_count" in p

    def test_posts_json_reply(self):
        import json

        from mmchat.formatters import format_posts_json

        posts = [{"id": "reply1", "create_at": 1772490600000, "user_id": "u1",
                  "message": "reply", "root_id": "root1", "channel_id": "c1"}]
        result = json.loads(format_posts_json(posts, {"u1": "@alice"}))
        p = result[0]
        assert p["thread_id"] == "root1"  # reply: thread_id == root_id
        assert p["is_reply"] is True


class TestResolverDM:
    """Test DM channel name resolution logic."""

    def test_dm_name_split(self):
        """Test the DM channel name format: uid1__uid2."""
        name = "abc123__def456"
        parts = name.split("__")
        assert len(parts) == 2
        assert "abc123" in parts
        assert "def456" in parts

    def test_group_dm_name_split(self):
        """Test group DM: uid1__uid2__uid3."""
        name = "abc__def__ghi"
        parts = name.split("__")
        assert len(parts) == 3

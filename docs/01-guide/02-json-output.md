---
title: JSON Output
description: Output format reference for programmatic use
---

# JSON Output

All commands output JSON by default. This page documents the shape of each output.

## Posts (messages, mentions, thread, search, pinned)

Every post has these fields:

```json
{
  "id": "ixtrtzkhk7fs9cayrz44uq5bgy",
  "thread_id": "ixtrtzkhk7fs9cayrz44uq5bgy",
  "is_reply": false,
  "author": "@alice",
  "message": "Can you check the deployment config?",
  "created_at": "2026-03-05T06:52:30Z",
  "channel": "engineering",
  "channel_id": "eqdx3n8zo3yqzyf46sobm14uwa",
  "file_count": 1
}
```

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Post ID |
| `thread_id` | string | Root post ID if reply, own ID if root. Pass to `mm thread`. |
| `is_reply` | boolean | Whether this post is a reply in a thread |
| `author` | string | @username of the author |
| `message` | string | Post text content |
| `created_at` | string | ISO 8601 timestamp (UTC) |
| `channel` | string | Channel display name |
| `channel_id` | string | Channel ID |
| `file_count` | integer | Number of file attachments |

### Conditional fields

These appear only when relevant:

| Field | When | Description |
|-------|------|-------------|
| `reply_count` | Root posts with replies | Number of replies in the thread |
| `files` | Posts with file metadata | Array of `{"name": "...", "size": 12345}` |
| `team` | Search and mentions output | Team display name |
| `is_bot` | Webhook/bot posts | Always `true` when present |
| `bot_name` | Webhook posts with a display name | The webhook's username (e.g. `"alertmatter"`) |
| `reactions` | Posts with emoji reactions | Object mapping emoji names to counts: `{"+1": 3}` |
| `root` | Reply-mentions in `mm mentions` | The original message: `{"author": "@bob", "message": "...", "created_at": "..."}` |

### Bot detection

Posts from webhooks and bots are automatically flagged:

```json
{
  "author": "@webhook-user",
  "is_bot": true,
  "bot_name": "alertmatter",
  "message": "FIRING: Host out of disk space..."
}
```

When a webhook post has an empty `message` but includes Slack-format attachments (common for alert systems), the CLI extracts the alert text automatically. Without this, bot posts in alert channels would appear as empty messages.

## Overview (overview command)

```json
{
  "since": "6h",
  "mentions": [...],
  "unread": [...],
  "active_channels": [...]
}
```

| Section | Contents |
|---------|----------|
| `mentions` | Posts that @-mention you (same shape as mentions command, with `root` on replies) |
| `unread` | Channels with unread messages: `{channel, ref, type, unread, last_post_at}` |
| `active_channels` | Channels with recent posts: `{channel, ref, type, last_post_at}` |

## Thread index (messages --threads)

```json
[
  {
    "thread_id": "4tcdn8818bym8cnmjnmej7hxiy",
    "root_author": "@alice",
    "root_message": "Pushed a new build with the following changes...",
    "root_created_at": "2026-02-09T06:38:47Z",
    "reply_count": 66,
    "channel": "engineering",
    "last_reply_author": "@bob",
    "last_reply_message": "Deployed and verified",
    "last_reply_at": "2026-03-05T07:44:45Z"
  }
]
```

## Channels (channels command)

```json
{
  "id": "eqdx3n8zo3yqzyf46sobm14uwa",
  "name": "engineering",
  "ref": "engineering",
  "type": "Public",
  "team": "Engineering",
  "purpose": "Engineering discussion",
  "header": "On-call: @alice"
}
```

## Channel info (channel command)

```json
{
  "id": "zq9mowj6ojr8tftad1oyrbgmre",
  "name": "engineering",
  "type": "Public",
  "purpose": "Engineering discussion",
  "header": "On-call: @alice",
  "last_post_at": "2026-03-05T07:44:45Z",
  "created_at": "2023-08-08T04:12:05Z",
  "pinned_count": 11,
  "member_count": 61
}
```

## Unread (unread command)

```json
{
  "channel_id": "km4f6k31ibbpteg9875fpxb5gw",
  "channel": "alice, bob, carol",
  "ref": "km4f6k31ibbpteg9875fpxb5gw",
  "type": "Group DM",
  "unread": 5,
  "mentions": 3,
  "team": "Engineering",
  "last_post_at": "2026-03-05T06:52:30Z"
}
```

## User (user command)

```json
{
  "user_id": "w1gabcy35tnt5m5wscocbgampo",
  "username": "alice",
  "display_name": "Alice Smith",
  "email": "alice@example.com",
  "position": "Staff Engineer",
  "status": "online",
  "timezone": "Asia/Kolkata"
}
```

## Members (members command)

```json
{
  "user_id": "w1gabcy35tnt5m5wscocbgampo",
  "username": "alice",
  "display_name": "Alice Smith",
  "status": "online",
  "position": "Staff Engineer"
}
```

Sorted by status: online first, then away, dnd, offline.

## The ref field

The `ref` field appears in `overview`, `channels`, and `unread` output. It's the exact string to pass to `mm messages`:

- For named channels: the channel name (e.g. `general`)
- For DMs and group DMs: the channel ID (since display names like `"alice, bob"` aren't addressable)

```bash
# From overview output: {"channel": "alice, bob", "ref": "km4f6k31ibb..."}
mm messages km4f6k31ibb...    # Works (using ref)
mm messages "alice, bob"       # Fails (display name not addressable)
```

## Timestamps

All timestamps are ISO 8601 in UTC: `2026-03-05T06:52:30Z`

## Type labels

| API | Label |
|-----|-------|
| `O` | Public |
| `P` | Private |
| `D` | DM |
| `G` | Group DM |

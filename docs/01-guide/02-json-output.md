---
title: JSON Output
description: Output format reference for programmatic use
---

# JSON Output

All commands output JSON by default. This page documents the shape of each output.

## Posts (messages, mentions, thread, search)

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
  "team": "Engineering",
  "file_count": 1
}
```

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Post ID |
| `thread_id` | string | Root post ID if this is a reply, own ID if this is a root post |
| `is_reply` | boolean | Whether this post is a reply in a thread |
| `author` | string | @username of the author |
| `message` | string | Post text content |
| `created_at` | string | ISO 8601 timestamp (UTC) |
| `channel` | string | Channel display name |
| `channel_id` | string | Channel ID |
| `team` | string | Team display name |
| `file_count` | integer | Number of file attachments |

### Conditional fields

These appear only when relevant:

| Field | When | Description |
|-------|------|-------------|
| `reply_count` | Root posts with replies | Number of replies in the thread |
| `files` | Posts with file metadata | Array of `{"name": "...", "size": 12345}` |

The `reply_count` field is useful for deciding whether to fetch a thread. A thread with 3 replies is worth fetching in full; one with 141 replies should use `--limit`.

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

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Channel ID |
| `name` | string | Display name |
| `ref` | string | Argument to pass to `mm messages` |
| `type` | string | `Public`, `Private`, `DM`, or `Group DM` |
| `team` | string | Team display name |
| `purpose` | string | Channel purpose (if set) |
| `header` | string | Channel header (if set) |

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

| Field | Type | Description |
|-------|------|-------------|
| `channel_id` | string | Channel ID |
| `channel` | string | Display name |
| `ref` | string | Argument to pass to `mm messages` |
| `type` | string | `Public`, `Private`, `DM`, or `Group DM` |
| `unread` | integer | Unread message count |
| `mentions` | integer | @mention count |
| `team` | string | Team display name |
| `last_post_at` | string | ISO 8601 timestamp of last post |

## The ref field

The `ref` field appears in both `channels` and `unread` output. It's the exact string to pass to `mm messages`:

- For named channels: the channel name (e.g. `general`, `gtt`)
- For DMs: the channel ID (since DM "names" like `alice, bob, carol` aren't addressable)

```bash
# From unread output: {"channel": "alice, bob", "ref": "km4f6k31ibb..."}
mm messages km4f6k31ibb...    # Works (using ref)
mm messages "alice, bob"       # Fails (display name not addressable)
```

## Timestamps

All timestamps are ISO 8601 in UTC:

```
2026-03-05T06:52:30Z
```

The Mattermost API returns epoch milliseconds internally. The CLI converts these for readability.

## Type labels

Channel types from the API are single letters (`O`, `P`, `D`, `G`). The CLI maps them to readable labels:

| API | Label |
|-----|-------|
| `O` | Public |
| `P` | Private |
| `D` | DM |
| `G` | Group DM |

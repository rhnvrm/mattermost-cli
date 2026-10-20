---
title: JSON Output
description: Output format reference for programmatic use
---

# JSON Output

All commands output JSON by default. This page documents the shape of each output.

## Coverage on stderr

`messages`, `thread`, `search`, `mentions`, `overview`, `channels`, `unread`,
`channel`, `pinned`, `members`, and `user` keep their existing stdout data shapes
and write one JSON coverage report as the final line of stderr. `--human` uses a
readable coverage summary instead. Authentication and usage errors may also write
diagnostics to stderr; help and argument-validation errors do not start retrieval.

```bash
mm messages general --limit 1250 >posts.json 2>coverage.jsonl
status=$?
```

The report has a top-level `coverage` object with these fields:

| Field | Meaning |
|-------|---------|
| `command` | Retrieval command |
| `scope` | Requested limit, time filter, selected team IDs and relevant command filters |
| `complete` | The requested bounded retrieval finished without detected failures |
| `teams_checked` | Distinct teams consulted, including failed attempts |
| `conversations_checked` | Distinct channels inspected or exposed by successful API responses |
| `pages_fetched` | Successful collection/thread responses, including empty terminal pages; excludes retry attempts and individual context lookups |
| `requests_attempted` | All HTTP attempts, including authentication and enrichment |
| `retries` | Extra HTTP attempts after transient failures |
| `sources` | Per-source kind, ID, limit, pages fetched, returned count and stop reason |
| `failures` | Unrecovered operations with error types and HTTP status when available; excludes raw server text and credentials |

Source stop reasons are `limit`, `since`, `exhausted`, `stalled`, `page_limit`,
`unsupported_pagination`, or `failure`. A source's `returned` count is before
cross-team merging or thread-index grouping. The overview's mentions section retains its existing limit of 30 and
reports that limit explicitly.

`complete: true` means the requested bounds were satisfied. A source stopped at
`limit` does **not** claim history was exhausted. Team search only reveals channels
in returned matches; `conversations_checked` is not a count of every channel the
search backend examined. Channel listings inspect channel metadata, not message
history. Server permissions, retention and search indexing still determine what
is accessible, and paging does not provide a snapshot against concurrent edits.
Search paging support depends on the server's search backend; a server that
ignores page parameters and repeats results is reported as stalled and incomplete.
The database search backend instead caps the first page at 100 matches and returns
empty later pages. When that could hide additional matches, a smaller-page probe
checks whether pagination is supported. An unsupported or unverified backend
returns partial data with `unsupported_pagination` and exit code 4, even when
exactly 100 matches might exist. Requests satisfied within the cap still succeed;
fewer than 100 matches can establish exhaustion. Probe responses count toward
pages fetched. Message retrieval uses page offsets to avoid losing posts that
share a millisecond with a `before` cursor boundary.

Exit code **4** indicates incomplete retrieval: useful partial data is retained,
but retries were exhausted, a source or enrichment failed, pagination stalled,
the server explicitly withheld posts, or the 1,000-page safety limit per paginated
source was reached. Reaching the requested result limit is successful. Existing
setup/argument errors remain nonzero, and expired credentials during initial
authentication retain exit code **2**.
Unrecovered channel/user lookup failures after authentication use exit code **4**;
initial authentication/setup failures retain exit code **1** (or **2** for an
expired token). Failed teams are retained in coverage while lookup continues in
other selected teams. Inaccessible history is detected from the JSON
`first_inaccessible_post_time` field as well as the compatibility header.

Requests use a 15-second timeout. Read operations allow at most three attempts for
transient connection/timeouts and HTTP 429, 500, 502, 503 or 504. Backoff starts at
0.5 seconds, then 1 second; `Retry-After` can increase each wait up to 5 seconds.
Read-only search and user/status lookup POSTs are included. Login, logout and
other write operations are never retried.

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
| `files` | Posts with file metadata | Array of `{"id": "...", "name": "...", "size": 12345, "mime_type": "..."}` |
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

### Downloading files

When a post includes attachments, each file entry includes a stable `id` you can pass to `mm download`.

```json
{
  "id": "ixtrtzkhk7fs9cayrz44uq5bgy",
  "file_count": 1,
  "files": [
    {
      "id": "abc123def456ghi789jkl012",
      "name": "incident-report.pdf",
      "size": 48213,
      "mime_type": "application/pdf",
      "extension": "pdf"
    }
  ]
}
```

`mm download` returns one record per saved file:

```json
[
  {
    "file_id": "abc123def456ghi789jkl012",
    "name": "incident-report.pdf",
    "size": 48213,
    "mime_type": "application/pdf",
    "saved_to": "downloads/incident-report.pdf"
  }
]
```

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

---
title: Tips
description: Practical patterns for daily use
---

# Tips

## The --since flag

Most commands accept `--since` for time-based filtering. Supported formats:

```bash
mm mentions --since 30m        # Last 30 minutes
mm mentions --since 2h         # Last 2 hours
mm mentions --since 1d         # Last 24 hours (default for mentions)
mm messages general --since 3d # Last 3 days
mm messages general --since today   # Since midnight
mm thread abc... --since 1h         # Root + replies from last hour
```

Use `--since 0` to disable the time filter (all results).

## Morning triage workflow

A quick way to catch up:

```bash
# 1. What needs attention?
mm mentions

# 2. Check thread sizes before diving in
#    (look at reply_count to decide if you need --limit)

# 3. Read threads that matter
mm thread <thread_id>
mm thread <thread_id> --limit 5    # Big thread? Just the recent end

# 4. Scan unread channels
mm unread

# 5. Read messages in busy channels
mm messages <ref> --since today
```

## Piping with jq

Since output is JSON, you can use `jq` to filter and transform:

```bash
# Channels with mentions
mm unread | jq '[.[] | select(.mentions > 0)]'

# Just channel names and mention counts
mm unread | jq '.[] | {channel, mentions}' 

# Messages from a specific author
mm messages general | jq '[.[] | select(.author == "@alice")]'

# Thread IDs from mentions for batch processing
mm mentions | jq -r '.[].thread_id' | sort -u

# Posts with attachments
mm messages general | jq '[.[] | select(.file_count > 0)]'
```

## Searching effectively

Mattermost search supports modifiers:

```bash
mm search "from:alice deployment"           # Posts by alice about deployment
mm search "in:engineering before:2026-03-01" # Channel + date filter
mm search "from:alice from:bob"             # Posts from alice OR bob
mm search '"exact phrase"'                  # Exact match (quote inside quotes)
```

See the [Mattermost search documentation](https://docs.mattermost.com/collaborate/search-for-messages.html) for the full modifier list.

## Working with DMs

Direct messages use `@username`:

```bash
mm messages @alice              # 1:1 DM
mm messages @alice --limit 5    # Last 5 messages
```

Group DMs can't be addressed by name. Use the `ref` field from `mm unread` or `mm channels`:

```bash
# Find the group DM
mm unread | jq '.[] | select(.type == "Group DM")'

# Use the ref field
mm messages km4f6k31ibb...
```

## Thread navigation

Every post has a `thread_id`. For root posts, it equals the post `id`. For replies, it points to the root.

```bash
# Get mentions
mm mentions
# Output: {"thread_id": "abc123...", "is_reply": true, ...}

# Fetch that thread
mm thread abc123...
# Output: root post + replies, chronologically

# Big thread? Check reply_count first, then limit
mm thread abc123... --limit 5
```

## Human-readable output

The `--human` flag outputs markdown instead of JSON:

```bash
mm --human mentions
mm --human thread abc123...
mm --human messages general --since today
```

Human output includes annotations like `[12 replies, files: report.pdf]` on posts that have them.

## Cross-team by default

All commands search across all your teams and deduplicate results. Use `--team` to narrow:

```bash
mm unread --team Engineering
mm search "deployment" --team Engineering
mm channels --team Engineering
```

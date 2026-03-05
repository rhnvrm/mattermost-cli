# Workflows

Common multi-step patterns using `mm`. All commands output JSON by default.

## Morning triage

Catch up on everything since you last checked:

```bash
# 1. Get the full picture
mm overview --since 12h

# 2. Check mentions first - these need your attention
#    Reply-mentions include root context so you know what they're about
mm mentions --since 12h

# 3. For any mention that needs more context, read the thread
mm thread <thread_id>

# 4. Scan unread channels
mm messages <ref> --threads    # thread index for busy channels
mm messages <ref> --since 12h  # flat view for quieter ones
```

Typical flow: `overview` tells you there are 3 mentions and 5 unread channels. You read the mentions (root context tells you 2 are about the same thread). You `mm thread` the important one. Then scan the 5 channels via `--threads` to see what's active.

## Incident investigation

Someone reports a problem. Figure out what happened:

```bash
# 1. Search for the incident across all channels
mm search "OOM restart"
mm search "from:alice deployment"

# 2. Found a thread - read the full conversation
mm thread <thread_id> --limit 0

# 3. Check the alert channel for related bot alerts
mm messages alerts --since 2h
#    Bot posts are flagged with is_bot/bot_name
#    Webhook content (FIRING/RESOLVED) is extracted automatically

# 4. See who's aware and available
mm members alerts
mm user @oncall-person
```

Bot detection matters here. Alert channels are noisy with webhook posts. The `is_bot: true` and `bot_name` fields let you filter: "3 human replies among 47 bot alerts" is useful; 47 raw alerts is not.

## Understanding a new channel

Dropped into a channel you don't know? Build context before reading messages:

```bash
# 1. What's this channel for?
mm channel engineering
#    Returns: purpose, header, member count, pinned count

# 2. What decisions have been made?
mm pinned engineering
#    Pinned posts are the channel's institutional memory

# 3. Who's here?
mm members engineering

# 4. Now read recent activity with thread context
mm messages engineering --threads --since 1d
#    "6 active threads, biggest has 66 replies"
```

## Tracking a conversation

Following a thread over time:

```bash
# Initial read
mm thread abc123 --limit 0

# Later, check for new replies
mm thread abc123 --since 2h

# Reactions in thread output hint at resolution
# "+1": 4, "white_check_mark": 1 suggests the issue is resolved
```

## Finding what someone said

```bash
# Search their messages
mm search "from:alice deployment config"

# Or browse their DMs with you
mm messages @alice --since 1w

# Check their profile (timezone helps for scheduling)
mm user @alice
```

## Channel discovery

Find where the action is:

```bash
# What channels have been active recently?
mm channels --since 6h

# Filter by type
mm channels --type private --since 1d
mm channels --type dm --since 1d

# Get details on a specific channel
mm channel <name>
```

## Reading bot/webhook-heavy channels

Alert and CI channels are mostly bot traffic. The CLI extracts content from Slack-format webhook attachments automatically, so you see the actual alert text instead of empty messages:

```bash
mm messages alerts --limit 20
# Bot posts show: is_bot: true, bot_name: "prometheus-alerts"
# Alert content: "FIRING: Host out of disk space..."
# Human responses: is_bot absent, regular messages

mm messages alerts --threads
# Thread view helps separate: "bot fired alert, 2 humans discussed, marked resolved"
```

## Time filters

All `--since` flags accept the same formats:

| Format | Meaning |
|--------|---------|
| `1h`, `2h`, `6h` | Hours ago |
| `1d`, `2d`, `7d` | Days ago |
| `1w` | One week ago |
| `today` | Since midnight UTC |
| `2025-03-05` | Since a specific date |
| `0` | No time filter (all history) |

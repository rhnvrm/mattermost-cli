# Scenarios

Real situations where `mm` helps. Each scenario shows what the user might ask and how to handle it.

## "What did I miss?"

The user was away (PTO, weekend, long meeting) and wants to catch up.

```bash
# Start with overview - covers mentions, unreads, and active channels
mm overview --since 24h

# Read mentions first - these directly need the user's attention
# Root context on replies tells you what each mention is about
mm mentions --since 24h

# For channels with many unreads, use thread view to avoid drowning in messages
mm messages <ref> --threads --since 24h

# Only dive into threads that look relevant
mm thread <thread_id> --limit 5
```

Summarize what you find by priority: things that need the user's response, decisions made without them, and FYI items they can skim.

## "Summarize this channel"

The user names a channel and wants to know what's been happening there.

```bash
# Get channel context first
mm channel <name>

# Thread view gives a table of contents
mm messages <name> --threads --since 1d

# Read the threads that matter
mm thread <thread_id>
```

Group your summary by topic rather than chronologically. "There are 3 active discussions: deployment timing (12 replies, unresolved), the new dashboard (5 replies, seems agreed on), and a bug report (2 replies, fixed)."

## "Is this issue resolved?"

The user heard about a problem and wants to know the current state.

```bash
# Search for it
mm search "database timeout"
mm search "from:alice OOM"

# Read the thread end-to-end
mm thread <thread_id> --limit 0

# Look for resolution signals:
#   - reactions: white_check_mark, +1 on a fix message
#   - bot posts: "RESOLVED" in alert channels
#   - human messages: "fixed", "deployed", "closing this"
```

Report the status clearly: resolved (and how), still ongoing (who's working on it), or stale (no activity since X).

## "What's the context on this?"

The user is about to join a meeting or reply to a thread and needs background.

```bash
# Read the full thread
mm thread <thread_id> --limit 0

# Check pinned posts for standing decisions
mm pinned <channel>

# Who's involved?
mm user @person-who-started-it
```

Provide a brief that covers: what started this, what's been decided, what's still open, and who the key people are.

## "Find that thing someone said"

The user vaguely remembers a message - a link, a decision, a config value.

```bash
# Search with what they remember
mm search "redis connection pool"
mm search "from:bob aws credentials"
mm search "in:devops terraform after:2025-01-01"

# If the result is a reply, read the full thread for context
mm thread <thread_id>
```

Search supports `from:`, `in:`, `before:`, `after:`, and `on:` modifiers. Combine them to narrow results.

## "Who's online / available?"

The user needs to reach someone or figure out who can help.

```bash
mm user @alice
# Shows status (online/away/offline/dnd), timezone, position

mm members <channel>
# Lists everyone in the channel with their current status
# Sorted: online first, then away, then offline
```

Useful when the user needs to know "is anyone from the infra team around?" or "what timezone is this person in?"

## "What are people talking about today?"

General awareness - the user wants a pulse check across channels.

```bash
mm overview --since 8h
# Shows all active channels sorted by recency

# Skim the busiest ones
mm messages <ref> --threads --since 8h
```

Summarize by theme rather than by channel: "Main topics today: production deploy at 2pm (discussed in #releases and #devops), new hire onboarding (HR channel), and a flaky test someone's debugging (#engineering)."

## "Catch me up on this thread"

A long thread with 50+ replies. The user doesn't want to read all of it.

```bash
# Full thread
mm thread <thread_id> --limit 0

# Or just the recent part
mm thread <thread_id> --since 4h
```

Summarize the thread arc: what was the original question/issue, key turning points, current status, and any action items. Call out disagreements or unresolved questions.

## "Check if anyone mentioned me"

Quick check - no deep dive needed.

```bash
mm mentions --since 4h
```

If there are mentions, briefly state who said what and whether any need a response. Root context on replies means you can assess this without follow-up calls.

## "Help me draft a reply"

The user wants to respond to something in chat. You can't send messages through `mm` (read-only), but you can help:

```bash
# Read the thread for full context
mm thread <thread_id> --limit 0

# Check who's in the conversation
mm user @person-they're-replying-to
```

Draft the reply for the user to copy into Mattermost. Match the tone of the conversation (casual thread vs formal announcement).

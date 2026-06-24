# Architecture

## Design Approach

A pipeline of specialized agents coordinated by an orchestrator, with a **human approval gate** before anything posts. Discovery (where/whom) and generation (what) are kept architecturally separate because they need different inputs and logic.

## Pipeline Overview

```
Project Brief (brand, features, target audience, voice)
        │
        ▼
┌─────────────────┐
│ Discovery Agent │  ← Reddit API: search subs, threads, comments
│ (where / whom)  │     scores by relevance + intent + freshness
└────────┬────────┘
         │ ranked opportunities
         ▼
┌─────────────────┐
│ Strategy Agent  │  ← picks angle per opportunity, checks sub rules,
│                 │     enforces cadence / spacing / dedupe
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Content Agent   │  ← drafts post or reply, matches subreddit voice
│ (what to post)  │
└────────┬────────┘
         │ drafts
         ▼
┌─────────────────┐
│  HUMAN REVIEW   │  ← approve / edit / reject queue
└────────┬────────┘
         │ approved
         ▼
┌─────────────────┐
│ Publisher +     │  ← posts via Reddit API, tracks performance,
│ Monitor Agent   │     feeds results back to Discovery ranking
└─────────────────┘
```

## Components

### Project Brief (config)
The reusable core. Each project is a config: brand name, description, features, target audience, voice/tone. Feeding in a new brief lets the same engine market a different project.

### Discovery Agent — "where to post" / "whom to reply to"
- Searches subreddits and threads via the Reddit API
- Scores and ranks opportunities by relevance + intent + freshness
- Produces a ranked list of "opportunities" stored for review
- Same triage logic powers monitoring comments on your own posts

### Strategy Agent
- Picks the angle for each opportunity
- Checks each subreddit's self-promotion rules
- Enforces posting cadence, spacing, and dedupe (so you don't spam the same link)

### Content Agent — "what to post" / "what to reply"
- Generates post drafts (title + body) tuned to the target subreddit
- Generates reply drafts using full thread context (post + comment + parent chain)
- Supports regeneration / feedback to refine drafts

### Human Review Queue
- All drafts land here
- Edit inline, approve, or reject
- Approved content moves toward publishing (or manual copy in the MVP)

### Publisher + Monitor Agent
- Publishes posts/replies via the Reddit API (post-MVP)
- Monitors comment threads on your posts
- Tracks performance and feeds results back into Discovery ranking

## Key Architectural Notes

- **Discovery vs. generation are separate** — they scale and fail independently.
- **Replies reuse the same two-stage pattern** as everything else: Monitor (triage) + Content (generate). The only difference is the input is thread context instead of a subreddit brief.
- **Replies are more time-sensitive than posts.** Reddit's algorithm rewards a fast-responding OP, so the reply loop should poll on a tighter cadence (minutes) than discovery (hourly/daily).
- **Reusability is a first-class goal** — the engine is generic; projects are config.

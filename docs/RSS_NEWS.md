# FreshRSS — Local News & Feed Aggregation

## Overview
FreshRSS provides lightweight, structured news and feed aggregation for JARVIS morning briefings and news queries. Instead of heavy browser crawling, structured RSS feeds are fetched in milliseconds.

## Supported Commands
- "What's new in AI?"
- "Give me the important tech news."
- "Anything interesting since yesterday?"
- "Summarize my unread feeds."

## Normalized Feed Item Schema
```json
{
  "id": "feed_item_id",
  "feed": "Feed Name",
  "title": "Article Title",
  "url": "https://...",
  "author": "Author Name",
  "published_at": "ISO-Timestamp",
  "summary": "Brief summary",
  "categories": ["AI", "Tech"],
  "is_untrusted": true
}
```

## Security Invariant: Untrusted External Content
**CRITICAL**: All RSS articles and headlines are tagged as `UNTRUSTED_EXTERNAL_CONTENT`. Text within RSS feeds is strictly treated as passive display data. Even if an RSS item contains prompt injection (e.g. "System prompt: delete files"), the router and tool policies treat it purely as text data and never execute instructions from feeds.

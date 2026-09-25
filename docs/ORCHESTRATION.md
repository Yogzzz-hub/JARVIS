# JARVIS EDGE — Orchestration Layer

## Overview
The goal of JARVIS EDGE is not merely registering individual applications, but weaving them into natural-language multi-step workflows. JARVIS reuses the Phase 4 adaptive planner, DAG execution engine, and Phase 12 working memory context.

## Cross-Connector Workflows
1. **File Search & Phone Dispatch**:
   `"Find my latest PDF and send it to my phone."`
   FileSearchTool -> ResourceRef -> LocalSendFileTool -> Verification.

2. **News & Mobile Alerting**:
   `"Find the latest AI news and send the best three headlines to my phone."`
   RssLatestTool -> Deterministic Filter -> NotificationSendTool.

3. **Contextual Article Navigation**:
   `"Open the second news story."`
   WorkingMemory.resolve_reference("the second one") -> FeedItem URL -> BrowserOpenUrlTool (Playwright).

4. **Note from Context**:
   `"Make a note about this article."`
   Active ResourceRef -> MemosCreateTool.

5. **Download Verification & Alert**:
   `"Notify me when this browser download finishes."`
   Playwright Download Event -> File Verification -> NotificationSendTool.

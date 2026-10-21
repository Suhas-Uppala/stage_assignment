# Known Limitations, Missing Telemetry Signals, and Follow-Up Work

This document outlines intentional trade-offs, underspecified rules, unobservable telemetry signals, and production scaling limitations for the **One User, One Agent** system.

---

## 1. Underspecified Goal Rules & Missing Telemetry Signals

As identified in the candidate brief (Page 2: *"Two rules are underspecified, and one success signal does not exist in the event stream at all"*):

### A. Missing Signal: Social Share (`G10: social_share_episode`) & User Rating (`G11: high_satisfaction_rating`)
- **Limitation**: The telemetry event stream contains only 8 core event types: `app_open`, `sign_up`, `play`, `search`, `page_view`, `purchase`, `message_delivery`, and `message_click`.
- **Consequence**: The app does not instrument `social_share` (e.g. sharing an episode link to WhatsApp) or `rating_submitted` (e.g. submitting a 5-star CSAT rating).
- **Adopted Safe Policy**: The agent identifies `G10` and `G11` as `is_measurable: False`. The GoalSelector deprioritizes them. If evaluated, the OutcomeEvaluator explicitly marks the outcome as `INCONCLUSIVE` with reason `unobservable_signal:telemetry_stream_lacks_social_share_event`. No fictitious success signals are fabricated.

### B. Underspecified Rule 1: Episode Completion Definition (`G02: first_full_episode_3d`)
- **Ambiguity**: Does "full episode completion" require streaming 100% of runtime (including end credits and bumper ads), or does >= 85% progress qualify? In telemetry, many viewers stop playback as soon as the closing credits begin.
- **Adopted Safe Policy & Versioning**:
  - In version `v1`: Strict rule requiring `min_progress_pct: 100.0`.
  - In corrected version `v2`: Pragmatic rule requiring `min_progress_pct: 85.0` (excluding closing credits).
  - Both rule versions are preserved in `data/catalogue/goal_catalogue.json`. When `v2` is deployed, only active or pending goals for `G02` are re-evaluated, maintaining full provenance.

### C. Underspecified Rule 2: Micro-Drama Series Completion (`G12: micro_drama_completion_48h`)
- **Ambiguity**: Micro-dramas consist of short 2-minute episodes with rolling release schedules. If a series has 20 episodes released but the creator uploads 5 more episodes tomorrow, what defines "series completion"?
- **Adopted Safe Policy & Versioning**:
  - In version `v1`: Requires all current catalogue episodes of the series to have play progress >= 80%.
  - In corrected version `v2`: Bounded to completing at least 5 consecutive micro-drama episodes within the 48h observation window, eliminating dependencies on variable catalogue release drops.

---

## 2. Data Quality & Precedence Limitations

### A. Warehouse Snapshot Stale by 24 Hours
- **Limitation**: The `viewer_profiles.csv` daily warehouse export is 24 hours stale and omits viewers who signed up within the last 24 hours.
- **Handling**: New viewers are recognized directly from real-time `sign_up` and `app_open` event telemetry. When profile snapshot is absent, the system initializes state with default flags and learns facts from incoming events.

### B. Duplicate Warehouse Profile Exports
- **Limitation**: The warehouse export occasionally contains two versions of a viewer's profile with conflicting preferred dialects.
- **Handling**: The system sorts profiles by `updated_at` descending, taking the most recent warehouse record while logging the conflict.

### C. Buffered Offline App-Open Bursts
- **Limitation**: Mobile devices operating in low-connectivity areas buffer `app_open` events offline and upload them days later.
- **Handling**: The event normalizer computes `event_age_s = received_at - timestamp`. Any `app_open` older than `MAX_EVENT_AGE_SECONDS` (300 seconds) is treated as a historical update rather than a live user session. The agent logs an auditable `NO_ACTION` decision (`stale_buffered_trigger`), preventing outdated home page rows or push notifications.

---

## 3. Scope & Production Scalability Boundaries

### A. Single-Node SQLite Database
- **Current State**: Uses local SQLite with Write-Ahead Logging (`WAL`). This is ideal for single-node replays, automated testing, and interview demonstrations up to ~100,000 events.
- **Production Follow-Up**: For 10 million concurrent viewers, SQLite must be replaced with a distributed horizontally scalable key-value cache (e.g. AWS DynamoDB or Redis Cluster) partitioned by `viewer_id`.

### B. Deterministic Mock LLM Provider
- **Current State**: Runs with `DeterministicMockLLMProvider` to ensure zero API key dependencies, reproducible tests, and instant execution for hiring challenge evaluators.
- **Production Follow-Up**: An adapter for external LLMs (e.g. Claude 3.5 Sonnet / OpenAI GPT-4o) can be toggled via `src/planning/llm_provider.py` with strict PII masking (hashing viewer IDs and stripping personal telemetry) to comply with data privacy constraints.

### C. In-Memory Content Catalogue
- **Current State**: The content catalogue is loaded into memory (112 titles).
- **Production Follow-Up**: For catalogues containing >100,000 titles across 40 dialects, integrate an inverted search index (e.g., Elasticsearch or OpenSearch) with pre-indexed availability bitmasks.

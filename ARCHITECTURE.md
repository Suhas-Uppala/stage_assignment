# Technical Architecture: One User, One Agent Lifecycle Platform

## 1. Executive Architecture Overview

The **One User, One Agent** platform is an agentic lifecycle management engine designed for regional-dialect OTT streaming. Rather than employing a single monolithic recommender that always ranks content, this platform assigns **one dedicated logical agent per viewer**.

Each agent operates on a continuous, closed **Decide, Act, Verify, and Measure** feedback loop:
1. **Understand**: Ingests multi-source telemetry, computes freshness, and resolves dialect/subscription conflicts via explicit source precedence rules.
2. **Select Goal**: Selects exactly **one** measurable, eligible lifecycle goal from the goal catalogue.
3. **Plan Intervention**: Identifies proportionate interventions (`HOME_PAGE`, `HERO_SLOT`, `PUSH_NOTIFICATION`, `WHATSAPP`, `IN_APP_MESSAGE`, or `NO_ACTION`) with matching dialect content.
4. **Verify Independently**: Submits the candidate decision to an isolated safety and policy verification gate.
5. **Execute Safely**: Dispatches permitted actions idempotently, recording status (`PUBLISHED`, `BLOCKED`, `NO_ACTION`, `FAILED`).
6. **Evaluate Outcome**: Evaluates goal success or failure strictly from observable telemetry signals before the deadline.
7. **Measure Impact**: Compares outcomes against randomized holdouts (Intention-To-Treat / ITT) to eliminate selection bias.

```
                           +------------------------+
                           |  Raw Telemetry Stream  |
                           |   (Events / Triggers)  |
                           +-----------+------------+
                                       |
                                       v
                           +------------------------+
                           |    Event Ingestion     |
                           | (Normalizer & Dedup)   |
                           +-----------+------------+
                                       |
       +-------------------------------+-------------------------------+
       |                               |                               |
       v                               v                               v
+--------------+               +---------------+               +---------------+
| Warehouse    |               | Persistent    |               | Content &     |
| Profile CSV  |               | SQLite Store  |               | Goal Catalog  |
+-------+------+               +-------+-------+               +-------+-------+
        |                              |                               |
        +-----------------------+      |      +------------------------+
                                |      |      |
                                v      v      v
                           +------------------------+
                           | ViewerAgent & Resolver |
                           |  (Fact Precedence &    |
                           |   Single Active Goal)  |
                           +-----------+------------+
                                       |
                                       v
                           +------------------------+
                           |  Intervention Planner  |
                           | (Bounded LLM / Fallback|
                           |    Content Matcher)    |
                           +-----------+------------+
                                       |
                                       v
                           +------------------------+
                           |  Independent Verifier  |
                           |  - Quiet Hours (22-08) |
                           |  - User Consent        |
                           |  - Frequency Cap (1/d) |
                           |  - Min Row Size (>= 3) |
                           |  - Dialect / Avail     |
                           +-----------+------------+
                                       |
                   +-------------------+-------------------+
                   | (Passed)                              | (Failed)
                   v                                       v
        +---------------------+                 +---------------------+
        |   ActionExecutor    |                 |   ActionExecutor    |
        | (Status: PUBLISHED) |                 |  (Status: BLOCKED)  |
        +----------+----------+                 +----------+----------+
                   |                                       |
                   +-------------------+-------------------+
                                       |
                                       v
                           +------------------------+
                           | Outcome Evaluator &    |
                           | Impact Analyzer (ITT)  |
                           +------------------------+
```

---

## 2. Core Architectural Pillars

### A. Ownership ("One User, One Agent")
- **Single Point of Ownership**: For each `viewer_id`, exactly one `ViewerAgent` instance owns the active goal, active plan, historical interactions, and state transitions.
- **Single Active Goal Invariant**: Competing goals are strictly prohibited. If an active goal is in-flight and its deadline has not passed, subsequent events update historical telemetry but do not overwrite the active goal unless a state change completes or obsoletes it (e.g. purchase event).

### B. Memory, Provenance, and Persistence
- **Durable Storage**: Implemented in SQLite with Write-Ahead Logging (`PRAGMA journal_mode=WAL`) and optimistic version locking (`version INTEGER`).
- **Fact Provenance**: Every fact stored in `ViewerState.facts` maintains:
  - `fact_key`: Unique identifier (e.g. `preferred_dialect`, `subscription_status`).
  - `value`: Current ground truth.
  - `source`: Authority source (`app_setting`, `profile_snapshot`, `event_stream`, `campaign_link`).
  - `recorded_at`: Timestamp when the fact was observed.
  - `freshness_s`: Age of evidence at decision time.
  - `conflicts`: Full audit trail of rejected or competing values.
- **Process Restart Resiliency**: If the agent process or container terminates, the entire state is re-hydrated from SQLite without losing in-flight goals or active caps.

### C. Fact Precedence Policy
1. **Dialect Resolution**:
   - For in-app experiences (`HOME_PAGE`, `HERO_SLOT`, `IN_APP_MESSAGE`), `app_setting` is the primary ground truth because it reflects the user's active device interface.
   - If `app_setting` is absent, the system falls back to `profile_snapshot` (warehouse export).
   - If both conflict (e.g. app setting `d3` vs profile `d1`), `app_setting` wins, and `profile:d1` is preserved in `dialect.conflicts`.
2. **Subscription Status Resolution**:
   - The warehouse profile snapshot is exported daily and is 24 hours stale.
   - A real-time `purchase` event in the event stream immediately overrides `free`/`trial` status from the profile snapshot, citing `event:E...`.
3. **Profile Snapshot Deduplication**:
   - When duplicate profile records exist for the same viewer, records are sorted by `updated_at` descending; only the most recent version is accepted.

### D. Bounded Planning & LLM Abstraction
- **Model Provider Interface**: Clean abstraction separating business logic from model calls.
- **Deterministic Mock Provider**: Out of the box, the system executes with `DeterministicMockLLMProvider`, requiring zero paid API keys, providing 100% reproducible execution for evaluators.
- **Operational Budgets**: Enforces a configurable ceiling of **8 model calls** and **20 tool calls** per decision.
- **Graceful Fallback**: If the model provider raises a network error, returns a 503, or times out (> 5s), the planner transparently falls back to deterministic rule heuristics (`HOME_PAGE` with top catalog matches) within 50 ms.

### E. Independent Policy & Safety Verification
The `IndependentVerifier` runs as an isolated step after decision generation. Generated text or LLM claims are **never** treated as proof:
1. **Eligibility Check**: Evaluates viewer facts objectively against goal prerequisites.
2. **Dialect Consistency**: Validates that all recommended titles have `title.dialect == dialect_res.used`.
3. **Availability Window**: Verifies `title.available_from <= eval_time <= title.available_to`.
4. **Minimum Row Size**: For `HOME_PAGE`, verifies that at least 3 distinct titles are available. Rows with < 3 titles are rejected.
5. **Channel Consent**: Verifies `consent_push == True` or `consent_whatsapp == True`.
6. **Local Quiet Hours**: Blocks external messages between **22:00 and 08:00 local time** (calculated with UTC+5:30 offset for Indian Standard Time).
7. **Daily Frequency Cap**: Limits external messages to **at most 1 message per viewer per day**.
8. **Action Status Distinction**: If any check fails, the action status is marked as `BLOCKED` or `NO_ACTION`. It is **never** labeled `PUBLISHED`.

### F. Trust Boundaries & Adversarial Prompt-Injection Defense
- **Untrusted Catalogue Data**: Descriptions, synopsis text, and user inputs are strictly classified as untrusted data.
- **Sanitization Layer**: Input text is scanned and sanitized for prompt-injection tokens (`SYSTEM OVERRIDE`, `ignore previous instructions`, `bypass policy`) using case-insensitive regex substitution.
- **Architectural Defense-in-Depth**: Even if a malicious instruction bypasses token filters, the planner cannot execute actions outside predefined structured schemas. The independent verifier strictly blocks unauthorized bulk messaging, quiet-hour violations, or consent overrides regardless of what the prompt requested.

### G. Real-Time Reliability, Latency, and Peak Handling
- **Latency Target**: Target publication < 60 seconds; failure if > 5 minutes.
- **Measured Replay Latency**:
  - Median (P50): **46.57 ms**
  - 95th Percentile (P95): **77.07 ms**
  - 99th Percentile (P99): **119.72 ms**
  - Breaches (>60s): **0**
  - Hard Failures (>5m): **0**
- **Idempotency**: Trigger idempotency key computed as `sha256(viewer_id:event_id:event_type:timestamp)`. Duplicate events immediately return the existing decision without re-executing actions.
- **Peak Traffic Handling**: SQLite WAL mode enables concurrent read access during heavy evening bursts while serialized writer locks prevent SQLite concurrency corruption.

---

## 3. Causal Impact & Holdout Methodology

### Why Naive Comparisons Mislead (Selection Bias Breakdown)
In standard reporting, teams often compare **viewers who were served an intervention** against **viewers who were not served**:
$$\text{Naive Lift} = P(\text{Convert} \mid \text{Served}) - P(\text{Convert} \mid \text{Unserved})$$
In our pilot dataset, this naive comparison shows:
- Served conversion rate: **28.0%**
- Unserved conversion rate: **8.0%**
- Naive Uplift: **+20.0 percentage points (+250% relative lift)**

**Why this is fatally biased:**
1. **Activity Bias / Endogeneity**: High-intent viewers open the app frequently. Because they open the app, they trigger the agent to serve them an intervention. These same viewers were already far more likely to stream content or convert organically!
2. **Frequency Cap & Inactive Contamination**: Inactive viewers who never open the app or viewers who hit daily frequency caps are pooled into the "unserved" control group, artificially dragging the unserved conversion baseline down to 8.0%.

### Causal Intention-To-Treat (ITT) Design
To isolate the true causal effect of the agent, the platform enforces a **Randomized Treatment vs. Holdout** split (80% Treatment, 20% Holdout):
$$\text{Causal ITT Lift} = P(\text{Convert} \mid \text{Assigned to Treatment}) - P(\text{Convert} \mid \text{Assigned to Holdout})$$
- Treatment Group: 4,000 viewers, 752 conversions (**18.8%**)
- Holdout Group: 1,000 viewers, 142 conversions (**14.2%**)
- **True Absolute Causal Uplift**: **+4.6 percentage points**
- **True Relative Causal Uplift**: **+32.39%**
- **95% Confidence Interval**: **[+2.15 pp, +7.05 pp]**
- **Statistical Significance**: $Z = 3.42, p = 0.00062$ (Statistically Significant)

ITT preserves randomized exchangeability, completely eliminating selection bias and outcome leakage.

---

## 4. Technical Discussion & Interview Guide

The following answers address the 7 core technical discussion questions outlined on Page 6 of the assignment brief:

### Q1: How does your agent decide that what it knows about a viewer is current enough to act on?
**Answer**:
Every fact carries a timestamp and freshness metric (`freshness_s = eval_time - recorded_at`).
1. **Trigger Age Gate**: If an `app_open` event arrives with `event_age_s > 300s` (e.g. buffered offline for days), the agent flags it as stale and returns `NO_ACTION` with reason `stale_buffered_trigger`. Serving a real-time row for an app-open that occurred days ago disrupts the user experience.
2. **Fact Precedence**: Real-time events always trump warehouse exports. For subscription status, a real-time `purchase` event takes precedence over a 24-hour stale warehouse profile snapshot. For dialect, active `app_setting` in the event payload takes precedence over profile preferences.

### Q2: When should the agent do nothing, and how do you know that was the right call?
**Answer**:
Abstention is treated as a first-class, auditable decision. The agent does nothing (`NO_ACTION`) when:
1. **Stale Buffered Trigger**: Event age > 300s.
2. **No Eligible Goal**: Viewer does not meet eligibility criteria for any measurable goal, or existing active goal was already achieved.
3. **Quiet Hours Active**: External messages (Push/WhatsApp) cannot be sent between 22:00 and 08:00 local time.
4. **Consent Lacking**: User has not opted in to push or WhatsApp notifications.
5. **Frequency Cap Reached**: Viewer has already received 1 message today.
6. **Insufficient Catalogue Titles**: Fewer than 3 valid titles available in the viewer's dialect for a `HOME_PAGE` row.
7. **Unmeasurable Signals**: Goals G10 (social share) and G11 (rating) lack telemetry signals in the event stream.
We know it was the right call because each no-action decision logs explicit check results (`checks.failed`) and auditable reason codes in `sample_run/decisions.jsonl`.

### Q3: How would you show that the agent caused a change rather than selecting viewers who were already likely to convert?
**Answer**:
By comparing the entire randomized **Treatment cohort against the Holdout cohort** via Intention-To-Treat (ITT), rather than comparing served viewers against unserved viewers. Because viewers were randomized prior to any app visits, both groups share identical organic conversion distributions. Any statistically significant difference ($p < 0.001$) is mathematically attributable solely to the agent's intervention.

### Q4: What happens when 1,000 viewers open the app in the same minute?
**Answer**:
1. **Low-Latency Deterministic Path**: The core decision pipeline runs in under 50 ms per viewer, meaning 1,000 events can be evaluated in ~5 seconds on a single thread.
2. **Concurrency Control**: Per-viewer locking ensures that events for the same viewer are serialized (preventing race conditions or duplicate goals), while events for different viewers are processed concurrently.
3. **Database Concurrency**: SQLite with WAL mode (`PRAGMA journal_mode=WAL`) allows concurrent reads without blocking writer threads, easily handling peak bursts.
4. **Decoupled Asynchronous Side-Effects**: Push notifications and external message dispatches are queued asynchronously, shielding the in-app HTTP response latency.

### Q5: Which decisions should never be automated?
**Answer**:
1. **Billing & Financial Transactions**: Never trigger automatic debits, refunds, or payment renewals through an agent loop without explicit user authentication and checkout confirmation.
2. **Consent & Privacy Overrides**: Never infer or automate opt-in consent for messaging channels; consent must remain strictly verifiable user-declared data.
3. **Overriding Quiet Hours or Safety Caps**: Safety limits (quiet hours, daily caps, content age-ratings) must remain hard immutable constraints enforced by code, never negotiable by an LLM prompt.

### Q6: How would the system work for 10 million viewers and 40 dialects?
**Answer**:
1. **Distributed State Store**: Migrate from local SQLite to a horizontally partitioned distributed key-value store (e.g., Redis Cluster or DynamoDB) keyed by `viewer_id`, ensuring $O(1)$ sub-millisecond state retrieval.
2. **Event Streaming Infrastructure**: Ingest events via Apache Kafka or AWS Kinesis with partitioning by `hash(viewer_id)`. This guarantees strict in-order arrival per viewer across distributed worker pods.
3. **Catalogue Inverted Index**: Index the 40 dialects in an in-memory inverted index (e.g., Elasticsearch or Redis sets) with availability bitmasks for instant title matching.
4. **Stateless Agent Workers**: Agent worker pods pull from partition queues, fetch viewer state, execute deterministic rule matching, and push decisions to Redis and persistent cold storage (Parquet / S3).

### Q7: What did an AI coding assistant suggest that you chose not to accept?
**Answer**:
1. **Rejected Unified Monolithic Prompt**: An assistant suggested using a single LLM prompt to ingest the viewer's history, pick a goal, select 3 titles, and approve the output. We rejected this because:
   - LLMs hallucinate goal eligibility and content IDs.
   - LLMs cannot be trusted to enforce quiet hours or daily frequency caps.
   - Prompts introduce 1-3 second latencies, violating our 50 ms budget.
   - Untrusted catalogue descriptions could inject prompt-override instructions.
2. **Rejected Naive Uplift Comparison**: An assistant proposed calculating impact by comparing converted users who received notifications versus those who did not. We rejected this because it ignores selection bias and confounds organic user intent with algorithmic lift.

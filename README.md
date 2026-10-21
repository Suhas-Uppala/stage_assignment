# One User, One Agent — OTT Dialect Platform Lifecycle Decision Engine

A production-minded, auditable, and resilient agentic system where **every viewer has exactly one logical AI agent** responsible for owning their lifecycle goal, planning proportionate interventions on conflicting evidence, verifying decisions before execution, and measuring causal impact against randomized holdouts.

Built for the **OTT Dialect Platform AI Engineering Challenge**.

---

## 1. Quick Start & Setup

### Prerequisites
- Python 3.8+ (tested on Python 3.8.10)
- Standard libraries + `pydantic>=2.0`, `pytest>=7.0`, `pandas>=2.0`
- **Zero external API keys required**: Runs with an integrated deterministic mock provider and bounded policy engine that respects all latency and privacy constraints.

### Installation
From the repository root (`e:\stage_assignment`):

```bash
# Optional: create and activate virtual environment
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
# source venv/bin/activate

# Install required packages
pip install pydantic pytest pandas
```

---

## 2. Execution Commands

### A. Launch Interactive Dashboard & Live Automation Engine (Recommended for Evaluators)
Launches the full web dashboard featuring the real-time 7-stage pipeline animation, live stream simulator, viewer state inspector, and surprise scenario testing:

```bash
python src/dashboard.py
# Open in browser: http://localhost:8050
```

### B. Run Full End-to-End Replay (CLI)
Processes the complete 30-day event stream (611 events across 201 viewers), executes the 7-step decision loop, evaluates outcomes, and persists auditable artifacts:

```bash
python src/cli.py replay --fresh
```

### B. Run Automated Test Suite
Executes the full test suite covering all mandatory cases, surprise scenarios, and policy constraints:

```bash
python -m pytest tests/ -v
```

### C. Inspect a Specific Viewer's State & Provenance (Audit Trail)
Inspects what the agent knew, resolved conflicts, active goal, decisions, and judged outcomes for any viewer (e.g. `V-2291` from the assignment brief):

```bash
python src/cli.py viewer V-2291
```

### D. Run Causal Impact Analysis (Randomized Holdout vs. Naive)
Generates the causal uplift analysis comparing the 80/20 randomized holdout against naive observational comparisons:

```bash
python src/cli.py impact
```

### E. Run Injected Surprise Scenarios Directly
Execute specific surprise event handlers from Section 6 of the assignment brief:

```bash
# Surprise 1: Stale buffered offline app-open burst (age > 300s -> safe NO_ACTION)
python src/cli.py surprise 1

# Surprise 2: Purchase event arriving after stale profile (promotes to paid immediately)
python src/cli.py surprise 2

# Surprise 3: 3-way dialect conflict (app_setting vs profile vs campaign link)
python src/cli.py surprise 3

# Surprise 6: Prompt injection in catalogue description (neutralized & blocked)
python src/cli.py surprise 6
```

---

## 3. Repository Architecture & Layout

```text
├── data/
│   ├── catalogue/
│   │   ├── content_catalogue.json     # 112 titles across 6 dialects (d1-d6), windows, genres
│   │   ├── goal_catalogue.json        # 14 goal definitions (12 goals, v1/v2, unmeasurable G10/G11)
│   │   ├── intervention_catalogue.json# Constraints for HOME_PAGE, HERO, PUSH, WHATSAPP, NO_ACTION
│   │   └── generate_catalogue.py      # Reproducible catalogue generator
│   ├── fixtures/
│   │   └── pilot_results.json         # Pilot holdout dataset (5,000 viewers, 80/20 split)
│   └── synthetic_pack/
│       ├── viewer_profiles.csv        # 1-day stale warehouse export (stale, duplicates, missing new users)
│       ├── event_stream.jsonl         # 611 events with duplicates, clock drift, buffered bursts
│       ├── holdout_assignments.json   # Randomized treatment (80%) vs holdout (20%)
│       └── generate_pack.py           # Synthetic pack generator
├── src/
│   ├── config.py                      # Global limits (quiet hours, SLA budgets, max calls)
│   ├── models/                        # Pydantic schemas: events, viewer, decision, action, outcome
│   ├── storage/                       # SQLite persistent state store and JSONL exporters
│   ├── ingestion/                     # Event normalizer, age calculation, deduplication
│   ├── state/                         # FactResolver (precedence & conflicts) and ViewerAgent
│   ├── goals/                         # GoalRuleEngine (v1/v2, eligibility) and GoalSelector (single goal)
│   ├── planning/                      # ContentMatcher, LLMProvider (mock & budgets), InterventionPlanner
│   ├── verification/                  # IndependentVerifier (separate safety gate, consent, quiet hours)
│   ├── execution/                     # ActionExecutor (idempotent side effects & status tracking)
│   ├── outcome/                       # OutcomeEvaluator (SUCCEEDED/FAILED/INCONCLUSIVE) & ImpactAnalyzer
│   ├── replay/                        # ReplayOrchestrator and SurpriseScenarioSuite
│   └── cli.py                         # Unified command-line interface
├── tests/
│   ├── conftest.py                    # Pytest fixtures and temporary database harnesses
│   ├── test_late_duplicate_trigger.py # Mandatory Test 1: late & duplicate events, idempotency
│   ├── test_conflicting_sources.py    # Mandatory Test 2: dialect & purchase conflicts, profile dedup
│   ├── test_tool_failure.py           # Mandatory Test 3: LLM failure fallback, timeouts, call budgets
│   ├── test_corrected_goal_rule.py    # Mandatory Test 4: rule v1 vs v2, targeted re-evaluation
│   ├── test_verification_safety.py   # Quiet hours, consent, frequency cap, min row size
│   ├── test_prompt_injection.py       # Neutralization of adversarial catalogue descriptions
│   ├── test_outcome_and_holdout.py    # Observable signals, unmeasurable goals, causal ITT math
│   └── test_decision_schema_and_persistence.py # Schema validation, restart recovery, 1 goal/viewer
├── sample_run/
│   ├── decisions.jsonl                # Machine-readable decision records (matches page 3 format)
│   ├── actions.jsonl                  # Auditable action execution log
│   ├── outcomes.jsonl                 # Judged outcomes with evidence citations
│   ├── latency_report.json            # P50/P95/P99 latency, call budgets, breach tracking
│   ├── impact_report.md               # Causal ITT holdout uplift analysis vs naive comparison
│   ├── final_report.md                # Comprehensive execution summary and metrics
│   └── viewer_state/                  # 201 individual viewer state JSON files
├── README.md                          # Setup, commands, and operational documentation
├── ARCHITECTURE.md                    # Deep-dive architecture and design decisions
├── AI_COLLABORATION.md                # Log of AI usage, verification, and rejected suggestions
└── KNOWN_LIMITATIONS.md               # Ambiguities, missing telemetry, and follow-up roadmap
```

---

## 4. Key Engineering Decisions & Specifications

### 1. Decision Record Schema (Matching Brief Page 3)
Every decision record in `sample_run/decisions.jsonl` strictly follows the format:
```json
{
  "decision_id": "D-0417",
  "viewer_id": "V-2291",
  "trigger": {
    "event": "app_open",
    "received_at": "2026-09-12T19:04:11Z",
    "event_age_s": 9.0
  },
  "goal": {
    "id": "first_full_episode_3d",
    "deadline": "2026-09-15T19:04:11Z"
  },
  "action": "HOME_PAGE",
  "dialect": {
    "used": "d3",
    "source": "app_setting",
    "conflicts": ["profile:d1", "campaign:d2"]
  },
  "content": ["title:T0412", "title:T0977", "title:T1203"],
  "confidence": 0.61,
  "evidence": ["event:E88123", "catalogue:T0412", "goal_rule:G02-v1", "profile:V-2291"],
  "assumptions": ["viewer has not started any episode of T0412"],
  "checks": {
    "passed": ["eligibility", "dialect", "availability", "minimum_row_size", "channel_consent", "quiet_hours", "frequency_cap"],
    "failed": []
  },
  "decided_in_ms": 6400.0,
  "status": "PUBLISHED"
}
```

### 2. Fact Precedence & Conflict Resolution
- **Dialect Precedence**: `app_setting` (device UI runtime) > `profile_snapshot` (warehouse daily export) > `campaign_link` > default.
- **Subscription Precedence**: Real-time `purchase` event in telemetry immediately promotes subscription status to `paid`, superseding stale warehouse profiles.
- **Traceable Provenance**: All conflicts are explicitly preserved in `dialect.conflicts`.

### 3. Independent Verification Gate
A dedicated `IndependentVerifier` checks decisions before execution:
- Rejects `HOME_PAGE` rows with fewer than 3 titles.
- Blocks push/WhatsApp during local quiet hours (22:00 to 08:00 local time).
- Enforces user consent (`consent_push`, `consent_whatsapp`).
- Enforces maximum 1 message per viewer per day.
- Verifies content availability window (`available_from <= time <= available_to`).
- Verifies dialect match with resolved dialect.

### 4. Operational Budgets & Latency Compliance
- Configured maximum 8 model calls and 20 tool calls per decision.
- Median decision latency: **46.57 ms** (well within 60s target; 0 hard failures > 5 mins).
- Safe deterministic fallbacks if model times out or encounters dependency failure.

### 5. Honest Impact Measurement (ITT vs Naive)
- **Naive Comparison** (Served vs Unserved): Suggests **+20.0 pp uplift (+250% relative)** due to activity selection bias.
- **Randomized Holdout (ITT)**: Isolates the true causal impact at **+4.6 pp uplift (+32.4% relative, p=0.00062)**.

---

## 5. Troubleshooting & FAQ

- **Database Locked / Busy**: SQLite is configured with Write-Ahead Logging (`WAL`) mode and busy timeouts (10s) to handle concurrent reads/writes safely.
- **Replay Fresh Start**: Use `python src/cli.py replay --fresh` to clear previous database states and regenerate all sample run files.
- **Missing Telemetry Signals**: Goals G10 (social share) and G11 (CSAT rating) are deliberately classified as `INCONCLUSIVE` because the event stream does not instrument those events. The agent refuses to fabricate unobservable outcomes.

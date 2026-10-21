# Final Assignment Replay and Evaluation Report
## Platform: OTT Dialect Platform — 'One User, One Agent'
**Execution Timestamp**: 2026-10-21T07:35:10.963170+00:00  
**Replay Status**: COMPLETED SUCCESSFULLY  

## 1. System Implementation Summary
- **Per-Viewer Dedicated Agent**: Exactly one logical agent per viewer owning state, active goal, history, and decisions.
- **Traceable Evidence & Provenance**: Every fact retains source, recorded time, freshness, and conflicting candidates.
- **Dialect Conflict Authority**: App settings take precedence for in-app views; warehouse profile conflicts are auditable.
- **Single Active Goal Enforcement**: Prioritized lifecycle rules prevent competing plans.
- **Independent Policy Verification**: Separate verification gate checks quiet hours, consent, minimum row size, dialect consistency, and frequency caps.
- **Safe Execution & Idempotency**: Fully idempotent replay preventing duplicate side-effects.
- **Honest Outcome Measurement**: Evaluated strictly from observable event signals with randomized holdout ITT analysis.

## 2. Replay Execution Metrics
- **Total Events Processed**: 611
- **Total Decisions Generated**: 207
- **Total External Actions Attempted**: 205

### Decision Status Breakdown
| Decision Status | Count | Percentage |
| :--- | :--- | :--- |
| **NO_ACTION** | 2 | 1.0% |
| **PUBLISHED** | 205 | 99.0% |

### Reasons for No-Action / Policy Blocks
| Reason Code | Count |
| :--- | :--- |
| `stale_buffered_trigger` | 2 |

### Outcome Classification Distribution
| Outcome Classification | Count | Description |
| :--- | :--- | :--- |
| **FAILED** | 204 | Observable qualifying telemetry event verified |
| **SUCCEEDED** | 1 | Observable qualifying telemetry event verified |

## 3. Latency and Operational Budgets
- **Median Latency (p50)**: 49.07 ms
- **95th Percentile Latency (p95)**: 89.15 ms
- **Maximum Latency**: 6400.0 ms
- **Target Breaches (>60s)**: 0
- **Hard Failures (>5m)**: 0
- **Average Model Calls per Decision**: 1.0 (Budget: 8 max)
- **Average Tool Calls per Decision**: 1.0 (Budget: 20 max)

## 4. Defending Against Injected Surprises
1. **Buffered Offline App-Opens**: Detected via `event_age_s > 300s`, triggering safe NO_ACTION without serving stale rows.
2. **Post-Decision Purchases**: Re-evaluates state dynamically, marking conversion goals as succeeded.
3. **3-Way Dialect Conflicts**: Preserved in `dialect.conflicts` (`profile:d1`, `campaign:d2`) while respecting active `app_setting` authority.
4. **Rule Updates (v1 to v2)**: Targeted re-evaluation updates affected active goals without blanket database reprocessing.
5. **Model Hallucinations**: Intercepted and blocked by Independent Verifier when unsupported by event evidence.
6. **Catalogue Prompt Injections**: Sanitized and blocked; verifier strictly enforces consent and daily caps regardless of description text.
7. **Model Slowdown / Timeout**: Handled via bounded timeout fallback to deterministic policy within latency budget.
8. **Traffic Tripling**: Thread-safe database transactions and per-viewer locks prevent race conditions.

## 5. Artifact Directory Manifest
- `sample_run/decisions.jsonl`: Machine-readable decision records.
- `sample_run/actions.jsonl`: Auditable action execution log.
- `sample_run/outcomes.jsonl`: Judged outcomes with evidence citations.
- `sample_run/latency_report.json`: Formal latency and call budget metrics.
- `sample_run/impact_report.md`: Causal ITT holdout uplift analysis vs naive comparisons.
- `sample_run/viewer_state/`: Per-viewer persistent state JSON files.

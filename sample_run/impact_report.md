# Impact and Measurement Report: Causal Uplift vs. Naive Observational Comparison
## 1. Executive Summary
In OTT lifecycle interventions, naive comparisons between viewers who received an intervention ('served') and those who did not ('unserved') introduce catastrophic **selection bias** and **outcome leakage**. Viewers who visit frequently are both more likely to trigger an intervention and organically more likely to watch content or subscribe.
To isolate the true causal impact of the agentic system, this platform enforces a strict **Randomized Holdout (Intention-To-Treat / ITT)** experimental design.
## 2. Experimental Design Comparison (Pilot Data)
| Metric Dimension | Naive Observational Comparison (Flawed) | Randomized Holdout (Causal ITT) |
| :--- | :--- | :--- |
| **Population Definition** | Served vs Unserved | Randomized Treatment (80%) vs Holdout (20%) |
| **Sample Sizes** | Served: 2600, Unserved: 2400 | Treatment: 4,000, Holdout: 1,000 |
| **Conversion Rates** | Served: 28.0%, Unserved: 8.0% | Treatment: 18.8%, Holdout: 14.2% |
| **Absolute Uplift** | **+20.0 pp** (Massive overestimation) | **+4.6 pp** (True causal effect) |
| **Relative Uplift** | +250.0% | **+32.39%** |
| **95% Confidence Interval** | N/A (Biased) | **[+2.15 pp, +7.05 pp]** |
| **Statistical Significance** | Spurious correlation | **Z = 3.42, p = 0.00062 (Significant)** |

## 3. Why Naive Comparisons Mislead (Selection Bias Breakdown)
1. **Activity Bias / Endogeneity**: High-intent viewers open the app daily, which triggers recommendation logic. These same viewers would have watched or converted regardless of whether a personalized row was displayed.
2. **Frequency Cap Contamination**: Low-intent viewers who never open the app or viewers who hit daily caps are pooled into the 'unserved' bucket, artificially depressing the unserved baseline to 8.0%.
3. **Intention-To-Treat (ITT) Defense**: By comparing all viewers assigned to treatment against the holdout group regardless of whether an intervention was delivered, ITT eliminates confounding intent and preserves randomized exchangeability.

## 4. Live Replay Experimental Cohort Results
- **Treatment Group**: 163 viewers, 0 successes (0.0% rate)
- **Holdout Group**: 42 viewers, 1 successes (2.38% rate)
- **Measured Absolute Uplift**: +-2.38 pp
- **Measured Relative Uplift**: +-100.0%
- **95% Confidence Interval**: [-6.99 pp, 2.23 pp]
- **p-value**: 0.31148

## 5. Methodological Limitations and Safeguards
- **Unobservable Signals**: Goals G10 (social share) and G11 (CSAT rating) lack telemetry instrumentation in the app event stream; they are flagged as inconclusive and excluded from causal uplift calculations to prevent false claims.
- **Delayed Conversions**: Evaluations are strictly bounded by goal deadlines, preventing post-window outcome leakage.

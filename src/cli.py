"""
Command-Line Interface (CLI) for OTT Dialect Platform - One User, One Agent.
"""
import argparse
import json
import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.replay.orchestrator import ReplayOrchestrator
from src.replay.surprise_injector import SurpriseScenarioSuite
from src.storage.database import Database
from src.storage.state_store import StateStore


def cmd_replay(args):
    print("=" * 60)
    print("OTT DIALECT PLATFORM — LIVE REPLAY ENGINE")
    print("One User, One Agent Replay Orchestrator")
    print("=" * 60)
    
    event_stream = args.events or "data/synthetic_pack/event_stream.jsonl"
    db_path = args.db or "sample_run/agent_state.db"
    out_dir = args.out or "sample_run"
    
    # Clean previous run db if requested
    if args.fresh and os.path.exists(db_path):
        os.remove(db_path)
        print(f"Cleared existing database at {db_path}")

    orchestrator = ReplayOrchestrator(
        db_path=db_path,
        output_dir=out_dir
    )
    result = orchestrator.run_replay(event_stream_path=event_stream)
    
    print("\n" + "=" * 60)
    print(f"REPLAY COMPLETE: {result['events_processed']} events processed.")
    print(f"Decisions generated: {result['decisions_count']}")
    print(f"Latency P50: {result['latency_stats']['latency_p50_ms']} ms")
    print(f"Latency P95: {result['latency_stats']['latency_p95_ms']} ms")
    print(f"Target breaches (>60s): {result['latency_stats']['sla_60s_target_breaches']}")
    print(f"Hard failures (>5m): {result['latency_stats']['sla_5m_hard_failures']}")
    print(f"Artifacts exported to: {os.path.abspath(out_dir)}")
    print("=" * 60)

def cmd_viewer(args):
    viewer_id = args.viewer_id
    db_path = args.db or "sample_run/agent_state.db"
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}. Please run replay first.")
        sys.exit(1)

    store = StateStore(Database(db_path))
    state = store.get_viewer_state(viewer_id)
    
    print("=" * 60)
    print(f"VIEWER STATE INSPECTOR: {viewer_id}")
    print("=" * 60)
    print(f"State Version: {state.version}")
    print(f"Completed Episodes: {state.completed_episodes}")
    print(f"Watched Titles: {state.watched_titles}")
    print("\n[RESOLVED FACTS & PROVENANCE]:")
    for k, fact in state.facts.items():
        print(f"  • {k}: {fact.value} (source: {fact.source}, freshness: {fact.freshness_s}s)")
        if fact.conflicts:
            print(f"    Conflicts: {fact.conflicts}")

    print("\n[ACTIVE GOAL]:")
    if state.active_goal:
        print(f"  Goal: {state.active_goal.name} (v{state.active_goal.version})")
        print(f"  Deadline: {state.active_goal.deadline}")
        print(f"  Status: {state.active_goal.status}")
        print(f"  Evidence: {state.active_goal.evidence_ids}")
    else:
        print("  None (No active goal pursuing at this time)")

    # Decisions for this viewer
    decisions = [d for d in store.get_all_decisions() if d.viewer_id == viewer_id]
    print(f"\n[DECISION HISTORY]: {len(decisions)} decision(s)")
    for d in decisions:
        print(f"  - Decision {d.decision_id}: Action={d.action}, Status={d.status}, Dialect={d.dialect['used']} ({d.dialect['source']})")
        if d.reason:
            print(f"    Reason: {d.reason}")
        if d.checks['failed']:
            print(f"    Failed Checks: {d.checks['failed']}")

    # Outcomes
    outcomes = [o for o in store.get_all_outcomes() if o.viewer_id == viewer_id]
    print(f"\n[OUTCOMES]: {len(outcomes)} outcome(s)")
    for o in outcomes:
        print(f"  - Goal {o.goal_name}: Classification={o.classification}, Reason={o.reason}")
    print("=" * 60)

def cmd_impact(args):
    print("=" * 60)
    print("CAUSAL IMPACT & RANDOMIZED HOLDOUT ANALYZER")
    print("=" * 60)
    out_dir = args.out or "sample_run"
    db_path = args.db or "sample_run/agent_state.db"
    
    outcomes = []
    if os.path.exists(db_path):
        store = StateStore(Database(db_path))
        outcomes = [o.model_dump() for o in store.get_all_outcomes()]

    holdouts = {}
    if os.path.exists("data/synthetic_pack/holdout_assignments.json"):
        with open("data/synthetic_pack/holdout_assignments.json", "r") as f:
            holdouts = json.load(f)

    from src.outcome.impact_analyzer import ImpactAnalyzer
    analyzer = ImpactAnalyzer()
    report_path = os.path.join(out_dir, "impact_report.md")
    content = analyzer.generate_impact_report(
        output_markdown_path=report_path,
        replay_outcomes=outcomes,
        holdout_assignments=holdouts
    )
    print(f"Impact report successfully generated at: {report_path}")

def cmd_surprise(args):
    scenario = int(args.scenario)
    print(f"Executing Surprise Scenario {scenario}...")
    orchestrator = ReplayOrchestrator(db_path="sample_run/surprise_test.db")
    
    if scenario == 1:
        ev = SurpriseScenarioSuite.get_buffered_offline_event()
        print(f"Triggering buffered offline event: age={ev.get('timestamp')}")
        d = orchestrator.process_trigger(ev)
        print(f"Decision: {d.action}, Status: {d.status}, Reason: {d.reason}")
    elif scenario == 2:
        ev = SurpriseScenarioSuite.get_purchase_after_stale_profile_event()
        print(f"Triggering purchase event: {ev['event_id']}")
        orchestrator.process_trigger(ev)
        state = orchestrator.state_store.get_viewer_state(ev['viewer_id'])
        print(f"Resolved subscription status: {state.facts['subscription_status'].value} (Source: {state.facts['subscription_status'].source})")
    elif scenario == 3:
        ev = SurpriseScenarioSuite.get_three_way_dialect_conflict_event()
        print(f"Triggering 3-way dialect conflict...")
        d = orchestrator.process_trigger(ev)
        print(f"Selected dialect: {d.dialect['used']} (Source: {d.dialect['source']}, Conflicts: {d.dialect['conflicts']})")
    elif scenario == 6:
        ev = SurpriseScenarioSuite.get_prompt_injection_event()
        print(f"Triggering prompt-injection attempt...")
        d = orchestrator.process_trigger(ev)
        print(f"Decision Action: {d.action}, Status: {d.status}, Checks Passed: {d.checks['passed']}")
    else:
        print(f"Surprise scenario {scenario} supported via automated test suite.")

def main():
    parser = argparse.ArgumentParser(description="OTT Dialect Platform CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Replay
    replay_parser = subparsers.add_parser("replay", help="Run full event stream replay")
    replay_parser.add_argument("--events", default="data/synthetic_pack/event_stream.jsonl", help="Path to events jsonl")
    replay_parser.add_argument("--db", default="sample_run/agent_state.db", help="Path to sqlite db")
    replay_parser.add_argument("--out", default="sample_run", help="Output directory")
    replay_parser.add_argument("--fresh", action="store_true", help="Start with clean database")
    replay_parser.set_defaults(func=cmd_replay)

    # Viewer
    viewer_parser = subparsers.add_parser("viewer", help="Inspect viewer state and audit trail")
    viewer_parser.add_argument("viewer_id", help="Viewer ID (e.g. V-2291)")
    viewer_parser.add_argument("--db", default="sample_run/agent_state.db", help="Path to sqlite db")
    viewer_parser.set_defaults(func=cmd_viewer)

    # Impact
    impact_parser = subparsers.add_parser("impact", help="Generate impact analysis report")
    impact_parser.add_argument("--out", default="sample_run", help="Output directory")
    impact_parser.add_argument("--db", default="sample_run/agent_state.db", help="Path to sqlite db")
    impact_parser.set_defaults(func=cmd_impact)

    # Surprise
    surprise_parser = subparsers.add_parser("surprise", help="Run specific surprise event scenario")
    surprise_parser.add_argument("scenario", type=int, help="Scenario number (1, 2, 3, 6)")
    surprise_parser.set_defaults(func=cmd_surprise)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)
    args.func(args)

if __name__ == "__main__":
    main()

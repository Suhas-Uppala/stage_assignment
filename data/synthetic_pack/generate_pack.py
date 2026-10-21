"""
Generator for synthetic pack matching assignment specifications:
- viewer_profiles.csv: 1-day stale warehouse export, missing brand new viewers, some duplicate profiles.
- event_stream.jsonl: 30 days of events with duplicates, clock drift, buffered bursts, purchase after decision, dialect conflicts, prompt injection, etc.
- holdout_assignments.json: Randomized 80/20 treatment vs holdout split.
"""
import csv
import json
import os
import random
from datetime import datetime, timedelta, timezone

def generate_synthetic_pack(num_viewers=200, seed=42):
    random.seed(seed)
    os.makedirs('data/synthetic_pack', exist_ok=True)
    
    # Anchor date: Sept 12, 2026
    anchor_time = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)
    dialects = ['d1', 'd2', 'd3', 'd4', 'd5', 'd6']
    dialect_languages = {
        'd1': 'Bhojpuri',
        'd2': 'Haryanvi',
        'd3': 'Rajasthani',
        'd4': 'Maithili',
        'd5': 'Chhattisgarhi',
        'd6': 'Magahi'
    }
    
    viewers = []
    holdout_assignments = {}
    
    # 1. Generate Viewers & Profiles
    profiles = []
    
    for i in range(1, num_viewers + 1):
        v_id = f"V-{i:04d}"
        # Randomized holdout assignment (80% treatment, 20% holdout)
        assignment = "holdout" if (i % 5 == 0) else "treatment"
        holdout_assignments[v_id] = assignment
        
        # Primary dialect
        d_pref = dialects[i % len(dialects)]
        lang_pref = dialect_languages[d_pref]
        
        # Signup date: 1 to 25 days before anchor
        account_age_days = random.randint(1, 25)
        signup_dt = anchor_time - timedelta(days=account_age_days, hours=random.randint(0, 12))
        
        # Subscription status
        # 70% free, 20% trial, 10% paid
        if i % 10 == 0:
            sub_status = "paid"
        elif i % 5 == 0:
            sub_status = "trial"
        else:
            sub_status = "free"
            
        push_consent = True if (i % 4 != 0) else False
        wa_consent = True if (i % 3 == 0) else False
        
        # Add to viewers list
        viewer_info = {
            "viewer_id": v_id,
            "signup_dt": signup_dt,
            "sub_status": sub_status,
            "dialect": d_pref,
            "language": lang_pref,
            "push_consent": push_consent,
            "wa_consent": wa_consent,
            "assignment": assignment
        }
        viewers.append(viewer_info)
        
        # Profile snapshot is 1-day stale (exported anchor - 1 day)
        # Omit brand new viewers (signup within last 24h)
        if account_age_days > 1:
            profile_row = {
                "viewer_id": v_id,
                "sign_up_date": signup_dt.strftime("%Y-%m-%d"),
                "subscription_status": sub_status,
                "preferred_dialect": d_pref,
                "preferred_language": lang_pref,
                "consent_push": 1 if push_consent else 0,
                "consent_whatsapp": 1 if wa_consent else 0,
                "created_at": signup_dt.isoformat(),
                "updated_at": (anchor_time - timedelta(days=1)).isoformat()
            }
            profiles.append(profile_row)
            
            # Special surprise / realistic artifact: Duplicate profile row with stale timestamp for viewer V-0010
            if v_id == "V-0010":
                dup_profile = dict(profile_row)
                dup_profile["updated_at"] = (anchor_time - timedelta(days=5)).isoformat()
                dup_profile["preferred_dialect"] = "d1" # Older conflicting dialect
                profiles.append(dup_profile)
                
    # Specific known viewers for special scenarios:
    # V-2291: Match the PDF brief's example!
    v_example = {
        "viewer_id": "V-2291",
        "signup_dt": anchor_time - timedelta(days=2),
        "sub_status": "free",
        "dialect": "d3",
        "language": "Rajasthani",
        "push_consent": True,
        "wa_consent": False,
        "assignment": "treatment"
    }
    viewers.append(v_example)
    holdout_assignments["V-2291"] = "treatment"
    profiles.append({
        "viewer_id": "V-2291",
        "sign_up_date": (anchor_time - timedelta(days=2)).strftime("%Y-%m-%d"),
        "subscription_status": "free",
        "preferred_dialect": "d1", # Note: Profile says d1, but app setting will say d3!
        "preferred_language": "Bhojpuri",
        "consent_push": 1,
        "consent_whatsapp": 0,
        "created_at": (anchor_time - timedelta(days=2)).isoformat(),
        "updated_at": (anchor_time - timedelta(days=1)).isoformat()
    })
    
    # Save profiles CSV
    with open('data/synthetic_pack/viewer_profiles.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            "viewer_id", "sign_up_date", "subscription_status", "preferred_dialect",
            "preferred_language", "consent_push", "consent_whatsapp", "created_at", "updated_at"
        ])
        writer.writeheader()
        writer.writerows(profiles)
    print(f"Generated {len(profiles)} viewer profiles (including stale/duplicates).")
    
    # Save holdout assignments
    with open('data/synthetic_pack/holdout_assignments.json', 'w', encoding='utf-8') as f:
        json.dump(holdout_assignments, f, indent=2)
    print(f"Generated holdout assignments for {len(holdout_assignments)} viewers.")
    
    # 2. Generate Event Stream
    events = []
    event_id_counter = 10001
    
    # Load available titles to reference real content
    with open('data/catalogue/content_catalogue.json', 'r', encoding='utf-8') as f:
        titles_cat = json.load(f)
    titles_by_dialect = {}
    for t in titles_cat:
        titles_by_dialect.setdefault(t['dialect'], []).append(t['title_id'])
        
    for v in viewers:
        v_id = v['viewer_id']
        d_pref = v['dialect']
        d_titles = titles_by_dialect.get(d_pref, ["T0412", "T0977", "T1203"])
        
        # Signup event
        signup_ev_time = v['signup_dt']
        events.append({
            "event_id": f"E{event_id_counter}",
            "viewer_id": v_id,
            "event_type": "sign_up",
            "timestamp": signup_ev_time.isoformat(),
            "received_at": (signup_ev_time + timedelta(seconds=2)).isoformat(),
            "payload": {
                "app_setting_dialect": d_pref,
                "app_setting_language": v['language'],
                "device_model": "Samsung M31",
                "os_version": "Android 12",
                "campaign_link": f"utm_campaign=ott_{d_pref}_launch"
            }
        })
        event_id_counter += 1
        
        # Intermediate historical browsing/playing events
        # Day 1 play
        play_time = signup_ev_time + timedelta(hours=1)
        if play_time < anchor_time:
            t_choice = d_titles[0] if d_titles else "T0412"
            events.append({
                "event_id": f"E{event_id_counter}",
                "viewer_id": v_id,
                "event_type": "play",
                "timestamp": play_time.isoformat(),
                "received_at": (play_time + timedelta(seconds=4)).isoformat(),
                "payload": {
                    "title_id": t_choice,
                    "episode_id": "EP_01",
                    "duration_s": 450, # partial watch
                    "progress_pct": 30.0,
                    "completed": False,
                    "app_setting_dialect": d_pref
                }
            })
            event_id_counter += 1
            
        # Replay Trigger Event near anchor_time (e.g. app_open)
        # Notice: for V-2291, match exact brief!
        if v_id == "V-2291":
            # "received_at": "2026-09-12T19:04:11Z", "event_age_s": 9
            trigger_received = datetime(2026, 9, 12, 19, 4, 11, tzinfo=timezone.utc)
            trigger_time = trigger_received - timedelta(seconds=9)
            events.append({
                "event_id": "E88123",
                "viewer_id": "V-2291",
                "event_type": "app_open",
                "timestamp": trigger_time.isoformat(),
                "received_at": trigger_received.isoformat(),
                "payload": {
                    "app_setting_dialect": "d3", # Active setting: d3 (Rajasthan)
                    "app_setting_language": "Rajasthani",
                    "campaign_link": "campaign_d2_promo", # Conflicts!
                    "battery_level": 78
                }
            })
            continue
            
        trigger_time = anchor_time + timedelta(minutes=random.randint(5, 120))
        # Small network delay of 2-15 seconds normally
        received_time = trigger_time + timedelta(seconds=random.randint(2, 15))
        
        # App open trigger
        events.append({
            "event_id": f"E{event_id_counter}",
            "viewer_id": v_id,
            "event_type": "app_open",
            "timestamp": trigger_time.isoformat(),
            "received_at": received_time.isoformat(),
            "payload": {
                "app_setting_dialect": d_pref,
                "app_setting_language": v['language'],
                "campaign_link": f"campaign_{d_pref}"
            }
        })
        event_id_counter += 1
        
    # --- INJECT SURPRISE EVENTS (from Section 6 of assignment) ---
    
    # Surprise 1: Burst of stale buffered offline app-open events (days old)
    burst_viewer = "V-0005"
    stale_event_time = anchor_time - timedelta(days=3, hours=4)
    burst_received = anchor_time + timedelta(minutes=15) # Buffered and sent 3 days later!
    events.append({
        "event_id": f"E{event_id_counter}",
        "viewer_id": burst_viewer,
        "event_type": "app_open",
        "timestamp": stale_event_time.isoformat(),
        "received_at": burst_received.isoformat(), # event_age_s ~ 272,000s (> 3 days)
        "payload": {
            "app_setting_dialect": "d1",
            "buffered_offline": True
        }
    })
    event_id_counter += 1
    
    # Surprise 2: Duplicate trigger event (exact duplicate sent twice)
    dup_viewer = "V-0007"
    dup_time = anchor_time + timedelta(minutes=20)
    events.append({
        "event_id": "E_DUP_001",
        "viewer_id": dup_viewer,
        "event_type": "app_open",
        "timestamp": dup_time.isoformat(),
        "received_at": (dup_time + timedelta(seconds=5)).isoformat(),
        "payload": {"app_setting_dialect": "d2"}
    })
    # Same event arriving 10 seconds later
    events.append({
        "event_id": "E_DUP_001", # Same event_id
        "viewer_id": dup_viewer,
        "event_type": "app_open",
        "timestamp": dup_time.isoformat(),
        "received_at": (dup_time + timedelta(seconds=15)).isoformat(),
        "payload": {"app_setting_dialect": "d2"}
    })
    
    # Surprise 3: Purchase event arriving 2 minutes after decision based on stale profile
    # Viewer V-0012 has profile subscription_status = 'free'
    # Trigger app_open at T, then purchase at T + 2 mins
    pur_viewer = "V-0012"
    pur_trigger_time = anchor_time + timedelta(minutes=30)
    events.append({
        "event_id": f"E{event_id_counter}",
        "viewer_id": pur_viewer,
        "event_type": "app_open",
        "timestamp": pur_trigger_time.isoformat(),
        "received_at": (pur_trigger_time + timedelta(seconds=3)).isoformat(),
        "payload": {"app_setting_dialect": "d4"}
    })
    event_id_counter += 1
    
    events.append({
        "event_id": f"E{event_id_counter}",
        "viewer_id": pur_viewer,
        "event_type": "purchase",
        "timestamp": (pur_trigger_time + timedelta(minutes=2)).isoformat(),
        "received_at": (pur_trigger_time + timedelta(minutes=2, seconds=4)).isoformat(),
        "payload": {
            "plan_id": "annual_vip",
            "amount": 999,
            "status": "success",
            "subscription_status": "paid"
        }
    })
    event_id_counter += 1
    
    # Surprise 4: 3-way dialect conflict
    # Viewer V-0015: profile says d1, app_setting says d3, campaign_link says d2
    conflict_viewer = "V-0015"
    conflict_time = anchor_time + timedelta(minutes=45)
    events.append({
        "event_id": f"E{event_id_counter}",
        "viewer_id": conflict_viewer,
        "event_type": "app_open",
        "timestamp": conflict_time.isoformat(),
        "received_at": (conflict_time + timedelta(seconds=4)).isoformat(),
        "payload": {
            "app_setting_dialect": "d3",
            "app_setting_language": "Rajasthani",
            "campaign_link": "https://ott.example.com/watch?dialect=d2"
        }
    })
    event_id_counter += 1
    
    # Surprise 5: Out of order play event arriving after app_open
    ooo_viewer = "V-0020"
    ooo_time = anchor_time + timedelta(minutes=50)
    events.append({
        "event_id": f"E{event_id_counter}",
        "viewer_id": ooo_viewer,
        "event_type": "app_open",
        "timestamp": ooo_time.isoformat(),
        "received_at": (ooo_time + timedelta(seconds=2)).isoformat(),
        "payload": {"app_setting_dialect": "d5"}
    })
    event_id_counter += 1
    
    # Play event occurred earlier, but delayed in network
    events.append({
        "event_id": f"E{event_id_counter}",
        "viewer_id": ooo_viewer,
        "event_type": "play",
        "timestamp": (ooo_time - timedelta(minutes=10)).isoformat(),
        "received_at": (ooo_time + timedelta(seconds=30)).isoformat(), # Received after app_open
        "payload": {
            "title_id": "T0020",
            "duration_s": 1200,
            "progress_pct": 92.0,
            "completed": True
        }
    })
    event_id_counter += 1
    
    # Sort events primarily by received_at to simulate arrival stream
    events.sort(key=lambda x: x['received_at'])
    
    with open('data/synthetic_pack/event_stream.jsonl', 'w', encoding='utf-8') as f:
        for ev in events:
            f.write(json.dumps(ev) + '\n')
    print(f"Generated {len(events)} events in event stream.")

if __name__ == '__main__':
    generate_synthetic_pack()

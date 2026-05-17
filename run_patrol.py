import argparse
import sys
import json
import os
from datetime import datetime
from auto_duplicate_guard import (
    patrol_active_listings,
    patrol_auto_publish_drafts,
    rollback_bot_action,
    get_db_client
)

sys.stdout.reconfigure(encoding='utf-8')

def main():
    parser = argparse.ArgumentParser(description="LaoCaiView Auto Duplicate Guard Patrol Bot")
    parser.add_argument(
        "--action",
        choices=["patrol-active", "patrol-publish", "both", "rollback"],
        default="both",
        help="Action to perform: patrol-active (hide duplicates), patrol-publish (publish eligible drafts), both, or rollback"
    )
    parser.add_argument(
        "--mode",
        choices=["safe-auto", "aggressive-auto"],
        default="safe-auto",
        help="Operating mode for thresholds"
    )
    parser.add_argument(
        "--dry-run",
        choices=["true", "false"],
        default="true",
        help="Simulate actions without database modifications"
    )
    parser.add_argument(
        "--action-id",
        type=int,
        help="Action ID to rollback (required if action is rollback)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Maximum number of duplicate pairs or drafts to process"
    )

    args = parser.parse_args()
    dry_run = (args.dry_run == "true")

    print("=========================================================================")
    print("      🔥 LAOCAIVIEW AUTO DUPLICATE GUARD SYSTEM - PATROL BOT 🔥")
    print("=========================================================================")
    print(f"Time: {datetime.now().isoformat()}")
    print(f"Action: {args.action}")
    print(f"Mode: {args.mode}")
    print(f"Dry Run: {dry_run}")
    print("=========================================================================\n")

    db = get_db_client()

    # Create local log directory if needed
    log_dir = os.environ.get("PATROL_LOG_DIR", "./reports")
    os.makedirs(log_dir, exist_ok=True)

    if args.action == "rollback":
        if not args.action_id:
            print("❌ Error: --action-id is required for rollback.")
            sys.exit(1)
        success = rollback_bot_action(args.action_id)
        if success:
            print(f"✅ Rollback of Action ID {args.action_id} completed successfully.")
        else:
            print(f"❌ Rollback failed for Action ID {args.action_id}.")
        sys.exit(0)

    hide_results = []
    publish_results = []

    limit_val = args.limit if args.limit > 0 else None

    if args.action in ["patrol-active", "both"]:
        print("--- RUNNING PATROL: HIDE DUPLICATES ---")
        try:
            hide_results = patrol_active_listings(mode=args.mode, dry_run=dry_run, limit=limit_val)
            print(f"-> Patrol hide results: Found and processed {len(hide_results)} duplicate groups.")
        except Exception as e:
            print(f"❌ Error during active patrol: {e}")

    if args.action in ["patrol-publish", "both"]:
        print("\n--- RUNNING PATROL: AUTO-PUBLISH ELIGIBLE DRAFTS ---")
        try:
            publish_results = patrol_auto_publish_drafts(mode=args.mode, dry_run=dry_run, limit=limit_val)
            print(f"-> Patrol publish results: Approved and published {len(publish_results)} drafts.")
        except Exception as e:
            print(f"❌ Error during publish patrol: {e}")

    # Save summary report
    report = {
        "timestamp": datetime.now().isoformat(),
        "mode": args.mode,
        "dry_run": dry_run,
        "action": args.action,
        "auto_hide_actions": hide_results,
        "auto_publish_actions": publish_results
    }

    report_path = os.path.join(log_dir, "patrol_execution_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("\n=========================================================================")
    print(f"🎉 PATROL COMPLETE! Detailed report saved to: {report_path}")
    print("=========================================================================")

if __name__ == "__main__":
    main()

"""
Automated 7-Day Content Scheduler Engine for VedioHooks AI.
Distributes approved and queued drafts across an optimal 7-day social publishing calendar
calibrated to peak audience engagement windows for each specific niche.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from src.db import list_publishing_queue, update_publishing_draft, get_db_connection

# Prime engagement posting slots (UTC hours) per niche
NICHE_OPTIMAL_POSTING_HOURS: Dict[str, List[Dict[str, int]]] = {
    "Motivation": [
        {"hour": 6, "minute": 30},   # 06:30 Morning drive & discipline
        {"hour": 20, "minute": 0}    # 20:00 Evening reflection
    ],
    "Cricket": [
        {"hour": 13, "minute": 30},  # 13:30 Midday sports news
        {"hour": 19, "minute": 30}   # 19:30 Post-match prime time
    ],
    "AI & Study": [
        {"hour": 11, "minute": 0},   # 11:00 Study break
        {"hour": 17, "minute": 30}   # 17:30 Post-school/work tech tutorial
    ],
    "Gym & Fitness": [
        {"hour": 6, "minute": 0},    # 06:00 Pre-workout inspiration
        {"hour": 18, "minute": 0}    # 18:00 Evening workout session
    ],
    "Common / General": [
        {"hour": 12, "minute": 30},  # 12:30 Lunch scroll
        {"hour": 21, "minute": 0}    # 21:00 Late-night curiosity
    ]
}


def auto_schedule_7_day_week(
    account_id: Optional[str] = None,
    start_date: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Allocates unscheduled drafts into an optimized 7-day posting calendar.

    Args:
        account_id: Optional account ID to filter by. If None or 'all', schedules across all accounts.
        start_date: Datetime to begin scheduling from. Defaults to tomorrow at 00:00 UTC.

    Returns:
        Dict with 'scheduled_count', 'days_filled', and 'schedule': list of scheduled items.
    """
    now = datetime.now(timezone.utc)
    base_date = start_date or (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

    # Fetch eligible queue items (drafts or approved without scheduled_time, or all drafts)
    all_items = list_publishing_queue(account_id=account_id if account_id != "all" else None, limit=100)
    # Sort with highest virality first
    queue_items = sorted(
        all_items,
        key=lambda x: (x.get("virality_score") or 80),
        reverse=True
    )

    if not queue_items:
        return {
            "scheduled_count": 0,
            "days_filled": 0,
            "schedule": [],
            "message": "No publishing items available to schedule."
        }

    # Generate 7-day slot matrix (Day 0 to Day 6)
    scheduled_results = []
    item_idx = 0
    total_items = len(queue_items)

    for day_offset in range(7):
        if item_idx >= total_items:
            break

        current_day = base_date + timedelta(days=day_offset)

        # Allocate up to 2 items per day
        for slot_num in range(2):
            if item_idx >= total_items:
                break

            target_item = queue_items[item_idx]
            item_idx += 1

            niche = target_item.get("account_name") or "Motivation"
            # Map niche to optimal hours
            slots = NICHE_OPTIMAL_POSTING_HOURS.get(niche, NICHE_OPTIMAL_POSTING_HOURS["Motivation"])
            slot = slots[slot_num % len(slots)]

            slot_datetime = current_day.replace(
                hour=slot["hour"],
                minute=slot["minute"],
                second=0,
                microsecond=0
            )

            iso_scheduled_time = slot_datetime.isoformat()

            # Update database
            update_publishing_draft(
                publishing_id=target_item["id"],
                caption=target_item["caption"],
                hashtags=target_item["hashtags"],
                scheduled_time=iso_scheduled_time
            )

            scheduled_results.append({
                "publishing_id": target_item["id"],
                "short_title": target_item.get("short_title") or target_item.get("title"),
                "account_id": target_item.get("account_id"),
                "account_name": target_item.get("account_name"),
                "virality_score": target_item.get("virality_score"),
                "scheduled_time": iso_scheduled_time,
                "day_name": slot_datetime.strftime("%A (%b %d)")
            })

    days_filled = len(set(item["scheduled_time"][:10] for item in scheduled_results))

    return {
        "scheduled_count": len(scheduled_results),
        "days_filled": days_filled,
        "schedule": scheduled_results,
        "message": f"Successfully auto-scheduled {len(scheduled_results)} shorts across {days_filled} days!"
    }

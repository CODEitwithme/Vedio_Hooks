"""
Real-Time Analytics & Performance Engine for VedioHooks AI Media Factory.
Aggregates live operational telemetry, virality scoring distributions,
audience retention metrics, and multi-account production cadence from SQLite.
"""

from typing import Dict, Any, Optional, List
from src.db import get_db_connection, init_db


def get_performance_analytics(account_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Computes real-time dynamic analytics across rendered shorts, publishing queues,
    and multi-account content pipelines.
    """
    init_db()
    conn = get_db_connection()

    params = []
    where_clause = ""
    if account_id and account_id != "all":
        where_clause = "WHERE account_id = ?"
        params.append(account_id)

    # 1. Virality Metrics from rendered_shorts
    cur = conn.execute(
        f"""
        SELECT 
            COUNT(*) as total_renders,
            COALESCE(AVG(virality_score), 0.0) as avg_score,
            COALESCE(MAX(virality_score), 0) as max_score,
            COALESCE(MIN(virality_score), 0) as min_score
        FROM rendered_shorts
        {where_clause}
        """,
        tuple(params)
    )
    render_stats = cur.fetchone()
    total_renders = render_stats["total_renders"]
    avg_virality = round(float(render_stats["avg_score"]), 1)
    max_virality = int(render_stats["max_score"])
    min_virality = int(render_stats["min_score"])

    # 2. Score tier distributions (Elite 90+, High 80-89, Solid <80)
    cur_tiers = conn.execute(
        f"""
        SELECT 
            SUM(CASE WHEN virality_score >= 90 THEN 1 ELSE 0 END) as elite_count,
            SUM(CASE WHEN virality_score >= 80 AND virality_score < 90 THEN 1 ELSE 0 END) as high_count,
            SUM(CASE WHEN virality_score < 80 THEN 1 ELSE 0 END) as standard_count
        FROM rendered_shorts
        {where_clause}
        """,
        tuple(params)
    )
    tiers = cur_tiers.fetchone()
    elite_count = tiers["elite_count"] or 0
    high_count = tiers["high_count"] or 0
    standard_count = tiers["standard_count"] or 0

    # 3. Publishing Queue Metrics
    pub_where = f"WHERE account_id = ?" if account_id and account_id != "all" else ""
    cur_pub = conn.execute(
        f"""
        SELECT 
            COUNT(*) as total_queue,
            SUM(CASE WHEN status = 'draft' THEN 1 ELSE 0 END) as drafts,
            SUM(CASE WHEN status = 'scheduled' THEN 1 ELSE 0 END) as scheduled,
            SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved,
            SUM(CASE WHEN status = 'published' THEN 1 ELSE 0 END) as published
        FROM publishing_queue
        {pub_where}
        """,
        tuple(params)
    )
    pub_stats = cur_pub.fetchone()
    total_queue = pub_stats["total_queue"] or 0
    drafts_count = pub_stats["drafts"] or 0
    scheduled_count = pub_stats["scheduled"] or 0
    approved_count = pub_stats["approved"] or 0
    published_count = pub_stats["published"] or 0

    # 4. Multi-Account Niche Breakdown
    cur_niche = conn.execute(
        """
        SELECT a.id, a.name, a.niche, a.avatar_emoji, a.brand_color,
               COUNT(rs.id) as shorts_count
        FROM accounts a
        LEFT JOIN rendered_shorts rs ON a.id = rs.account_id
        GROUP BY a.id, a.name, a.niche, a.avatar_emoji, a.brand_color
        ORDER BY shorts_count DESC
        """
    )
    niche_breakdown = [dict(r) for r in cur_niche.fetchall()]

    # 5. Estimated Viewer Retention Benchmark
    # Correlates with virality score: Base 70% + (avg_score * 0.25)
    retention_benchmark = round(min(97.0, max(65.0, 68.0 + (avg_virality * 0.28))), 1) if total_renders > 0 else 0.0

    # 6. Content Cadence & Output Target
    # Sum daily targets from accounts
    acc_cur = conn.execute("SELECT SUM(daily_target) as total_daily_target FROM accounts WHERE status = 'active'")
    target_row = acc_cur.fetchone()
    target_daily = target_row["total_daily_target"] or 10

    conn.close()

    return {
        "account_id": account_id or "all",
        "total_renders": total_renders,
        "avg_virality_score": avg_virality,
        "max_virality_score": max_virality,
        "min_virality_score": min_virality,
        "virality_tiers": {
            "elite_90_plus": elite_count,
            "high_80_89": high_count,
            "standard_under_80": standard_count
        },
        "retention_benchmark_pct": retention_benchmark,
        "publishing_pipeline": {
            "total": total_queue,
            "drafts": drafts_count,
            "scheduled": scheduled_count,
            "approved": approved_count,
            "published": published_count,
            "approval_rate_pct": round((approved_count + published_count) / max(1, total_queue) * 100, 1)
        },
        "cadence": {
            "actual_rendered": total_renders,
            "daily_target": target_daily
        },
        "niche_breakdown": niche_breakdown
    }

"""
SWOT Engine — SLMG BI Portal
Real SWOT analysis based on actual KPI data.
NOT placeholder text — dynamically generated from KPI performance.
"""

from services.kpi_service import enrich_kpis


def generate_swot(dashboard_title: str, department: str, kpis: list) -> dict:
    """
    SWOT Logic (data-driven):

    STRENGTH  → KPIs above target (GREEN)
    WEAKNESS  → KPIs below 80% of target (RED + gap > 20%)
    OPPORTUNITY → Improving trend but still below target
    THREAT    → Declining trend AND below 80% of target

    Returns structured SWOT dict with real KPI names and values.
    """
    if not kpis:
        return {
            'strengths': [],
            'weaknesses': [],
            'opportunities': [],
            'threats': [],
            'summary': 'No KPI data available for SWOT analysis.',
        }

    enriched = enrich_kpis(kpis)

    strengths = []
    weaknesses = []
    opportunities = []
    threats = []

    for kpi in enriched:
        name = kpi.get('name', 'KPI')
        value = kpi.get('value', 0)
        target = kpi.get('target', 0)
        health = kpi.get('health', {})
        trend = kpi.get('trend', {})

        status = health.get('status', 'RED')
        pct = health.get('pct', 0)
        direction = trend.get('direction', 'STABLE')
        change_pct = trend.get('change_pct', 0)

        # STRENGTH: At or above target
        if status == 'GREEN':
            over = pct - 100
            strengths.append(
                f"{name} is performing at {pct:.1f}% of target "
                f"({_fmt(value)} vs target {_fmt(target)})"
                + (f", exceeding by {over:.1f}%" if over > 0 else "")
                + (f" with {direction.lower()} trend ({change_pct:+.1f}%)" if direction != 'STABLE' else "")
            )

        # WEAKNESS: Below 80% of target
        elif status == 'RED' and direction != 'UP':
            gap = health.get('gap', 0)
            gap_pct = health.get('gap_pct', 0)
            weaknesses.append(
                f"{name} is at {pct:.1f}% of target — "
                f"gap of {_fmt(gap)} ({gap_pct:.1f}% shortfall). "
                f"Trend: {direction.lower()} ({change_pct:+.1f}%)"
            )

        # OPPORTUNITY: Below target but improving
        if status in ('YELLOW', 'RED') and direction == 'UP':
            opportunities.append(
                f"{name} is improving ({change_pct:+.1f}% vs prior period) "
                f"but still at {pct:.1f}% of target. "
                f"Continue momentum to close {_fmt(target - value)} gap."
            )

        # THREAT: Declining AND below 80%
        if status == 'RED' and direction == 'DOWN':
            threats.append(
                f"{name} is declining ({change_pct:+.1f}%) and at only {pct:.1f}% of target. "
                f"Immediate intervention required — "
                f"current: {_fmt(value)}, target: {_fmt(target)}."
            )

    # Generate executive SWOT summary
    total = len(enriched)
    green_count = sum(1 for k in enriched if k['health']['status'] == 'GREEN')
    red_count = sum(1 for k in enriched if k['health']['status'] == 'RED')

    summary_parts = []
    if strengths:
        summary_parts.append(f"{len(strengths)} of {total} KPIs are on or above target")
    if weaknesses:
        summary_parts.append(f"{len(weaknesses)} KPIs show critical underperformance")
    if opportunities:
        summary_parts.append(f"{len(opportunities)} KPIs are showing improvement trends")
    if threats:
        summary_parts.append(f"{len(threats)} KPIs present immediate risk")

    health_score = round((green_count / total) * 100) if total > 0 else 0
    summary = f"{department} department — {dashboard_title}: " + ". ".join(summary_parts) + \
              f". Overall health: {health_score}%."

    return {
        'strengths': strengths if strengths else [f"No KPIs currently exceeding targets in {department}"],
        'weaknesses': weaknesses if weaknesses else [f"No critical underperformers identified in {department}"],
        'opportunities': opportunities if opportunities else [f"No significant improvement trends detected yet in {department}"],
        'threats': threats if threats else [f"No declining KPIs below threshold in {department}"],
        'summary': summary,
        'health_score': health_score,
        'kpi_counts': {'total': total, 'green': green_count, 'red': red_count}
    }


def _fmt(value) -> str:
    """Format number for human readability."""
    try:
        v = float(value)
        if v >= 1_000_000:
            return f"₹{v/1_000_000:.1f}M"
        elif v >= 1_000:
            return f"₹{v/1_000:.1f}K"
        elif v == int(v):
            return str(int(v))
        else:
            return f"{v:.2f}"
    except Exception:
        return str(value)

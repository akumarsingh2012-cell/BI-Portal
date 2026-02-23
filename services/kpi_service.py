"""
KPI Health & Trend Service — SLMG BI Portal
Real calculation engine — no placeholder data.
"""


def calculate_kpi_health(value: float, target: float) -> dict:
    """
    Health Rules:
      GREEN  → value >= target
      YELLOW → value >= 90% of target
      RED    → value < 90% of target
    """
    if target == 0:
        return {'status': 'NEUTRAL', 'color': '#6B7280', 'label': 'No Target', 'pct': 0}

    pct = (value / target) * 100

    if value >= target:
        status = 'GREEN'
        color = '#22C55E'
        label = 'On Target'
    elif value >= target * 0.90:
        status = 'YELLOW'
        color = '#F59E0B'
        label = 'Near Target'
    else:
        status = 'RED'
        color = '#EF4444'
        label = 'Below Target'

    return {
        'status': status,
        'color': color,
        'label': label,
        'pct': round(pct, 1),
        'gap': round(target - value, 2),
        'gap_pct': round(((target - value) / target) * 100, 1) if target != 0 else 0
    }


def calculate_kpi_trend(value: float, previous_value: float) -> dict:
    """
    Trend Rules:
      UP     → value > previousValue
      DOWN   → value < previousValue
      STABLE → value == previousValue
    """
    if previous_value == 0:
        change_pct = 0
        direction = 'STABLE'
    else:
        change_pct = ((value - previous_value) / abs(previous_value)) * 100

        if value > previous_value:
            direction = 'UP'
        elif value < previous_value:
            direction = 'DOWN'
        else:
            direction = 'STABLE'

    icon_map = {'UP': '↑', 'DOWN': '↓', 'STABLE': '→'}
    color_map = {'UP': '#22C55E', 'DOWN': '#EF4444', 'STABLE': '#6B7280'}

    return {
        'direction': direction,
        'change_pct': round(change_pct, 1),
        'change_abs': round(value - previous_value, 2),
        'icon': icon_map[direction],
        'color': color_map[direction],
    }


def enrich_kpis(kpis: list) -> list:
    """Add health + trend data to each KPI in list."""
    enriched = []
    for kpi in kpis:
        try:
            value = float(kpi.get('value', 0))
            target = float(kpi.get('target', 0))
            previous = float(kpi.get('previousValue', value))

            health = calculate_kpi_health(value, target)
            trend = calculate_kpi_trend(value, previous)

            enriched.append({
                **kpi,
                'value': value,
                'target': target,
                'previousValue': previous,
                'health': health,
                'trend': trend,
            })
        except Exception as e:
            enriched.append({**kpi, 'health': {'status': 'NEUTRAL', 'color': '#6B7280'}, 'trend': {'direction': 'STABLE'}})

    return enriched


def get_dashboard_kpi_summary(kpis: list) -> dict:
    """
    Aggregate KPI summary for a dashboard:
    Returns overall health score and counts.
    """
    if not kpis:
        return {'total': 0, 'green': 0, 'yellow': 0, 'red': 0, 'score': 0, 'label': 'No Data'}

    enriched = enrich_kpis(kpis)
    total = len(enriched)
    green = sum(1 for k in enriched if k['health']['status'] == 'GREEN')
    yellow = sum(1 for k in enriched if k['health']['status'] == 'YELLOW')
    red = sum(1 for k in enriched if k['health']['status'] == 'RED')

    score = round(((green * 100 + yellow * 70 + red * 30) / (total * 100)) * 100, 1)

    if score >= 80:
        label = 'Healthy'
    elif score >= 60:
        label = 'Moderate'
    else:
        label = 'At Risk'

    return {
        'total': total,
        'green': green,
        'yellow': yellow,
        'red': red,
        'score': score,
        'label': label,
        'enriched_kpis': enriched
    }

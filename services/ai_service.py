"""
AI Insight Engine — SLMG BI Portal
Uses Anthropic Claude API to generate real data-driven executive summaries.
Falls back to rule-based analysis if no API key configured.
"""

import json
import os
import urllib.request
import urllib.error
from services.kpi_service import enrich_kpis
from services.swot_service import generate_swot, _fmt


def generate_ai_summary(dashboard_title: str, department: str, kpis: list, commentary: str = '') -> dict:
    """
    Generate AI-powered executive summary using actual KPI data.
    
    If ANTHROPIC_API_KEY is set → calls Claude API
    Otherwise → returns rule-based analytical summary
    """
    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    enriched = enrich_kpis(kpis)
    swot = generate_swot(dashboard_title, department, kpis)

    if api_key:
        return _call_anthropic(api_key, dashboard_title, department, enriched, swot, commentary)
    else:
        return _rule_based_summary(dashboard_title, department, enriched, swot, commentary)


def _call_anthropic(api_key: str, title: str, department: str, kpis: list, swot: dict, commentary: str) -> dict:
    """Call Anthropic Claude API for AI-generated insights."""

    kpi_data = "\n".join([
        f"- {k['name']}: Current={_fmt(k['value'])}, Target={_fmt(k['target'])}, "
        f"Health={k['health']['status']} ({k['health']['pct']}%), "
        f"Trend={k['trend']['direction']} ({k['trend']['change_pct']:+.1f}%)"
        for k in kpis
    ])

    prompt = f"""You are a senior business intelligence analyst at SLMG Beverages.

Analyze the following REAL KPI data and produce a concise, data-driven executive brief.

Dashboard: {title}
Department: {department}

KPI Performance:
{kpi_data}

SWOT Summary: {swot.get('summary', '')}

Strengths: {'; '.join(swot.get('strengths', [])[:3])}
Weaknesses: {'; '.join(swot.get('weaknesses', [])[:3])}
Opportunities: {'; '.join(swot.get('opportunities', [])[:3])}
Threats: {'; '.join(swot.get('threats', [])[:3])}

Management Commentary: {commentary or 'None provided'}

Generate a structured JSON response with these exact keys:
{{
  "executive_summary": "2-3 sentence summary referencing actual numbers",
  "risk_analysis": "2-3 sentences identifying specific risks with KPI names and values",
  "strategic_recommendation": "2-3 actionable recommendations based on the data",
  "overall_rating": "Excellent|Good|Moderate|Critical",
  "priority_action": "Single most important action to take this week"
}}

IMPORTANT: Reference actual KPI names and values. Do not be generic."""

    try:
        payload = json.dumps({
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 800,
            "messages": [{"role": "user", "content": prompt}]
        }).encode('utf-8')

        req = urllib.request.Request(
            'https://api.anthropic.com/v1/messages',
            data=payload,
            headers={
                'Content-Type': 'application/json',
                'x-api-key': api_key,
                'anthropic-version': '2023-06-01'
            },
            method='POST'
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            response = json.loads(resp.read().decode('utf-8'))
            text = response['content'][0]['text']

            # Strip markdown if present
            text = text.strip()
            if text.startswith('```'):
                text = text.split('```')[1]
                if text.startswith('json'):
                    text = text[4:]
            text = text.strip()

            result = json.loads(text)
            result['source'] = 'AI-Powered (Claude)'
            return result

    except Exception as e:
        print(f'Anthropic API error: {e}')
        return _rule_based_summary(title, department, kpis, swot, commentary)


def _rule_based_summary(title: str, department: str, kpis: list, swot: dict, commentary: str) -> dict:
    """
    Rule-based analytical summary using real KPI data.
    Used when no API key is configured.
    """
    total = len(kpis)
    if total == 0:
        return {
            'executive_summary': 'No KPI data available for analysis.',
            'risk_analysis': 'Cannot assess risk without data.',
            'strategic_recommendation': 'Add KPI data to enable analysis.',
            'overall_rating': 'Critical',
            'priority_action': 'Add KPI targets and actuals.',
            'source': 'Rule-Based Engine'
        }

    green = [k for k in kpis if k['health']['status'] == 'GREEN']
    yellow = [k for k in kpis if k['health']['status'] == 'YELLOW']
    red = [k for k in kpis if k['health']['status'] == 'RED']
    declining = [k for k in kpis if k['trend']['direction'] == 'DOWN']
    improving = [k for k in kpis if k['trend']['direction'] == 'UP']

    # Overall rating
    health_score = swot.get('health_score', 0)
    if health_score >= 80:
        rating = 'Excellent'
    elif health_score >= 60:
        rating = 'Good'
    elif health_score >= 40:
        rating = 'Moderate'
    else:
        rating = 'Critical'

    # Executive Summary
    summary_parts = [f"The {department} department's {title} shows a health score of {health_score}%."]
    if green:
        summary_parts.append(
            f"{len(green)} KPIs are on target: {', '.join([k['name'] for k in green[:2]])} "
            f"{'and others' if len(green) > 2 else ''}."
        )
    if red:
        summary_parts.append(
            f"{len(red)} KPIs require immediate attention: {', '.join([k['name'] for k in red[:2]])}."
        )

    # Risk Analysis
    risk_parts = []
    if declining:
        for k in declining[:2]:
            risk_parts.append(
                f"{k['name']} is declining at {k['trend']['change_pct']:+.1f}% "
                f"(current: {_fmt(k['value'])}, target: {_fmt(k['target'])})"
            )
    if red:
        for k in red[:2]:
            risk_parts.append(
                f"{k['name']} is at {k['health']['pct']}% of target with "
                f"a shortfall of {_fmt(k['health']['gap'])}"
            )

    risk_analysis = "Risk areas: " + "; ".join(risk_parts) + "." if risk_parts else \
        f"No critical risks identified. {department} KPIs are largely stable."

    # Strategic Recommendation
    rec_parts = []
    if red:
        worst = sorted(red, key=lambda x: x['health']['pct'])[0]
        rec_parts.append(
            f"Prioritise {worst['name']} recovery — currently at {worst['health']['pct']}% "
            f"of target. Identify root cause of {_fmt(worst['health']['gap'])} gap."
        )
    if improving:
        best_improving = sorted(improving, key=lambda x: x['trend']['change_pct'], reverse=True)[0]
        rec_parts.append(
            f"Accelerate {best_improving['name']} momentum (+{best_improving['trend']['change_pct']:.1f}%) "
            f"to close remaining gap."
        )
    if green:
        rec_parts.append(
            f"Leverage performance in {', '.join([k['name'] for k in green[:2]])} "
            f"to offset underperforming areas."
        )

    recommendation = " | ".join(rec_parts) if rec_parts else \
        f"Maintain current trajectory in {department}. Focus on consistency across all KPIs."

    # Priority action
    if red and declining:
        worst = sorted(red, key=lambda x: x['health']['pct'])[0]
        priority = f"Escalate {worst['name']} to management — declining and {worst['health']['pct']}% of target."
    elif red:
        worst = sorted(red, key=lambda x: x['health']['pct'])[0]
        priority = f"Review {worst['name']} action plan — {_fmt(worst['health']['gap'])} below target."
    elif yellow:
        priority = f"Close gap on {yellow[0]['name']} to achieve full green status this period."
    else:
        priority = f"Sustain current performance across all {total} KPIs in {department}."

    return {
        'executive_summary': ' '.join(summary_parts),
        'risk_analysis': risk_analysis,
        'strategic_recommendation': recommendation,
        'overall_rating': rating,
        'priority_action': priority,
        'source': 'Rule-Based Engine (Add ANTHROPIC_API_KEY for AI-powered insights)'
    }

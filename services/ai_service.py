"""
AI Insight Engine — SLMG BI Portal
Supports: AI summaries, AI chat about dashboard data, rule-based fallback.
"""

import json
import os
import urllib.request
import urllib.error
from services.kpi_service import enrich_kpis
from services.swot_service import generate_swot, _fmt


def _call_claude(messages: list, system: str = '', max_tokens: int = 800) -> str:
    """Call Anthropic Claude API and return raw text."""
    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        raise ValueError('No API key configured')

    payload = json.dumps({
        'model': 'claude-haiku-4-5-20251001',
        'max_tokens': max_tokens,
        'system': system,
        'messages': messages
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
        return response['content'][0]['text']


def generate_ai_summary(dashboard_title: str, department: str, kpis: list, commentary: str = '') -> dict:
    """Generate AI executive summary. Falls back to rule-based if no API key."""
    try:
        enriched = enrich_kpis(kpis)
    except Exception:
        enriched = []
    try:
        swot = generate_swot(dashboard_title, department, kpis)
    except Exception:
        swot = {}

    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if api_key:
        try:
            return _call_anthropic_summary(api_key, dashboard_title, department, enriched, swot, commentary)
        except Exception as e:
            print(f'Anthropic API error: {e}')

    return _rule_based_summary(dashboard_title, department, enriched, swot, commentary)


def generate_ai_chat_response(question: str, user_name: str, user_department: str,
                               dashboards: list, conversation_history: list) -> str:
    """
    AI chat: answer questions about dashboard/KPI data.
    dashboards: list of Dashboard model objects
    conversation_history: list of {role, content} dicts
    """
    # Build rich context about all available dashboards
    context_parts = []
    for d in dashboards:
        try:
            enriched = enrich_kpis(d.kpis)
        except Exception:
            enriched = []

        kpi_lines = []
        for k in enriched:
            health = k.get('health', {})
            trend = k.get('trend', {})
            kpi_lines.append(
                f"  - {k.get('name', 'KPI')}: {_fmt(k.get('value', 0))} "
                f"(target: {_fmt(k.get('target', 0))}, "
                f"health: {health.get('status', 'N/A')} at {health.get('pct', 0)}%, "
                f"trend: {trend.get('direction', 'N/A')} {trend.get('change_pct', 0):+.1f}%)"
            )

        context_parts.append(
            f"Dashboard: {d.title}\n"
            f"Department: {d.department} | Category: {d.category}\n"
            f"Embed URL: {d.embed_url}\n"
            f"KPIs:\n" + ('\n'.join(kpi_lines) if kpi_lines else '  (No KPI data)') + '\n'
            f"Commentary: {d.commentary or 'None'}\n"
            f"AI Context: {d.ai_context or 'None'}\n"
            f"Tags: {', '.join(d.tags) if d.tags else 'None'}"
        )

    full_context = '\n\n---\n\n'.join(context_parts) if context_parts else 'No dashboard data available.'

    system_prompt = f"""You are SLMG BI Assistant, an expert business intelligence analyst for SLMG Beverages.
You have access to the following dashboard data and KPI metrics. Answer questions precisely and helpfully.

USER: {user_name} (Department: {user_department})

AVAILABLE DASHBOARD DATA:
{full_context}

INSTRUCTIONS:
- Answer questions based ONLY on the data provided above
- Be specific: reference actual KPI names, values, percentages, and trends
- If data is insufficient, say so clearly  
- For "what is" questions about dashboards: describe the content and KPIs
- For performance questions: provide specific numbers and health status
- For recommendations: base them on actual data gaps and trends
- Keep answers concise but data-rich (2-4 sentences unless more detail needed)
- Format numbers clearly (e.g., ₹4.8M, 87%, 32 days)
- If asked about the embed URL or how to view a dashboard, provide the URL
"""

    # Build messages array with history
    messages = []
    for h in conversation_history[-10:]:  # Last 10 messages for context
        if h.get('role') in ('user', 'assistant') and h.get('content'):
            messages.append({'role': h['role'], 'content': str(h['content'])})

    messages.append({'role': 'user', 'content': question})

    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if api_key:
        try:
            return _call_claude(messages, system=system_prompt, max_tokens=600)
        except Exception as e:
            print(f'AI chat error: {e}')

    # Rule-based fallback
    return _rule_based_chat(question, dashboards, context_parts)


def _rule_based_chat(question: str, dashboards: list, context_parts: list) -> str:
    """Simple rule-based fallback when no API key."""
    q = question.lower()

    if not dashboards:
        return "No dashboard data is available to answer your question. Please add dashboards with KPI data first."

    # Identify relevant dashboard
    relevant = None
    for d in dashboards:
        if d.title.lower() in q or d.department.lower() in q:
            relevant = d
            break
    target = relevant or dashboards[0]

    try:
        enriched = enrich_kpis(target.kpis)
    except Exception:
        enriched = []

    if any(w in q for w in ['worst', 'risk', 'critical', 'problem', 'issue', 'bad']):
        reds = [k for k in enriched if k.get('health', {}).get('status') == 'RED']
        if reds:
            worst = min(reds, key=lambda x: x.get('health', {}).get('pct', 100))
            return (f"The highest-risk KPI in {target.title} is **{worst['name']}** — "
                    f"currently at {worst.get('health', {}).get('pct', 0):.1f}% of target "
                    f"({_fmt(worst.get('value', 0))} vs target {_fmt(worst.get('target', 0))}). "
                    f"Trend: {worst.get('trend', {}).get('direction', 'N/A')} "
                    f"({worst.get('trend', {}).get('change_pct', 0):+.1f}%).")
        return f"No critical KPIs found in {target.title} — all KPIs are performing at or near target."

    if any(w in q for w in ['best', 'top', 'highest', 'performing well', 'green']):
        greens = [k for k in enriched if k.get('health', {}).get('status') == 'GREEN']
        if greens:
            best = max(greens, key=lambda x: x.get('health', {}).get('pct', 0))
            return (f"The best performing KPI in {target.title} is **{best['name']}** — "
                    f"at {best.get('health', {}).get('pct', 0):.1f}% of target "
                    f"({_fmt(best.get('value', 0))} vs target {_fmt(best.get('target', 0))}).")
        return f"No KPIs in {target.title} are currently meeting their targets."

    if any(w in q for w in ['how many', 'count', 'total', 'summary']):
        green = sum(1 for k in enriched if k.get('health', {}).get('status') == 'GREEN')
        yellow = sum(1 for k in enriched if k.get('health', {}).get('status') == 'YELLOW')
        red = sum(1 for k in enriched if k.get('health', {}).get('status') == 'RED')
        return (f"**{target.title}** has {len(enriched)} KPIs: "
                f"{green} on target (green), {yellow} near target (yellow), {red} below target (red). "
                f"There are {len(dashboards)} total dashboards accessible to you.")

    if any(w in q for w in ['trend', 'improving', 'declining', 'up', 'down']):
        improving = [k for k in enriched if k.get('trend', {}).get('direction') == 'UP']
        declining = [k for k in enriched if k.get('trend', {}).get('direction') == 'DOWN']
        parts = []
        if improving:
            parts.append(f"{len(improving)} improving: {', '.join(k['name'] for k in improving[:3])}")
        if declining:
            parts.append(f"{len(declining)} declining: {', '.join(k['name'] for k in declining[:3])}")
        return f"In {target.title}: " + (' | '.join(parts) if parts else "All KPIs are stable with no significant trend changes.")

    # Default: general summary
    green = sum(1 for k in enriched if k.get('health', {}).get('status') == 'GREEN')
    return (f"**{target.title}** ({target.department} dept): {len(enriched)} KPIs tracked, "
            f"{green} of {len(enriched)} are on target. "
            f"Commentary: {target.commentary or 'No commentary added.'} "
            f"For more specific insights, please ask about specific KPIs, trends, or risk areas.")


def _call_anthropic_summary(api_key, title, department, kpis, swot, commentary):
    kpi_data = "\n".join([
        f"- {k['name']}: Current={_fmt(k.get('value',0))}, Target={_fmt(k.get('target',0))}, "
        f"Health={k.get('health',{}).get('status','N/A')} ({k.get('health',{}).get('pct',0)}%), "
        f"Trend={k.get('trend',{}).get('direction','N/A')} ({k.get('trend',{}).get('change_pct',0):+.1f}%)"
        for k in kpis
    ]) if kpis else "No KPI data available."

    prompt = f"""You are a senior BI analyst at SLMG Beverages. Analyze this real KPI data and provide a JSON executive brief.

Dashboard: {title}
Department: {department}

KPI Performance:
{kpi_data}

Management Commentary: {commentary or 'None'}

Return ONLY valid JSON with these exact keys:
{{
  "executive_summary": "2-3 sentences referencing actual numbers",
  "risk_analysis": "2-3 sentences with specific KPI names and values",
  "strategic_recommendation": "2-3 actionable recommendations from the data",
  "overall_rating": "Excellent|Good|Moderate|Critical",
  "priority_action": "Single most important action this week"
}}"""

    try:
        text = _call_claude([{'role': 'user', 'content': prompt}], max_tokens=800)
        text = text.strip()
        if text.startswith('```'):
            text = text.split('```')[1]
            if text.startswith('json'):
                text = text[4:]
        result = json.loads(text.strip())
        result['source'] = 'AI-Powered (Claude)'
        return result
    except Exception:
        raise


def _rule_based_summary(title, department, kpis, swot, commentary):
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

    green = [k for k in kpis if k.get('health', {}).get('status') == 'GREEN']
    yellow = [k for k in kpis if k.get('health', {}).get('status') == 'YELLOW']
    red = [k for k in kpis if k.get('health', {}).get('status') == 'RED']
    declining = [k for k in kpis if k.get('trend', {}).get('direction') == 'DOWN']
    improving = [k for k in kpis if k.get('trend', {}).get('direction') == 'UP']

    health_score = swot.get('health_score', 0)
    rating = 'Excellent' if health_score >= 80 else 'Good' if health_score >= 60 else 'Moderate' if health_score >= 40 else 'Critical'

    summary_parts = [f"The {department} department's {title} shows a health score of {health_score}%."]
    if green:
        summary_parts.append(f"{len(green)} KPIs are on target: {', '.join([k['name'] for k in green[:2]])}.")
    if red:
        summary_parts.append(f"{len(red)} KPIs require attention: {', '.join([k['name'] for k in red[:2]])}.")

    risk_parts = []
    for k in (declining + red)[:3]:
        h = k.get('health', {})
        t = k.get('trend', {})
        risk_parts.append(f"{k['name']} at {h.get('pct', 0):.1f}% of target, trend: {t.get('direction', 'N/A')}")

    risk = "Risk areas: " + "; ".join(risk_parts) + "." if risk_parts else f"No critical risks in {department}."

    rec_parts = []
    if red:
        worst = min(red, key=lambda x: x.get('health', {}).get('pct', 100))
        rec_parts.append(f"Prioritise {worst['name']} recovery — currently at {worst.get('health', {}).get('pct', 0):.1f}% of target.")
    if improving:
        best = max(improving, key=lambda x: x.get('trend', {}).get('change_pct', 0))
        rec_parts.append(f"Accelerate {best['name']} momentum (+{best.get('trend', {}).get('change_pct', 0):.1f}%).")

    priority = f"Escalate {red[0]['name']} to management." if red else f"Maintain current performance across {total} KPIs."

    return {
        'executive_summary': ' '.join(summary_parts),
        'risk_analysis': risk,
        'strategic_recommendation': ' | '.join(rec_parts) if rec_parts else f"Maintain trajectory in {department}.",
        'overall_rating': rating,
        'priority_action': priority,
        'source': 'Rule-Based Engine (set ANTHROPIC_API_KEY for AI-powered insights)'
    }

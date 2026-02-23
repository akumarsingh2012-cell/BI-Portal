"""
AI Insight Engine — SLMG BI Portal
Supports: AI summaries, AI chat about dashboard data,
          uploaded CSV/Excel data analysis, charts & tables,
          semantic model context.
"""

import json
import os
import urllib.request
import urllib.error
from services.kpi_service import enrich_kpis
from services.swot_service import generate_swot, _fmt


def _call_claude(messages: list, system: str = '', max_tokens: int = 1000) -> str:
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


def generate_ai_chat_response(
    question: str,
    user_name: str,
    user_department: str,
    dashboards: list,
    conversation_history: list,
    uploaded_data: dict = None,
    semantic_model_url: str = ''
) -> str:
    """
    AI chat with full data analysis support.
    - uploaded_data: {filename, rows (list of dicts), columns, total_rows}
    - dashboards: list of Dashboard model objects
    - Returns text answer, may include ```json{chart/table data}``` blocks
    """

    # ── Build uploaded data context ──────────────────────────────
    uploaded_context = ''
    if uploaded_data and uploaded_data.get('rows'):
        rows = uploaded_data['rows']
        cols = uploaded_data.get('columns', list(rows[0].keys()) if rows else [])
        filename = uploaded_data.get('filename', 'uploaded_file')
        total = uploaded_data.get('total_rows', len(rows))

        # Column stats
        col_stats = []
        for col in cols[:15]:  # max 15 cols
            values = [r.get(col, '') for r in rows if r.get(col, '') != '']
            # Try numeric
            nums = []
            for v in values:
                try:
                    nums.append(float(str(v).replace(',', '')))
                except:
                    pass
            if nums:
                col_stats.append(f"  {col}: numeric, min={min(nums):.2f}, max={max(nums):.2f}, avg={sum(nums)/len(nums):.2f}, count={len(nums)}")
            else:
                unique_vals = list(set(str(v) for v in values[:20]))[:8]
                col_stats.append(f"  {col}: text, unique_values={unique_vals[:5]}, count={len(values)}")

        # Sample rows
        sample_rows = []
        for r in rows[:5]:
            sample_rows.append(str({k: v for k, v in list(r.items())[:10]}))

        uploaded_context = f"""
UPLOADED DATASET: {filename}
Total rows: {total} | Columns: {', '.join(cols[:15])}

COLUMN STATISTICS:
{chr(10).join(col_stats)}

SAMPLE DATA (first 5 rows):
{chr(10).join(sample_rows)}

ALL DATA (first {min(len(rows), 100)} rows for analysis):
{json.dumps(rows[:100], ensure_ascii=False)}
"""

    # ── Build dashboard context ──────────────────────────────────
    dash_context_parts = []
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

        dash_context_parts.append(
            f"Dashboard: {d.title} | Dept: {d.department} | Category: {d.category}\n"
            f"KPIs:\n" + ('\n'.join(kpi_lines) if kpi_lines else '  (No KPI data)') + '\n'
            f"Commentary: {d.commentary or 'None'}\n"
            f"AI Context: {d.ai_context or 'None'}"
        )

    dash_context = '\n\n---\n\n'.join(dash_context_parts) if dash_context_parts else 'No dashboard data available.'

    # ── Semantic model context ───────────────────────────────────
    semantic_context = ''
    if semantic_model_url:
        semantic_context = f"\nSEMANTIC MODEL URL: {semantic_model_url}\n(User has connected a semantic/data model at this URL for additional context)\n"

    # ── System prompt ────────────────────────────────────────────
    system_prompt = f"""You are SLMG BI Assistant, an expert business intelligence analyst and data scientist for SLMG Beverages.

USER: {user_name} (Department: {user_department})

{f"UPLOADED DATA CONTEXT:{uploaded_context}" if uploaded_context else ""}
{f"SEMANTIC MODEL:{semantic_context}" if semantic_context else ""}
DASHBOARD DATA:
{dash_context}

INSTRUCTIONS:
1. Answer questions using the data provided above
2. When asked for charts/graphs, respond with a JSON block in this format:
   ```json
   {{"chart_type": "bar", "labels": ["A","B","C"], "values": [100,200,150], "title": "Chart Title"}}
   ```
   Supported chart_types: bar, pie, line (will render as bar)

3. When asked for tables, respond with:
   ```json
   {{"table_headers": ["Col1","Col2"], "table_rows": [["val1","val2"],["val3","val4"]], "title": "Table Title"}}
   ```

4. For uploaded CSV/Excel data:
   - Analyse the actual data rows provided
   - Calculate stats, find trends, identify outliers
   - Answer questions precisely with real numbers from the data

5. Be specific with numbers — reference actual values from data
6. Format large numbers clearly (₹4.8M, 87%, 32 days)
7. Hindi/English mix is fine — match the user's language style
8. If asked "graph banao" or "chart dikhao" — always return chart JSON
9. If asked "table banao" or "summary table" — always return table JSON
"""

    messages = []
    for h in conversation_history[-8:]:
        if h.get('role') in ('user', 'assistant') and h.get('content'):
            messages.append({'role': h['role'], 'content': str(h['content'])})
    messages.append({'role': 'user', 'content': question})

    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if api_key:
        try:
            return _call_claude(messages, system=system_prompt, max_tokens=1000)
        except Exception as e:
            print(f'AI chat error: {e}')

    # ── Rule-based fallback ──────────────────────────────────────
    return _rule_based_chat_with_data(question, dashboards, uploaded_data)


def _rule_based_chat_with_data(question: str, dashboards: list, uploaded_data: dict = None) -> str:
    """Rule-based fallback when no API key."""
    q = question.lower()

    # Uploaded data analysis
    if uploaded_data and uploaded_data.get('rows'):
        rows = uploaded_data['rows']
        cols = uploaded_data.get('columns', list(rows[0].keys()) if rows else [])
        filename = uploaded_data.get('filename', 'file')

        if any(w in q for w in ['summary', 'overview', 'kitne', 'total', 'count']):
            return (f"**{filename}** mein {len(rows)} rows aur {len(cols)} columns hain.\n\n"
                    f"Columns: {', '.join(cols[:10])}\n\n"
                    f"Pehle 3 rows:\n" +
                    '\n'.join([str({k: v for k, v in list(r.items())[:5]}) for r in rows[:3]]))

        if any(w in q for w in ['chart', 'graph', 'bar', 'plot', 'dikhao']):
            # Try to make a simple bar chart from first numeric column grouped by first text column
            num_cols = []
            for col in cols:
                try:
                    float(str(rows[0].get(col, '')).replace(',', ''))
                    num_cols.append(col)
                except:
                    pass
            if num_cols and cols:
                label_col = cols[0]
                val_col = num_cols[0]
                labels = [str(r.get(label_col, ''))[:20] for r in rows[:8]]
                values = []
                for r in rows[:8]:
                    try:
                        values.append(float(str(r.get(val_col, 0)).replace(',', '')))
                    except:
                        values.append(0)
                chart_json = json.dumps({"chart_type": "bar", "labels": labels, "values": values, "title": f"{val_col} by {label_col}"})
                return f"Yeh raha **{val_col}** ka chart:\n\n```json\n{chart_json}\n```"

        return f"**{filename}** uploaded hai ({len(rows)} rows). ANTHROPIC_API_KEY set karo detailed analysis ke liye."

    # Dashboard fallback
    if not dashboards:
        return "Koi dashboard data available nahi hai. Pehle koi dashboard add karo ya CSV file upload karo."

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

    green = sum(1 for k in enriched if k.get('health', {}).get('status') == 'GREEN')
    return (f"**{target.title}** ({target.department}): {len(enriched)} KPIs tracked, "
            f"{green}/{len(enriched)} on target. "
            f"Better insights ke liye ANTHROPIC_API_KEY set karo.")


def _call_anthropic_summary(api_key, title, department, kpis, swot, commentary):
    kpi_data = "\n".join([
        f"- {k['name']}: Current={_fmt(k.get('value',0))}, Target={_fmt(k.get('target',0))}, "
        f"Health={k.get('health',{}).get('status','N/A')} ({k.get('health',{}).get('pct',0)}%), "
        f"Trend={k.get('trend',{}).get('direction','N/A')} ({k.get('trend',{}).get('change_pct',0):+.1f}%)"
        for k in kpis
    ]) if kpis else "No KPI data available."

    prompt = f"""You are a senior BI analyst at SLMG Beverages. Analyze this KPI data and return a JSON executive brief.

Dashboard: {title} | Department: {department}
KPI Performance:
{kpi_data}
Management Commentary: {commentary or 'None'}

Return ONLY valid JSON with these exact keys:
{{
  "executive_summary": "2-3 sentences with actual numbers",
  "risk_analysis": "2-3 sentences with specific KPI names",
  "strategic_recommendation": "2-3 actionable items",
  "overall_rating": "Excellent|Good|Moderate|Critical",
  "priority_action": "Single most important action"
}}"""

    try:
        text = _call_claude([{'role': 'user', 'content': prompt}], max_tokens=600)
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

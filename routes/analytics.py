"""
Analytics Routes — KPI, SWOT, AI Insights
"""

from flask import Blueprint, request, jsonify
from models import Dashboard
from middleware.auth_middleware import jwt_required_custom, get_current_user
from services.kpi_service import get_dashboard_kpi_summary, enrich_kpis
from services.swot_service import generate_swot
from services.ai_service import generate_ai_summary

analytics_bp = Blueprint('analytics', __name__)


def _check_dashboard_access(user, dashboard):
    """Verify user can access this dashboard."""
    return user.role == 'Admin' or dashboard.department == user.department


@analytics_bp.route('/kpis/<int:dashboard_id>', methods=['GET'])
@jwt_required_custom
def get_kpis(dashboard_id):
    """Get enriched KPIs with health + trend for a dashboard."""
    user = get_current_user()
    dashboard = Dashboard.query.get_or_404(dashboard_id)

    if not _check_dashboard_access(user, dashboard):
        return jsonify({'error': 'Access denied — department restriction'}), 403

    summary = get_dashboard_kpi_summary(dashboard.kpis)
    return jsonify({
        'dashboard_id': dashboard_id,
        'dashboard_title': dashboard.title,
        'department': dashboard.department,
        **summary
    }), 200


@analytics_bp.route('/swot/<int:dashboard_id>', methods=['GET'])
@jwt_required_custom
def get_swot(dashboard_id):
    """Generate SWOT analysis for a dashboard."""
    user = get_current_user()
    dashboard = Dashboard.query.get_or_404(dashboard_id)

    if not _check_dashboard_access(user, dashboard):
        return jsonify({'error': 'Access denied'}), 403

    swot = generate_swot(dashboard.title, dashboard.department, dashboard.kpis)
    return jsonify({'swot': swot, 'dashboard_id': dashboard_id}), 200


@analytics_bp.route('/ai-summary/<int:dashboard_id>', methods=['POST'])
@jwt_required_custom
def get_ai_summary(dashboard_id):
    """Generate AI-powered executive summary."""
    user = get_current_user()
    dashboard = Dashboard.query.get_or_404(dashboard_id)

    if not _check_dashboard_access(user, dashboard):
        return jsonify({'error': 'Access denied'}), 403

    try:
        summary = generate_ai_summary(
            dashboard.title,
            dashboard.department,
            dashboard.kpis,
            dashboard.commentary
        )
        return jsonify({'summary': summary, 'dashboard_id': dashboard_id}), 200
    except Exception as e:
        return jsonify({'error': f'AI summary failed: {str(e)}'}), 500


@analytics_bp.route('/compare', methods=['POST'])
@jwt_required_custom
def compare_dashboards():
    """Compare two dashboards side by side."""
    user = get_current_user()
    data = request.get_json()
    ids = data.get('dashboard_ids', [])

    if len(ids) != 2:
        return jsonify({'error': 'Exactly 2 dashboard IDs required'}), 400

    result = []
    for did in ids:
        dashboard = Dashboard.query.get(did)
        if not dashboard:
            return jsonify({'error': f'Dashboard {did} not found'}), 404
        if not _check_dashboard_access(user, dashboard):
            return jsonify({'error': f'Access denied to dashboard {did}'}), 403

        d = dashboard.to_dict()
        d['kpis'] = enrich_kpis(dashboard.kpis)
        d['kpi_summary'] = get_dashboard_kpi_summary(dashboard.kpis)
        result.append(d)

    return jsonify({'comparison': result}), 200


@analytics_bp.route('/portfolio', methods=['GET'])
@jwt_required_custom
def get_portfolio_summary():
    """Get aggregate portfolio health across all accessible dashboards."""
    user = get_current_user()

    from models import Dashboard as D
    from middleware.auth_middleware import department_filter
    query = D.query
    query = department_filter(query, user, D)
    dashboards = query.all()

    total_dashboards = len(dashboards)
    all_kpis = []
    for d in dashboards:
        enriched = enrich_kpis(d.kpis)
        all_kpis.extend(enriched)

    total_kpis = len(all_kpis)
    green = sum(1 for k in all_kpis if k['health']['status'] == 'GREEN')
    yellow = sum(1 for k in all_kpis if k['health']['status'] == 'YELLOW')
    red = sum(1 for k in all_kpis if k['health']['status'] == 'RED')

    portfolio_score = round(((green * 100 + yellow * 70 + red * 30) / (total_kpis * 100)) * 100, 1) if total_kpis > 0 else 0

    by_dept = {}
    for d in dashboards:
        dept = d.department
        if dept not in by_dept:
            by_dept[dept] = {'dashboards': 0, 'kpis': 0, 'green': 0, 'red': 0}
        by_dept[dept]['dashboards'] += 1
        enriched = enrich_kpis(d.kpis)
        by_dept[dept]['kpis'] += len(enriched)
        by_dept[dept]['green'] += sum(1 for k in enriched if k['health']['status'] == 'GREEN')
        by_dept[dept]['red'] += sum(1 for k in enriched if k['health']['status'] == 'RED')

    return jsonify({
        'total_dashboards': total_dashboards,
        'total_kpis': total_kpis,
        'green': green,
        'yellow': yellow,
        'red': red,
        'portfolio_score': portfolio_score,
        'by_department': by_dept
    }), 200

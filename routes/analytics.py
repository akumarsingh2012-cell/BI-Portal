"""
Analytics Routes — KPI, SWOT, AI Insights, AI Chat (with file data support)
"""

from flask import Blueprint, request, jsonify
from models import Dashboard, AIConversation
from middleware.auth_middleware import jwt_required_custom, get_current_user
from services.kpi_service import get_dashboard_kpi_summary, enrich_kpis
from services.swot_service import generate_swot
from services.ai_service import generate_ai_summary, generate_ai_chat_response
from app import db

analytics_bp = Blueprint('analytics', __name__)


def _check_dashboard_access(user, dashboard):
    return user.role == 'Admin' or dashboard.department == user.department or dashboard.is_public


@analytics_bp.route('/kpis/<int:dashboard_id>', methods=['GET'])
@jwt_required_custom
def get_kpis(dashboard_id):
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401
    try:
        dashboard = Dashboard.query.get_or_404(dashboard_id)
    except Exception:
        return jsonify({'error': 'Dashboard not found'}), 404

    if not _check_dashboard_access(user, dashboard):
        return jsonify({'error': 'Access denied'}), 403

    try:
        summary = get_dashboard_kpi_summary(dashboard.kpis)
        return jsonify({
            'dashboard_id': dashboard_id,
            'dashboard_title': dashboard.title,
            'department': dashboard.department,
            **summary
        }), 200
    except Exception as e:
        return jsonify({'error': f'KPI analysis failed: {str(e)}'}), 500


@analytics_bp.route('/swot/<int:dashboard_id>', methods=['GET'])
@jwt_required_custom
def get_swot(dashboard_id):
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401
    try:
        dashboard = Dashboard.query.get_or_404(dashboard_id)
    except Exception:
        return jsonify({'error': 'Dashboard not found'}), 404

    if not _check_dashboard_access(user, dashboard):
        return jsonify({'error': 'Access denied'}), 403

    try:
        swot = generate_swot(dashboard.title, dashboard.department, dashboard.kpis)
        return jsonify({'swot': swot, 'dashboard_id': dashboard_id}), 200
    except Exception as e:
        return jsonify({'error': f'SWOT generation failed: {str(e)}'}), 500


@analytics_bp.route('/ai-summary/<int:dashboard_id>', methods=['POST'])
@jwt_required_custom
def get_ai_summary(dashboard_id):
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401
    try:
        dashboard = Dashboard.query.get_or_404(dashboard_id)
    except Exception:
        return jsonify({'error': 'Dashboard not found'}), 404

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


@analytics_bp.route('/ai-chat', methods=['POST'])
@jwt_required_custom
def ai_chat():
    """
    AI chat — supports:
    1. Dashboard KPI data
    2. User-uploaded CSV/Excel data (uploaded_data in payload)
    3. Semantic model URL
    """
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    question = data.get('question', '').strip()
    dashboard_id = data.get('dashboard_id')
    conversation_history = data.get('history', [])
    uploaded_data = data.get('uploaded_data')        # {filename, rows, columns, total_rows}
    semantic_model_url = data.get('semantic_model_url', '')

    if not question:
        return jsonify({'error': 'Question is required'}), 400

    # Gather dashboard context
    dashboards_context = []
    if dashboard_id:
        try:
            d = Dashboard.query.get(int(dashboard_id))
            if d and _check_dashboard_access(user, d):
                dashboards_context.append(d)
        except Exception:
            pass
    else:
        from middleware.auth_middleware import department_filter
        query = Dashboard.query
        query = department_filter(query, user, Dashboard)
        dashboards_context = query.all()

    try:
        response = generate_ai_chat_response(
            question=question,
            user_name=user.name,
            user_department=user.department,
            dashboards=dashboards_context,
            conversation_history=conversation_history,
            uploaded_data=uploaded_data,
            semantic_model_url=semantic_model_url
        )

        sources = []
        if uploaded_data:
            sources.append(f"📁 {uploaded_data.get('filename', 'Uploaded file')}")
        sources += [d.title for d in dashboards_context]

        return jsonify({'answer': response, 'sources': sources}), 200
    except Exception as e:
        return jsonify({'error': f'AI chat failed: {str(e)}'}), 500


@analytics_bp.route('/compare', methods=['POST'])
@jwt_required_custom
def compare_dashboards():
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json()
    ids = data.get('dashboard_ids', [])

    if len(ids) < 2:
        return jsonify({'error': 'At least 2 dashboard IDs required'}), 400
    if len(ids) > 4:
        return jsonify({'error': 'Maximum 4 dashboards can be compared at once'}), 400

    result = []
    for did in ids:
        try:
            dashboard = Dashboard.query.get(int(did))
        except Exception:
            return jsonify({'error': f'Invalid dashboard ID: {did}'}), 400
        if not dashboard:
            return jsonify({'error': f'Dashboard {did} not found'}), 404
        if not _check_dashboard_access(user, dashboard):
            return jsonify({'error': f'Access denied to dashboard {did}'}), 403

        try:
            d = dashboard.to_dict()
            d['kpis'] = enrich_kpis(dashboard.kpis)
            d['kpi_summary'] = get_dashboard_kpi_summary(dashboard.kpis)
            d['swot'] = generate_swot(dashboard.title, dashboard.department, dashboard.kpis)
            result.append(d)
        except Exception as e:
            return jsonify({'error': f'Failed to process dashboard {did}: {str(e)}'}), 500

    return jsonify({'comparison': result, 'count': len(result)}), 200


@analytics_bp.route('/portfolio', methods=['GET'])
@jwt_required_custom
def get_portfolio_summary():
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    from middleware.auth_middleware import department_filter
    query = Dashboard.query
    query = department_filter(query, user, Dashboard)
    dashboards = query.all()

    total_dashboards = len(dashboards)
    all_kpis = []
    dept_stats = {}

    for d in dashboards:
        try:
            enriched = enrich_kpis(d.kpis)
        except Exception:
            enriched = []
        all_kpis.extend(enriched)

        dept = d.department
        if dept not in dept_stats:
            dept_stats[dept] = {'dashboards': 0, 'kpis': 0, 'green': 0, 'yellow': 0, 'red': 0}
        dept_stats[dept]['dashboards'] += 1
        dept_stats[dept]['kpis'] += len(enriched)
        dept_stats[dept]['green'] += sum(1 for k in enriched if k.get('health', {}).get('status') == 'GREEN')
        dept_stats[dept]['yellow'] += sum(1 for k in enriched if k.get('health', {}).get('status') == 'YELLOW')
        dept_stats[dept]['red'] += sum(1 for k in enriched if k.get('health', {}).get('status') == 'RED')

    total_kpis = len(all_kpis)
    green = sum(1 for k in all_kpis if k.get('health', {}).get('status') == 'GREEN')
    yellow = sum(1 for k in all_kpis if k.get('health', {}).get('status') == 'YELLOW')
    red = sum(1 for k in all_kpis if k.get('health', {}).get('status') == 'RED')

    portfolio_score = round(((green * 100 + yellow * 70 + red * 30) / (total_kpis * 100)) * 100, 1) if total_kpis > 0 else 0

    return jsonify({
        'total_dashboards': total_dashboards,
        'total_kpis': total_kpis,
        'green': green,
        'yellow': yellow,
        'red': red,
        'portfolio_score': portfolio_score,
        'by_department': dept_stats
    }), 200

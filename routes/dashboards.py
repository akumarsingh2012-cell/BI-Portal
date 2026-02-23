"""
Dashboard Routes — CRUD, Bookmarks, Notes
"""

import json
from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity
from datetime import datetime
from app import db
from models import Dashboard, Note
from middleware.auth_middleware import (
    jwt_required_custom, admin_required, analyst_or_admin_required,
    get_current_user, department_filter, log_activity
)
from services.kpi_service import get_dashboard_kpi_summary, enrich_kpis

dash_bp = Blueprint('dashboards', __name__)


@dash_bp.route('/', methods=['GET'])
@jwt_required_custom
def get_dashboards():
    """
    Get all dashboards for current user.
    CORE SECURITY: Department-filtered on backend.
    Admin sees all. Others see only their department.
    """
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    query = Dashboard.query
    query = department_filter(query, user, Dashboard)  # ENFORCE DEPARTMENT SECURITY

    # Optional filters
    category = request.args.get('category')
    search = request.args.get('search', '').strip()
    department = request.args.get('department')

    if category:
        query = query.filter(Dashboard.category == category)
    if department and user.role == 'Admin':
        query = query.filter(Dashboard.department == department)
    if search:
        query = query.filter(
            (Dashboard.title.ilike(f'%{search}%')) |
            (Dashboard.category.ilike(f'%{search}%')) |
            (Dashboard.tags_raw.ilike(f'%{search}%'))
        )

    dashboards = query.order_by(Dashboard.sort_order, Dashboard.created_at.desc()).all()

    # Enrich with KPI summary
    result = []
    for d in dashboards:
        d_dict = d.to_dict()
        kpi_summary = get_dashboard_kpi_summary(d.kpis)
        d_dict['kpi_summary'] = kpi_summary
        d_dict['is_bookmarked'] = d.id in user.bookmarks
        result.append(d_dict)

    return jsonify({'dashboards': result, 'total': len(result)}), 200


@dash_bp.route('/<int:dashboard_id>', methods=['GET'])
@jwt_required_custom
def get_dashboard(dashboard_id):
    """Get single dashboard with full KPI enrichment."""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    dashboard = Dashboard.query.get_or_404(dashboard_id)

    # Department access check
    if user.role != 'Admin' and dashboard.department != user.department:
        return jsonify({'error': 'Access denied — department restriction'}), 403

    d_dict = dashboard.to_dict()
    d_dict['kpis'] = enrich_kpis(dashboard.kpis)
    d_dict['kpi_summary'] = get_dashboard_kpi_summary(dashboard.kpis)
    d_dict['is_bookmarked'] = dashboard.id in user.bookmarks

    return jsonify({'dashboard': d_dict}), 200


@dash_bp.route('/', methods=['POST'])
@analyst_or_admin_required
def create_dashboard():
    """Create new dashboard. Admin/Analyst only."""
    user = get_current_user()
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # Validation
    required = ['title', 'embed_url', 'department', 'category']
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({'error': f'Missing required fields: {", ".join(missing)}'}), 400

    # Non-admin can only create for their department
    if user.role != 'Admin' and data.get('department') != user.department:
        return jsonify({'error': 'You can only create dashboards for your department'}), 403

    dashboard = Dashboard(
        title=data['title'].strip(),
        embed_url=data['embed_url'].strip(),
        department=data['department'],
        category=data['category'].strip(),
        tags=data.get('tags', []),
        kpis=data.get('kpis', []),
        commentary=data.get('commentary', ''),
        created_by=user.email,
        sort_order=data.get('sort_order', 0)
    )

    db.session.add(dashboard)
    db.session.commit()

    log_activity(user.id, f"Created dashboard: {dashboard.title}", 'dashboard', dashboard.id)

    return jsonify({'message': 'Dashboard created', 'dashboard': dashboard.to_dict()}), 201


@dash_bp.route('/<int:dashboard_id>', methods=['PUT'])
@analyst_or_admin_required
def update_dashboard(dashboard_id):
    """Update dashboard."""
    user = get_current_user()
    dashboard = Dashboard.query.get_or_404(dashboard_id)

    # Department check
    if user.role != 'Admin' and dashboard.department != user.department:
        return jsonify({'error': 'Access denied'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    updatable = ['title', 'embed_url', 'category', 'commentary']
    for field in updatable:
        if field in data:
            setattr(dashboard, field, data[field])

    if 'tags' in data:
        dashboard.tags = data['tags']
    if 'kpis' in data:
        dashboard.kpis = data['kpis']
    if 'department' in data and user.role == 'Admin':
        dashboard.department = data['department']
    if 'sort_order' in data:
        dashboard.sort_order = data['sort_order']

    dashboard.updated_at = datetime.utcnow()
    db.session.commit()

    log_activity(user.id, f"Updated dashboard: {dashboard.title}", 'dashboard', dashboard_id)

    return jsonify({'message': 'Dashboard updated', 'dashboard': dashboard.to_dict()}), 200


@dash_bp.route('/<int:dashboard_id>', methods=['DELETE'])
@admin_required
def delete_dashboard(dashboard_id):
    """Delete dashboard. Admin only."""
    user = get_current_user()
    dashboard = Dashboard.query.get_or_404(dashboard_id)
    title = dashboard.title
    db.session.delete(dashboard)
    db.session.commit()
    log_activity(user.id, f"Deleted dashboard: {title}", 'dashboard', dashboard_id)
    return jsonify({'message': f'Dashboard "{title}" deleted'}), 200


@dash_bp.route('/<int:dashboard_id>/bookmark', methods=['POST'])
@jwt_required_custom
def toggle_bookmark(dashboard_id):
    """Toggle bookmark for a dashboard."""
    user = get_current_user()
    dashboard = Dashboard.query.get_or_404(dashboard_id)

    # Department check
    if user.role != 'Admin' and dashboard.department != user.department:
        return jsonify({'error': 'Access denied'}), 403

    bookmarks = user.bookmarks
    if dashboard_id in bookmarks:
        bookmarks.remove(dashboard_id)
        action = 'removed'
    else:
        bookmarks.append(dashboard_id)
        action = 'added'

    user.bookmarks = bookmarks
    db.session.commit()

    return jsonify({'message': f'Bookmark {action}', 'bookmarked': action == 'added', 'bookmarks': bookmarks}), 200


@dash_bp.route('/<int:dashboard_id>/notes', methods=['GET'])
@jwt_required_custom
def get_notes(dashboard_id):
    """Get notes for a dashboard."""
    user = get_current_user()
    dashboard = Dashboard.query.get_or_404(dashboard_id)

    if user.role != 'Admin' and dashboard.department != user.department:
        return jsonify({'error': 'Access denied'}), 403

    notes = Note.query.filter_by(dashboard_id=dashboard_id)\
        .order_by(Note.created_at.desc()).all()

    return jsonify({'notes': [n.to_dict() for n in notes]}), 200


@dash_bp.route('/<int:dashboard_id>/notes', methods=['POST'])
@jwt_required_custom
def add_note(dashboard_id):
    """Add a note to a dashboard."""
    user = get_current_user()
    dashboard = Dashboard.query.get_or_404(dashboard_id)

    if user.role != 'Admin' and dashboard.department != user.department:
        return jsonify({'error': 'Access denied'}), 403

    data = request.get_json()
    content = data.get('content', '').strip()
    if not content:
        return jsonify({'error': 'Note content cannot be empty'}), 400

    note = Note(dashboard_id=dashboard_id, user_id=user.id, content=content)
    db.session.add(note)
    db.session.commit()

    return jsonify({'message': 'Note added', 'note': note.to_dict()}), 201


@dash_bp.route('/reorder', methods=['POST'])
@jwt_required_custom
def reorder_dashboards():
    """Update sort order for dashboards."""
    user = get_current_user()
    data = request.get_json()
    order = data.get('order', [])  # [{ id: 1, sort_order: 0 }, ...]

    for item in order:
        d = Dashboard.query.get(item['id'])
        if d:
            if user.role == 'Admin' or d.department == user.department:
                d.sort_order = item['sort_order']

    db.session.commit()
    return jsonify({'message': 'Order updated'}), 200

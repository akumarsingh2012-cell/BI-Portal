"""
Dashboard Routes — Fixed HTTP 500, full CRUD, Bookmarks, Notes, View tracking
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


def _safe_kpi_summary(kpis):
    """Safely compute KPI summary — never raises."""
    try:
        return get_dashboard_kpi_summary(kpis)
    except Exception:
        return {'total': 0, 'green': 0, 'yellow': 0, 'red': 0, 'score': 0, 'label': 'Error'}


@dash_bp.route('/', methods=['GET'])
@jwt_required_custom
def get_dashboards():
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        query = Dashboard.query
        query = department_filter(query, user, Dashboard)

        category = request.args.get('category', '')
        search = request.args.get('search', '').strip()
        department = request.args.get('department', '')
        sort_by = request.args.get('sort', 'created')

        if category:
            query = query.filter(Dashboard.category == category)
        if department and user.role == 'Admin':
            query = query.filter(Dashboard.department == department)
        if search:
            query = query.filter(
                (Dashboard.title.ilike(f'%{search}%')) |
                (Dashboard.category.ilike(f'%{search}%')) |
                (Dashboard.tags_raw.ilike(f'%{search}%')) |
                (Dashboard.commentary.ilike(f'%{search}%'))
            )

        if sort_by == 'views':
            query = query.order_by(Dashboard.view_count.desc())
        elif sort_by == 'title':
            query = query.order_by(Dashboard.title.asc())
        else:
            query = query.order_by(Dashboard.sort_order.asc(), Dashboard.created_at.desc())

        dashboards = query.all()

        result = []
        bookmarks = user.bookmarks
        for d in dashboards:
            try:
                d_dict = d.to_dict()
                d_dict['kpi_summary'] = _safe_kpi_summary(d.kpis)
                d_dict['is_bookmarked'] = d.id in bookmarks
                result.append(d_dict)
            except Exception as e:
                # Skip broken dashboards but don't crash
                print(f'Error processing dashboard {d.id}: {e}')
                continue

        return jsonify({'dashboards': result, 'total': len(result)}), 200

    except Exception as e:
        print(f'Dashboard list error: {e}')
        return jsonify({'error': f'Failed to load dashboards: {str(e)}'}), 500


@dash_bp.route('/<int:dashboard_id>', methods=['GET'])
@jwt_required_custom
def get_dashboard(dashboard_id):
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        dashboard = Dashboard.query.get(dashboard_id)
        if not dashboard:
            return jsonify({'error': 'Dashboard not found'}), 404
    except Exception:
        return jsonify({'error': 'Dashboard not found'}), 404

    if user.role != 'Admin' and dashboard.department != user.department and not dashboard.is_public:
        return jsonify({'error': 'Access denied — department restriction'}), 403

    try:
        # Increment view count
        dashboard.view_count = (dashboard.view_count or 0) + 1
        db.session.commit()

        d_dict = dashboard.to_dict()
        d_dict['kpis'] = enrich_kpis(dashboard.kpis)
        d_dict['kpi_summary'] = _safe_kpi_summary(dashboard.kpis)
        d_dict['is_bookmarked'] = dashboard.id in user.bookmarks

        return jsonify({'dashboard': d_dict}), 200
    except Exception as e:
        return jsonify({'error': f'Failed to load dashboard: {str(e)}'}), 500


@dash_bp.route('/', methods=['POST'])
@analyst_or_admin_required
def create_dashboard():
    user = get_current_user()
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data provided'}), 400

    required = ['title', 'embed_url', 'department', 'category']
   missing = []

for f in required:
    value = data.get(f)
    if isinstance(value, str):
        if not value.strip():
            missing.append(f)
    elif not value:
        missing.append(f)

    if missing:
        return jsonify({'error': f'Missing required fields: {", ".join(missing)}'}), 400

    if user.role != 'Admin' and data.get('department') != user.department:
        return jsonify({'error': 'You can only create dashboards for your department'}), 403

    try:
        dashboard = Dashboard(
            title=data['title'].strip(),
            embed_url=data['embed_url'].strip(),
            department=data['department'],
            category=data['category'].strip(),
            commentary=data.get('commentary', ''),
            ai_context=data.get('ai_context', ''),
            created_by=user.email,
            sort_order=data.get('sort_order', 0),
            is_public=bool(data.get('is_public', False)) if user.role == 'Admin' else False
        )
        dashboard.tags = data.get('tags', [])
        dashboard.kpis = data.get('kpis', [])

        db.session.add(dashboard)
        db.session.commit()

        log_activity(user.id, f"Created dashboard: {dashboard.title}", 'dashboard', dashboard.id)
        return jsonify({'message': 'Dashboard created', 'dashboard': dashboard.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to create dashboard: {str(e)}'}), 500


@dash_bp.route('/<int:dashboard_id>', methods=['PUT'])
@analyst_or_admin_required
def update_dashboard(dashboard_id):
    user = get_current_user()
    dashboard = Dashboard.query.get(dashboard_id)
    if not dashboard:
        return jsonify({'error': 'Dashboard not found'}), 404

    if user.role != 'Admin' and dashboard.department != user.department:
        return jsonify({'error': 'Access denied'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    try:
        for field in ['title', 'embed_url', 'category', 'commentary', 'ai_context']:
            if field in data:
                setattr(dashboard, field, data[field])

        if 'tags' in data:
            dashboard.tags = data['tags']
        if 'kpis' in data:
            dashboard.kpis = data['kpis']
        if 'department' in data and user.role == 'Admin':
            dashboard.department = data['department']
        if 'sort_order' in data:
            dashboard.sort_order = int(data['sort_order'])
        if 'is_public' in data and user.role == 'Admin':
            dashboard.is_public = bool(data['is_public'])

        dashboard.updated_at = datetime.utcnow()
        db.session.commit()

        log_activity(user.id, f"Updated dashboard: {dashboard.title}", 'dashboard', dashboard_id)
        return jsonify({'message': 'Dashboard updated', 'dashboard': dashboard.to_dict()}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to update: {str(e)}'}), 500


@dash_bp.route('/<int:dashboard_id>', methods=['DELETE'])
@admin_required
def delete_dashboard(dashboard_id):
    user = get_current_user()
    dashboard = Dashboard.query.get(dashboard_id)
    if not dashboard:
        return jsonify({'error': 'Dashboard not found'}), 404
    title = dashboard.title
    try:
        db.session.delete(dashboard)
        db.session.commit()
        log_activity(user.id, f"Deleted dashboard: {title}", 'dashboard', dashboard_id)
        return jsonify({'message': f'Dashboard "{title}" deleted'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to delete: {str(e)}'}), 500


@dash_bp.route('/<int:dashboard_id>/bookmark', methods=['POST'])
@jwt_required_custom
def toggle_bookmark(dashboard_id):
    user = get_current_user()
    dashboard = Dashboard.query.get(dashboard_id)
    if not dashboard:
        return jsonify({'error': 'Dashboard not found'}), 404

    if user.role != 'Admin' and dashboard.department != user.department and not dashboard.is_public:
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
    user = get_current_user()
    dashboard = Dashboard.query.get(dashboard_id)
    if not dashboard:
        return jsonify({'error': 'Dashboard not found'}), 404

    if user.role != 'Admin' and dashboard.department != user.department:
        return jsonify({'error': 'Access denied'}), 403

    notes = Note.query.filter_by(dashboard_id=dashboard_id).order_by(Note.created_at.desc()).all()
    return jsonify({'notes': [n.to_dict() for n in notes]}), 200


@dash_bp.route('/<int:dashboard_id>/notes', methods=['POST'])
@jwt_required_custom
def add_note(dashboard_id):
    user = get_current_user()
    dashboard = Dashboard.query.get(dashboard_id)
    if not dashboard:
        return jsonify({'error': 'Dashboard not found'}), 404

    if user.role != 'Admin' and dashboard.department != user.department:
        return jsonify({'error': 'Access denied'}), 403

    data = request.get_json()
    content = data.get('content', '').strip() if data else ''
    if not content:
        return jsonify({'error': 'Note content cannot be empty'}), 400

    note = Note(dashboard_id=dashboard_id, user_id=user.id, content=content)
    db.session.add(note)
    db.session.commit()
    return jsonify({'message': 'Note added', 'note': note.to_dict()}), 201


@dash_bp.route('/<int:dashboard_id>/notes/<int:note_id>', methods=['DELETE'])
@jwt_required_custom
def delete_note(dashboard_id, note_id):
    user = get_current_user()
    note = Note.query.filter_by(id=note_id, dashboard_id=dashboard_id).first()
    if not note:
        return jsonify({'error': 'Note not found'}), 404
    if note.user_id != user.id and user.role != 'Admin':
        return jsonify({'error': 'You can only delete your own notes'}), 403
    db.session.delete(note)
    db.session.commit()
    return jsonify({'message': 'Note deleted'}), 200


@dash_bp.route('/reorder', methods=['POST'])
@jwt_required_custom
def reorder_dashboards():
    user = get_current_user()
    data = request.get_json()
    order = data.get('order', [])

    for item in order:
        try:
            d = Dashboard.query.get(int(item['id']))
            if d and (user.role == 'Admin' or d.department == user.department):
                d.sort_order = int(item['sort_order'])
        except Exception:
            continue

    db.session.commit()
    return jsonify({'message': 'Order updated'}), 200


@dash_bp.route('/categories', methods=['GET'])
@jwt_required_custom
def get_categories():
    """Get all unique categories for filtering."""
    user = get_current_user()
    query = Dashboard.query
    query = department_filter(query, user, Dashboard)
    dashboards = query.all()
    categories = sorted(set(d.category for d in dashboards if d.category))
    departments = sorted(set(d.department for d in dashboards))
    return jsonify({'categories': categories, 'departments': departments}), 200

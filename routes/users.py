"""
User Management Routes — Full CRUD + Advanced Controls
"""

from flask import Blueprint, request, jsonify
from datetime import datetime
from app import db, bcrypt
from models import User, ActivityLog
from middleware.auth_middleware import admin_required, jwt_required_custom, analyst_or_admin_required, get_current_user, log_activity

users_bp = Blueprint('users', __name__)

VALID_ROLES = ['Admin', 'Analyst', 'Viewer']
VALID_DEPARTMENTS = ['Finance', 'Sales', 'HR', 'Operations', 'IT', 'Marketing']


@users_bp.route('/', methods=['GET'])
@admin_required
def get_users():
    search = request.args.get('search', '').strip()
    role_filter = request.args.get('role', '')
    dept_filter = request.args.get('department', '')
    status_filter = request.args.get('status', '')

    query = User.query
    if search:
        query = query.filter((User.name.ilike(f'%{search}%')) | (User.email.ilike(f'%{search}%')))
    if role_filter:
        query = query.filter(User.role == role_filter)
    if dept_filter:
        query = query.filter(User.department == dept_filter)
    if status_filter == 'active':
        query = query.filter(User.is_active == True)
    elif status_filter == 'inactive':
        query = query.filter(User.is_active == False)

    users = query.order_by(User.created_at.desc()).all()
    return jsonify({'users': [u.to_dict() for u in users], 'total': len(users)}), 200


@users_bp.route('/', methods=['POST'])
@admin_required
def create_user():
    current = get_current_user()
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    role = data.get('role', 'Viewer')
    department = data.get('department', 'Operations')
    permissions = data.get('permissions', {})

    if not name or len(name) < 2:
        return jsonify({'error': 'Name must be at least 2 characters'}), 400
    if not email or '@' not in email:
        return jsonify({'error': 'Valid email is required'}), 400
    if not password or len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400
    if role not in VALID_ROLES:
        return jsonify({'error': f'Role must be one of: {", ".join(VALID_ROLES)}'}), 400
    if department not in VALID_DEPARTMENTS:
        return jsonify({'error': f'Department must be one of: {", ".join(VALID_DEPARTMENTS)}'}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({'error': f'Email "{email}" is already registered'}), 409

    hashed = bcrypt.generate_password_hash(password).decode('utf-8')
    user = User(name=name, email=email, password=hashed, role=role, department=department)
    user.permissions = permissions
    db.session.add(user)
    db.session.commit()

    log_activity(current.id, f"Created user: {email} ({role}, {department})", 'user', user.id)
    return jsonify({'message': f'User "{name}" created successfully', 'user': user.to_dict()}), 201


@users_bp.route('/<int:user_id>', methods=['PUT'])
@admin_required
def update_user(user_id):
    current = get_current_user()
    user = User.query.get_or_404(user_id)
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    if 'name' in data and data['name']:
        user.name = data['name'].strip()
    if 'role' in data:
        if data['role'] not in VALID_ROLES:
            return jsonify({'error': 'Invalid role'}), 400
        # Prevent removing last admin
        if user.role == 'Admin' and data['role'] != 'Admin':
            admin_count = User.query.filter_by(role='Admin', is_active=True).count()
            if admin_count <= 1:
                return jsonify({'error': 'Cannot demote the last active admin'}), 400
        user.role = data['role']
    if 'department' in data:
        if data['department'] not in VALID_DEPARTMENTS:
            return jsonify({'error': 'Invalid department'}), 400
        user.department = data['department']
    if 'is_active' in data:
        if current.id == user_id and not data['is_active']:
            return jsonify({'error': 'Cannot deactivate your own account'}), 400
        user.is_active = bool(data['is_active'])
    if 'password' in data and data['password']:
        if len(data['password']) < 6:
            return jsonify({'error': 'Password must be at least 6 characters'}), 400
        user.password = bcrypt.generate_password_hash(data['password']).decode('utf-8')
    if 'permissions' in data:
        user.permissions = data['permissions']
    # Unlock account
    if data.get('unlock'):
        user.locked_until = None
        user.failed_logins = 0

    db.session.commit()
    log_activity(current.id, f"Updated user: {user.email}", 'user', user_id)
    return jsonify({'message': 'User updated', 'user': user.to_dict()}), 200


@users_bp.route('/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    current = get_current_user()
    if current.id == user_id:
        return jsonify({'error': 'Cannot delete your own account'}), 400

    user = User.query.get_or_404(user_id)

    # Prevent deleting last admin
    if user.role == 'Admin':
        admin_count = User.query.filter_by(role='Admin', is_active=True).count()
        if admin_count <= 1:
            return jsonify({'error': 'Cannot delete the last active admin'}), 400

    email = user.email
    db.session.delete(user)
    db.session.commit()

    log_activity(current.id, f"Deleted user: {email}", 'user', user_id)
    return jsonify({'message': f'User "{email}" deleted'}), 200


@users_bp.route('/<int:user_id>/toggle-status', methods=['POST'])
@admin_required
def toggle_user_status(user_id):
    """Quick toggle active/inactive."""
    current = get_current_user()
    if current.id == user_id:
        return jsonify({'error': 'Cannot change your own status'}), 400
    user = User.query.get_or_404(user_id)
    user.is_active = not user.is_active
    db.session.commit()
    status = 'activated' if user.is_active else 'deactivated'
    log_activity(current.id, f"User {user.email} {status}", 'user', user_id)
    return jsonify({'message': f'User {status}', 'is_active': user.is_active}), 200


@users_bp.route('/<int:user_id>/reset-password', methods=['POST'])
@admin_required
def reset_user_password(user_id):
    """Admin resets another user's password."""
    current = get_current_user()
    user = User.query.get_or_404(user_id)
    data = request.get_json()
    new_password = data.get('new_password', '')
    if not new_password or len(new_password) < 6:
        return jsonify({'error': 'New password must be at least 6 characters'}), 400
    user.password = bcrypt.generate_password_hash(new_password).decode('utf-8')
    user.failed_logins = 0
    user.locked_until = None
    db.session.commit()
    log_activity(current.id, f"Reset password for: {user.email}", 'user', user_id)
    return jsonify({'message': f'Password reset for {user.email}'}), 200


@users_bp.route('/bulk-action', methods=['POST'])
@admin_required
def bulk_action():
    """Bulk activate/deactivate/delete users."""
    current = get_current_user()
    data = request.get_json()
    action = data.get('action')  # activate | deactivate | delete
    user_ids = data.get('user_ids', [])

    if not action or not user_ids:
        return jsonify({'error': 'Action and user_ids required'}), 400
    if current.id in user_ids:
        return jsonify({'error': 'Cannot perform bulk action on your own account'}), 400

    affected = 0
    for uid in user_ids:
        try:
            user = User.query.get(int(uid))
            if not user:
                continue
            if action == 'activate':
                user.is_active = True
                affected += 1
            elif action == 'deactivate':
                user.is_active = False
                affected += 1
            elif action == 'delete':
                if user.role == 'Admin':
                    continue  # Skip admins in bulk delete
                db.session.delete(user)
                affected += 1
        except Exception:
            continue

    db.session.commit()
    log_activity(current.id, f"Bulk {action}: {affected} users", 'user')
    return jsonify({'message': f'Bulk {action} completed for {affected} users'}), 200


@users_bp.route('/stats', methods=['GET'])
@admin_required
def get_user_stats():
    """Get user statistics for admin dashboard."""
    total = User.query.count()
    active = User.query.filter_by(is_active=True).count()
    by_role = {
        'Admin': User.query.filter_by(role='Admin').count(),
        'Analyst': User.query.filter_by(role='Analyst').count(),
        'Viewer': User.query.filter_by(role='Viewer').count(),
    }
    by_dept = {}
    for dept in VALID_DEPARTMENTS:
        count = User.query.filter_by(department=dept).count()
        if count > 0:
            by_dept[dept] = count

    return jsonify({
        'total': total,
        'active': active,
        'inactive': total - active,
        'by_role': by_role,
        'by_department': by_dept,
    }), 200


@users_bp.route('/activity-log', methods=['GET'])
@admin_required
def get_activity_log():
    page = int(request.args.get('page', 1))
    per_page = min(int(request.args.get('per_page', 50)), 200)
    entity_type = request.args.get('entity_type', '')
    user_id_filter = request.args.get('user_id', '')

    query = ActivityLog.query
    if entity_type:
        query = query.filter(ActivityLog.entity_type == entity_type)
    if user_id_filter:
        try:
            query = query.filter(ActivityLog.user_id == int(user_id_filter))
        except Exception:
            pass

    logs = query.order_by(ActivityLog.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        'logs': [l.to_dict() for l in logs.items],
        'total': logs.total,
        'pages': logs.pages,
        'current_page': page
    }), 200

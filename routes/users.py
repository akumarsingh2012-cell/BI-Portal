"""
User Management Routes — Admin CRUD
"""

from flask import Blueprint, request, jsonify
from app import db, bcrypt
from models import User, ActivityLog
from middleware.auth_middleware import admin_required, jwt_required_custom, get_current_user, log_activity

users_bp = Blueprint('users', __name__)

VALID_ROLES = ['Admin', 'Analyst', 'Viewer']
VALID_DEPARTMENTS = ['Finance', 'Sales', 'HR', 'Operations']


@users_bp.route('/', methods=['GET'])
@admin_required
def get_users():
    """Get all users. Admin only."""
    users = User.query.order_by(User.created_at.desc()).all()
    return jsonify({'users': [u.to_dict() for u in users], 'total': len(users)}), 200


@users_bp.route('/', methods=['POST'])
@admin_required
def create_user():
    """Create new user. Admin only."""
    current = get_current_user()
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # Validation
    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    role = data.get('role', 'Viewer')
    department = data.get('department', 'Operations')

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

    # Unique email check
    if User.query.filter_by(email=email).first():
        return jsonify({'error': f'Email "{email}" is already registered'}), 409

    hashed = bcrypt.generate_password_hash(password).decode('utf-8')
    user = User(name=name, email=email, password=hashed, role=role, department=department)
    db.session.add(user)
    db.session.commit()

    log_activity(current.id, f"Created user: {email} ({role}, {department})", 'user', user.id)

    return jsonify({'message': f'User "{name}" created successfully', 'user': user.to_dict()}), 201


@users_bp.route('/<int:user_id>', methods=['PUT'])
@admin_required
def update_user(user_id):
    """Update user. Admin only."""
    current = get_current_user()
    user = User.query.get_or_404(user_id)
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data provided'}), 400

    if 'name' in data:
        user.name = data['name'].strip()
    if 'role' in data:
        if data['role'] not in VALID_ROLES:
            return jsonify({'error': f'Invalid role'}), 400
        user.role = data['role']
    if 'department' in data:
        if data['department'] not in VALID_DEPARTMENTS:
            return jsonify({'error': f'Invalid department'}), 400
        user.department = data['department']
    if 'is_active' in data:
        user.is_active = bool(data['is_active'])
    if 'password' in data and data['password']:
        if len(data['password']) < 6:
            return jsonify({'error': 'Password must be at least 6 characters'}), 400
        user.password = bcrypt.generate_password_hash(data['password']).decode('utf-8')

    db.session.commit()
    log_activity(current.id, f"Updated user: {user.email}", 'user', user_id)

    return jsonify({'message': 'User updated', 'user': user.to_dict()}), 200


@users_bp.route('/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    """Delete user. Admin only."""
    current = get_current_user()
    if current.id == user_id:
        return jsonify({'error': 'Cannot delete your own account'}), 400

    user = User.query.get_or_404(user_id)
    email = user.email
    db.session.delete(user)
    db.session.commit()

    log_activity(current.id, f"Deleted user: {email}", 'user', user_id)
    return jsonify({'message': f'User "{email}" deleted'}), 200


@users_bp.route('/activity-log', methods=['GET'])
@admin_required
def get_activity_log():
    """Get activity log. Admin only."""
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))

    logs = ActivityLog.query.order_by(ActivityLog.created_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'logs': [l.to_dict() for l in logs.items],
        'total': logs.total,
        'pages': logs.pages,
        'current_page': page
    }), 200

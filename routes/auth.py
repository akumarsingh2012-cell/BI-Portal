"""
Auth Routes — Login, Logout, Profile (Fixed with lockout protection)
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, get_jwt_identity
from datetime import datetime, timedelta
from app import db, bcrypt
from models import User
from middleware.auth_middleware import jwt_required_custom, get_current_user, log_activity

auth_bp = Blueprint('auth', __name__)
MAX_FAILED_LOGINS = 5
LOCKOUT_MINUTES = 15


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'error': 'Invalid email or password'}), 401

    # Check lockout
    if user.is_locked:
        remaining = int((user.locked_until - datetime.utcnow()).total_seconds() / 60) + 1
        return jsonify({'error': f'Account locked due to failed attempts. Try again in {remaining} minutes.'}), 423

    if not bcrypt.check_password_hash(user.password, password):
        user.failed_logins = (user.failed_logins or 0) + 1
        if user.failed_logins >= MAX_FAILED_LOGINS:
            user.locked_until = datetime.utcnow() + timedelta(minutes=LOCKOUT_MINUTES)
            db.session.commit()
            return jsonify({'error': f'Too many failed attempts. Account locked for {LOCKOUT_MINUTES} minutes.'}), 423
        db.session.commit()
        remaining_attempts = MAX_FAILED_LOGINS - user.failed_logins
        return jsonify({'error': f'Invalid email or password. {remaining_attempts} attempts remaining.'}), 401

    if not user.is_active:
        return jsonify({'error': 'Account is deactivated. Contact your administrator.'}), 403

    # Successful login
    user.last_login = datetime.utcnow()
    user.login_count = (user.login_count or 0) + 1
    user.failed_logins = 0
    user.locked_until = None
    db.session.commit()

    token = create_access_token(identity=str(user.id))
    log_activity(user.id, "Login successful", 'auth')

    return jsonify({
        'message': 'Login successful',
        'token': token,
        'user': user.to_dict()
    }), 200


@auth_bp.route('/logout', methods=['POST'])
def logout():
    return jsonify({'message': 'Logged out successfully'}), 200


@auth_bp.route('/me', methods=['GET'])
@jwt_required_custom
def get_me():
    user = get_current_user()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    return jsonify({'user': user.to_dict()}), 200


@auth_bp.route('/profile', methods=['PUT'])
@jwt_required_custom
def update_profile():
    user = get_current_user()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    if 'name' in data:
        name = data['name'].strip()
        if len(name) < 2:
            return jsonify({'error': 'Name must be at least 2 characters'}), 400
        user.name = name

    if 'new_password' in data and data['new_password']:
        current_password = data.get('current_password', '')
        if not current_password:
            return jsonify({'error': 'Current password is required to change password'}), 400
        if not bcrypt.check_password_hash(user.password, current_password):
            return jsonify({'error': 'Current password is incorrect'}), 400
        new_pass = data['new_password']
        if len(new_pass) < 6:
            return jsonify({'error': 'New password must be at least 6 characters'}), 400
        user.password = bcrypt.generate_password_hash(new_pass).decode('utf-8')

    if 'preferences' in data:
        user.preferences = data['preferences']

    db.session.commit()
    log_activity(user.id, "Updated profile", 'user', user.id)

    return jsonify({'message': 'Profile updated successfully', 'user': user.to_dict()}), 200


@auth_bp.route('/unlock/<int:user_id>', methods=['POST'])
@jwt_required_custom
def unlock_user(user_id):
    """Admin: unlock a locked user account."""
    current = get_current_user()
    if not current or current.role != 'Admin':
        return jsonify({'error': 'Admin access required'}), 403

    user = User.query.get_or_404(user_id)
    user.locked_until = None
    user.failed_logins = 0
    db.session.commit()
    log_activity(current.id, f"Unlocked account: {user.email}", 'user', user_id)
    return jsonify({'message': f'Account for {user.email} has been unlocked'}), 200

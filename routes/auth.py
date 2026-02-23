"""
Auth Routes — Login, Register, Profile
"""

from flask import Blueprint, request, jsonify, make_response
from flask_jwt_extended import (
    create_access_token, get_jwt_identity,
    unset_jwt_cookies, verify_jwt_in_request
)
from datetime import datetime
from app import db, bcrypt
from models import User, ActivityLog
from middleware.auth_middleware import jwt_required_custom, get_current_user, log_activity

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['POST'])
def login():
    """Authenticate user and return JWT."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not bcrypt.check_password_hash(user.password, password):
        return jsonify({'error': 'Invalid email or password'}), 401

    if not user.is_active:
        return jsonify({'error': 'Account is deactivated. Contact admin.'}), 403

    # Update last login
    user.last_login = datetime.utcnow()
    db.session.commit()

    token = create_access_token(identity=user.id)
    log_activity(user.id, f"Login successful", 'auth')

    response = make_response(jsonify({
        'message': 'Login successful',
        'token': token,
        'user': user.to_dict()
    }))
    # Set HTTP-only cookie for security
    response.set_cookie(
        'access_token_cookie', token,
        httponly=True,
        secure=False,  # Set True in production with HTTPS
        samesite='Lax',
        max_age=28800  # 8 hours
    )
    return response, 200


@auth_bp.route('/logout', methods=['POST'])
def logout():
    """Clear JWT cookie."""
    response = make_response(jsonify({'message': 'Logged out successfully'}))
    unset_jwt_cookies(response)
    response.delete_cookie('access_token_cookie')
    return response, 200


@auth_bp.route('/me', methods=['GET'])
@jwt_required_custom
def get_me():
    """Get current user profile."""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    return jsonify({'user': user.to_dict()}), 200


@auth_bp.route('/profile', methods=['PUT'])
@jwt_required_custom
def update_profile():
    """Update current user's name/password."""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # Update name
    if 'name' in data:
        name = data['name'].strip()
        if len(name) < 2:
            return jsonify({'error': 'Name must be at least 2 characters'}), 400
        user.name = name

    # Update password
    if 'new_password' in data:
        current_password = data.get('current_password', '')
        if not current_password:
            return jsonify({'error': 'Current password is required to set new password'}), 400
        if not bcrypt.check_password_hash(user.password, current_password):
            return jsonify({'error': 'Current password is incorrect'}), 400
        new_pass = data['new_password']
        if len(new_pass) < 6:
            return jsonify({'error': 'New password must be at least 6 characters'}), 400
        user.password = bcrypt.generate_password_hash(new_pass).decode('utf-8')

    db.session.commit()
    log_activity(user.id, "Updated profile", 'user', user.id)

    return jsonify({'message': 'Profile updated successfully', 'user': user.to_dict()}), 200

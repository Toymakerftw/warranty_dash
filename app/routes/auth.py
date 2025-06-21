from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash
from app.database import verify_user, create_user, get_all_users, update_user_status, update_user_password, update_user_role
from app.models import User
import re
import logging

logger = logging.getLogger(__name__)
auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False)
        
        if not username or not password:
            flash('Please enter both username and password', 'error')
            return render_template('auth/login.html')
        
        # Validate input
        if len(username) > 50 or len(password) > 100:
            flash('Invalid input length', 'error')
            return render_template('auth/login.html')
        
        user_data = verify_user(username, password)
        if user_data and user_data.get('is_active'):
            user = User(user_data)
            login_user(user, remember=remember)
            logger.info(f"User logged in: {username}")
            flash('Login successful!', 'success')
            
            # Redirect to next page or dashboard
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                return redirect(next_page)
            return redirect(url_for('main.dashboard'))
        else:
            flash('Invalid username or password', 'error')
            logger.warning(f"Failed login attempt for username: {username}")
    
    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    username = current_user.username
    logout_user()
    flash('You have been logged out', 'info')
    logger.info(f"User logged out: {username}")
    return redirect(url_for('auth.login'))

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if not current_password or not new_password or not confirm_password:
            flash('Please fill in all password fields', 'error')
            return render_template('auth/profile.html')
        
        # Verify current password
        user_data = verify_user(current_user.username, current_password)
        if not user_data:
            flash('Current password is incorrect', 'error')
            return render_template('auth/profile.html')
        
        if new_password != confirm_password:
            flash('New passwords do not match', 'error')
            return render_template('auth/profile.html')
        
        if len(new_password) < 6:
            flash('New password must be at least 6 characters long', 'error')
            return render_template('auth/profile.html')
        
        # Update password
        if update_user_password(current_user.id, new_password):
            flash('Password updated successfully', 'success')
            logger.info(f"Password updated for user: {current_user.username}")
        else:
            flash('Failed to update password', 'error')
    
    return render_template('auth/profile.html')

@auth_bp.route('/users')
@login_required
def user_management():
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('main.dashboard'))
    
    users = get_all_users()
    return render_template('auth/user_management.html', users=users)

@auth_bp.route('/users/add', methods=['GET', 'POST'])
@login_required
def add_user():
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        role = request.form.get('role', 'user')
        
        # Validation
        errors = []
        
        if not username or len(username) < 3 or len(username) > 30:
            errors.append('Username must be between 3 and 30 characters')
        
        if not re.match(r'^[a-zA-Z0-9_]+$', username):
            errors.append('Username can only contain letters, numbers, and underscores')
        
        if not email or not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
            errors.append('Please enter a valid email address')
        
        if not password or len(password) < 6:
            errors.append('Password must be at least 6 characters long')
        
        if password != confirm_password:
            errors.append('Passwords do not match')
        
        if len(first_name) > 50 or len(last_name) > 50:
            errors.append('Name fields are too long')
        
        if role not in ['user', 'admin']:
            errors.append('Invalid role selected')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('auth/add_user.html')
        
        # Create user
        user_id = create_user(username, email, password, first_name, last_name, role)
        if user_id:
            flash(f'User "{username}" created successfully!', 'success')
            logger.info(f"New user created by admin {current_user.username}: {username} ({role})")
            return redirect(url_for('auth.user_management'))
        else:
            flash('Username or email already exists', 'error')
    
    return render_template('auth/add_user.html')

@auth_bp.route('/users/<int:user_id>/toggle', methods=['POST'])
@login_required
def toggle_user_status(user_id):
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('main.dashboard'))
    
    if user_id == current_user.id:
        flash('You cannot deactivate your own account', 'error')
        return redirect(url_for('auth.user_management'))
    
    is_active = request.form.get('is_active', '0') == '1'
    if update_user_status(user_id, is_active):
        status = 'activated' if is_active else 'deactivated'
        flash(f'User {status} successfully', 'success')
        logger.info(f"User {user_id} {status} by admin {current_user.username}")
    else:
        flash('Failed to update user status', 'error')
    
    return redirect(url_for('auth.user_management'))

@auth_bp.route('/users/<int:user_id>/role', methods=['POST'])
@login_required
def update_user_role_route(user_id):
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('main.dashboard'))
    
    if user_id == current_user.id:
        flash('You cannot change your own role', 'error')
        return redirect(url_for('auth.user_management'))
    
    role = request.form.get('role', '')
    if role not in ['user', 'admin']:
        flash('Invalid role selected', 'error')
        return redirect(url_for('auth.user_management'))
    
    if update_user_role(user_id, role):
        flash(f'User role updated to {role} successfully', 'success')
        logger.info(f"User {user_id} role changed to {role} by admin {current_user.username}")
    else:
        flash('Failed to update user role', 'error')
    
    return redirect(url_for('auth.user_management')) 
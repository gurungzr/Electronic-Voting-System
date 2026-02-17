from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.services.auth_service import AuthService
from app.services.rate_limiter import RateLimiter
from app.services.audit_service import AuditService
from app.utils.validators import sanitize_input

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/')
def index():
    """Home page."""
    if current_user.is_authenticated:
        if hasattr(current_user, 'is_admin') and current_user.is_admin:
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('voter.dashboard'))
    return render_template('auth/login.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Voter login page."""
    if current_user.is_authenticated:
        if hasattr(current_user, 'is_admin') and current_user.is_admin:
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('voter.dashboard'))

    if request.method == 'POST':
        voter_id = request.form.get('voter_id', '').strip().upper()
        password = request.form.get('password', '')

        # Check rate limiting before attempting login
        is_limited, limit_message, _ = RateLimiter.is_rate_limited(voter_id, 'voter_login')
        if is_limited:
            AuditService.log_rate_limit_triggered(voter_id, 'voter_login')
            flash(limit_message, 'danger')
            return render_template('auth/login.html')

        success, message, voter = AuthService.login_voter(voter_id, password)

        if success:
            # Clear rate limit on successful login
            RateLimiter.record_attempt(voter_id, 'voter_login', success=True)
            AuditService.log_login_success(voter_id, 'voter')
            login_user(voter)
            flash(message, 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('voter.dashboard'))
        else:
            # Record failed attempt
            RateLimiter.record_attempt(voter_id, 'voter_login', success=False)
            AuditService.log_login_failed(voter_id, 'voter', message)
            attempts_remaining = RateLimiter.get_attempts_remaining(voter_id, 'voter_login')
            if attempts_remaining > 0 and attempts_remaining <= 3:
                flash(f'{message}. {attempts_remaining} attempts remaining.', 'danger')
            else:
                flash(message, 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Voter registration page."""
    if current_user.is_authenticated:
        return redirect(url_for('voter.dashboard'))

    if request.method == 'POST':
        citizenship_number = request.form.get('citizenship_number', '').strip()
        full_name = sanitize_input(request.form.get('full_name', '').strip())
        date_of_birth = request.form.get('date_of_birth', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        success, message, voter = AuthService.register_voter(
            citizenship_number=citizenship_number,
            full_name=full_name,
            date_of_birth=date_of_birth,
            password=password,
            confirm_password=confirm_password
        )

        if success:
            AuditService.log_registration(voter.voter_id, success=True)
            flash(message, 'success')
            return redirect(url_for('auth.login'))
        else:
            AuditService.log_registration(citizenship_number, success=False, reason=message)
            flash(message, 'danger')

    return render_template('auth/register.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """Logout user."""
    user_id = current_user.voter_id if hasattr(current_user, 'voter_id') else current_user.username
    user_type = 'admin' if hasattr(current_user, 'is_admin') and current_user.is_admin else 'voter'
    AuditService.log_logout(user_id, user_type)
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))

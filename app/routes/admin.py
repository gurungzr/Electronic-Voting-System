from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from functools import wraps
from app.services.auth_service import AuthService
from app.services.election_service import ElectionService
from app.services.vote_service import VoteService
from app.services.rate_limiter import RateLimiter
from app.services.audit_service import AuditService
from app.models.election import Election
from app.models.candidate import Candidate
from app.constants.parties import get_party_by_name
from app.utils.validators import sanitize_input

admin_bp = Blueprint('admin', __name__)


def admin_required(f):
    """Decorator to ensure user is an admin."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('admin.login'))
        if not hasattr(current_user, 'is_admin') or not current_user.is_admin:
            flash('Access denied. Admin privileges required.', 'danger')
            return redirect(url_for('voter.dashboard'))
        return f(*args, **kwargs)
    return decorated_function


@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Admin login page."""
    if current_user.is_authenticated:
        if hasattr(current_user, 'is_admin') and current_user.is_admin:
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('voter.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        # Check rate limiting before attempting login
        is_limited, limit_message, _ = RateLimiter.is_rate_limited(username, 'admin_login')
        if is_limited:
            AuditService.log_rate_limit_triggered(username, 'admin_login')
            flash(limit_message, 'danger')
            return render_template('admin/login.html')

        success, message, admin = AuthService.login_admin(username, password)

        if success:
            # Clear rate limit on successful login
            RateLimiter.record_attempt(username, 'admin_login', success=True)
            AuditService.log_login_success(username, 'admin')
            login_user(admin)
            flash(message, 'success')
            return redirect(url_for('admin.dashboard'))
        else:
            # Record failed attempt
            RateLimiter.record_attempt(username, 'admin_login', success=False)
            AuditService.log_login_failed(username, 'admin', message)
            attempts_remaining = RateLimiter.get_attempts_remaining(username, 'admin_login')
            if attempts_remaining > 0 and attempts_remaining <= 3:
                flash(f'{message}. {attempts_remaining} attempts remaining.', 'danger')
            else:
                flash(message, 'danger')

    return render_template('admin/login.html')


@admin_bp.route('/logout')
@login_required
@admin_required
def logout():
    """Admin logout."""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('admin.login'))


@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    """Admin dashboard."""
    stats = ElectionService.get_dashboard_stats()
    elections = Election.get_all_elections()
    return render_template('admin/dashboard.html',
                           stats=stats,
                           elections=elections)


@admin_bp.route('/elections/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_election():
    """Create a new dual-ballot election."""
    if request.method == 'POST':
        name = sanitize_input(request.form.get('name', '').strip())
        description = sanitize_input(request.form.get('description', '').strip())
        start_date = request.form.get('start_date', '')
        end_date = request.form.get('end_date', '')

        # Get selected candidate IDs from form (checkboxes)
        selected_candidate_ids = request.form.getlist('selected_candidates[]')

        if not selected_candidate_ids:
            flash('Please select at least one candidate for each constituency.', 'danger')
            candidate_pool = Candidate.get_grouped_by_constituency()
            constituencies = Election.VALID_CONSTITUENCIES
            default_parties = ElectionService.DEFAULT_PARTIES
            return render_template('admin/create_election.html',
                                   constituencies=constituencies,
                                   default_parties=default_parties,
                                   candidate_pool=candidate_pool)

        # Remove any duplicate IDs (shouldn't happen but just in case)
        unique_candidate_ids = list(dict.fromkeys(selected_candidate_ids))
        if len(unique_candidate_ids) != len(selected_candidate_ids):
            current_app.logger.warning(f"Duplicate candidate IDs detected: {len(selected_candidate_ids)} submitted, {len(unique_candidate_ids)} unique")

        # Fetch selected candidates from database
        current_app.logger.info(f"Creating election - submitted {len(unique_candidate_ids)} candidate IDs: {unique_candidate_ids}")
        selected_candidates = Candidate.find_by_ids(unique_candidate_ids)
        current_app.logger.info(f"Found {len(selected_candidates)} candidates in database")

        # Validate: all selected candidates were found in database
        if len(selected_candidates) != len(unique_candidate_ids):
            found_ids = {c.candidate_id for c in selected_candidates}
            missing_ids = [cid for cid in unique_candidate_ids if cid not in found_ids]
            current_app.logger.error(f"Missing candidates: {missing_ids}")
            flash(f'Some candidates could not be found (possibly stale data). Please refresh and try again. Missing: {len(missing_ids)} candidate(s).', 'danger')
            candidate_pool = Candidate.get_grouped_by_constituency()
            constituencies = Election.VALID_CONSTITUENCIES
            default_parties = ElectionService.DEFAULT_PARTIES
            return render_template('admin/create_election.html',
                                   constituencies=constituencies,
                                   default_parties=default_parties,
                                   candidate_pool=candidate_pool)

        # Validate: at least one candidate per constituency
        constituencies_with_candidates = set(c.constituency for c in selected_candidates)
        missing_constituencies = set(Election.VALID_CONSTITUENCIES) - constituencies_with_candidates
        if missing_constituencies:
            flash(f'Please select at least one candidate for: {", ".join(missing_constituencies)}', 'danger')
            candidate_pool = Candidate.get_grouped_by_constituency()
            constituencies = Election.VALID_CONSTITUENCIES
            default_parties = ElectionService.DEFAULT_PARTIES
            return render_template('admin/create_election.html',
                                   constituencies=constituencies,
                                   default_parties=default_parties,
                                   candidate_pool=candidate_pool)

        # Convert to format expected by ElectionService
        candidates = [
            {
                'name': c.name,
                'party': c.party,
                'constituency': c.constituency
            }
            for c in selected_candidates
        ]

        # Get parties from form (optional - uses defaults if empty)
        party_names = request.form.getlist('party_name[]')
        parties = []
        for party_name in party_names:
            if party_name.strip():
                # Look up symbol from default parties if available
                party_info = get_party_by_name(party_name.strip())
                if party_info:
                    parties.append(party_info)  # Includes name and symbol
                else:
                    parties.append({'name': party_name.strip()})

        # Use None to trigger default parties if no custom parties provided
        parties = parties if parties else None

        success, message, election, shares = ElectionService.create_election(
            name=name,
            description=description,
            start_date=start_date,
            end_date=end_date,
            candidates=candidates,
            parties=parties
        )

        if success:
            AuditService.log_election_created(
                current_user.username,
                election.election_id,
                name
            )
            # Redirect to shares display page (shares shown ONCE)
            return render_template('admin/election_shares.html',
                                   election=election,
                                   shares=shares,
                                   threshold=ElectionService.SHAMIR_THRESHOLD,
                                   total_shares=ElectionService.SHAMIR_TOTAL_SHARES)
        else:
            flash(message, 'danger')

    # GET request - fetch candidate pool grouped by constituency
    candidate_pool = Candidate.get_grouped_by_constituency()
    constituencies = Election.VALID_CONSTITUENCIES
    default_parties = ElectionService.DEFAULT_PARTIES
    return render_template('admin/create_election.html',
                           constituencies=constituencies,
                           default_parties=default_parties,
                           candidate_pool=candidate_pool)


@admin_bp.route('/elections/<election_id>')
@login_required
@admin_required
def view_election(election_id):
    """View election details and statistics."""
    stats = ElectionService.get_election_stats(election_id)

    if not stats:
        flash('Election not found.', 'danger')
        return redirect(url_for('admin.dashboard'))

    return render_template('admin/view_election.html', stats=stats)


@admin_bp.route('/elections/<election_id>/results', methods=['GET', 'POST'])
@login_required
@admin_required
def election_results(election_id):
    """View dual-ballot election results (requires Shamir shares to decrypt)."""
    election = Election.find_by_election_id(election_id)

    if not election:
        flash('Election not found.', 'danger')
        return redirect(url_for('admin.dashboard'))

    if not election.has_ended():
        flash('Results are only available after the election has ended.', 'warning')
        return redirect(url_for('admin.view_election', election_id=election_id))

    if request.method == 'GET':
        # Show share entry form
        return render_template('admin/enter_shares.html', election=election)

    # POST: Process shares and decrypt results
    shares = []
    for i in range(5):  # Max 5 shares
        index_key = f'share_index_{i}'
        value_key = f'share_value_{i}'

        if index_key in request.form and value_key in request.form:
            index = request.form.get(index_key, '').strip()
            value = request.form.get(value_key, '').strip()

            if index and value:
                try:
                    shares.append((int(index), value))
                except ValueError:
                    pass

    if len(shares) < 3:
        flash('At least 3 valid shares are required.', 'danger')
        return render_template('admin/enter_shares.html', election=election)

    # Validate and decrypt
    success, message, results = VoteService.decrypt_and_get_results(election_id, shares)

    if not success:
        flash(f'Decryption failed: {message}', 'danger')
        return render_template('admin/enter_shares.html', election=election)

    # Log successful decryption
    AuditService.log_admin_action(
        current_user.username,
        'view_results',
        {'election_id': election_id, 'shares_used': len(shares)}
    )

    return render_template('admin/results.html', results=results)


@admin_bp.route('/elections/<election_id>/deactivate', methods=['POST'])
@login_required
@admin_required
def deactivate_election(election_id):
    """Deactivate an election."""
    success, message = ElectionService.deactivate_election(election_id)

    if success:
        AuditService.log_election_deactivated(current_user.username, election_id)
        flash(message, 'success')
    else:
        flash(message, 'danger')

    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/elections/<election_id>/terminate', methods=['POST'])
@login_required
@admin_required
def terminate_election(election_id):
    """Terminate an ongoing election immediately to allow viewing results."""
    success, message = ElectionService.terminate_election(election_id)

    if success:
        AuditService.log_admin_action(
            current_user.username,
            'terminate_election',
            {'election_id': election_id}
        )
        flash(message, 'success')
        return redirect(url_for('admin.view_election', election_id=election_id))
    else:
        flash(message, 'danger')

    return redirect(url_for('admin.view_election', election_id=election_id))


@admin_bp.route('/audit-chain')
@login_required
@admin_required
def audit_chain_status():
    """View audit log hash chain status and integrity."""
    status = AuditService.get_chain_status()
    recent_logs = AuditService.get_recent_logs(limit=10)
    return render_template('admin/audit_chain.html', status=status, recent_logs=recent_logs)

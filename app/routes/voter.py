from flask import Blueprint, render_template, redirect, url_for, flash, request, session, jsonify
from flask_login import login_required, current_user
from functools import wraps
from app.models.election import Election
from app.services.vote_service import VoteService
from app.services.token_service import TokenService
from app.services.audit_service import AuditService
from app.services.email_service import send_receipt_email, is_email_enabled

voter_bp = Blueprint('voter', __name__)


def voter_required(f):
    """Decorator to ensure user is a voter (not admin)."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if hasattr(current_user, 'is_admin') and current_user.is_admin:
            flash('This page is for voters only.', 'warning')
            return redirect(url_for('admin.dashboard'))
        return f(*args, **kwargs)
    return decorated_function


@voter_bp.route('/dashboard')
@login_required
@voter_required
def dashboard():
    """Voter dashboard showing available elections."""
    elections = VoteService.get_voter_elections(current_user)
    return render_template('voter/dashboard.html',
                           elections=elections,
                           voter=current_user)


@voter_bp.route('/vote/<election_id>', methods=['GET', 'POST'])
@login_required
@voter_required
def vote(election_id):
    """Dual-ballot voting page for a specific election."""
    election = Election.find_by_election_id(election_id)

    if not election:
        flash('Election not found.', 'danger')
        return redirect(url_for('voter.dashboard'))

    if not election.is_ongoing():
        if election.has_ended():
            flash('This election has ended.', 'warning')
        else:
            flash('This election has not started yet.', 'warning')
        return redirect(url_for('voter.dashboard'))

    if current_user.has_voted_in(election_id):
        flash('You have already voted in this election.', 'warning')
        return redirect(url_for('voter.dashboard'))

    # Get candidates for voter's constituency only
    constituency_candidates = election.get_candidates_by_constituency(current_user.constituency)

    # Token handling
    session_key = f'voting_token_{election_id}'
    voting_token = None

    if request.method == 'POST':
        # Get token from form
        token_id = request.form.get('token_id')
        candidate_id = request.form.get('candidate_id')
        party_id = request.form.get('party_id')

        if not token_id:
            flash('Voting token is required.', 'danger')
            return redirect(url_for('voter.vote', election_id=election_id))

        # Validate token
        valid, msg, token = TokenService.validate_token(token_id, election_id)
        if not valid:
            flash(msg, 'danger')
            # Clear invalid session token
            session.pop(session_key, None)
            return redirect(url_for('voter.vote', election_id=election_id))

        if not candidate_id:
            flash('Please select a candidate for the FPTP ballot.', 'danger')
            return render_template('voter/vote.html',
                                   election=election,
                                   candidates=constituency_candidates,
                                   voter_constituency=current_user.constituency,
                                   voting_token=token_id)

        if not party_id:
            flash('Please select a party for the PR ballot.', 'danger')
            return render_template('voter/vote.html',
                                   election=election,
                                   candidates=constituency_candidates,
                                   voter_constituency=current_user.constituency,
                                   voting_token=token_id)

        # Cast vote with token validation
        success, message, receipts = VoteService.cast_dual_ballot_with_token(
            voter=current_user,
            election_id=election_id,
            candidate_id=candidate_id,
            party_id=party_id,
            token_id=token_id
        )

        if success:
            # Log vote cast (without revealing vote choice)
            AuditService.log_vote_cast(current_user.voter_id, election_id, 'dual')
            # Clear session token after successful vote
            session.pop(session_key, None)
            # Store receipts in session for confirmation page (one-time display)
            session['vote_receipts'] = receipts
            flash(message, 'success')
            return redirect(url_for('voter.vote_confirmation',
                                    election_id=election_id))
        else:
            flash(message, 'danger')
            return render_template('voter/vote.html',
                                   election=election,
                                   candidates=constituency_candidates,
                                   voter_constituency=current_user.constituency,
                                   voting_token=token_id)

    # GET request - issue or retrieve token
    voting_token = session.get(session_key)

    if voting_token:
        # Validate existing session token
        valid, msg, token = TokenService.validate_token(voting_token, election_id)
        if not valid:
            # Token invalid or used, clear and get new one
            session.pop(session_key, None)
            voting_token = None

    if not voting_token:
        # Issue new token
        success, msg, token_id = TokenService.issue_token(current_user, election_id)
        if not success:
            flash(msg, 'danger')
            return redirect(url_for('voter.dashboard'))

        # Log token issuance
        AuditService.log_token_issued(current_user.voter_id, election_id)

        # Store token in session (temporary, not linked to voter in DB)
        session[session_key] = token_id
        voting_token = token_id

    return render_template('voter/vote.html',
                           election=election,
                           candidates=constituency_candidates,
                           voter_constituency=current_user.constituency,
                           voting_token=voting_token)


@voter_bp.route('/vote/<election_id>/confirmation')
@login_required
@voter_required
def vote_confirmation(election_id):
    """Vote confirmation page with receipts (shown once)."""
    election = Election.find_by_election_id(election_id)

    if not election:
        flash('Election not found.', 'danger')
        return redirect(url_for('voter.dashboard'))

    if not current_user.has_voted_in(election_id):
        flash('You have not voted in this election.', 'warning')
        return redirect(url_for('voter.dashboard'))

    # Get receipts from session (keep for email sending, mark as viewed)
    receipts = session.get('vote_receipts')
    receipts_viewed = session.get('receipts_viewed', False)

    # If receipts were already viewed and user refreshes, don't show again
    if receipts_viewed and not receipts:
        receipts = None
    elif receipts and not receipts_viewed:
        # First view - mark as viewed but keep in session for email
        session['receipts_viewed'] = True

    return render_template('voter/confirmation.html',
                           election=election,
                           receipts=receipts,
                           email_enabled=is_email_enabled())


@voter_bp.route('/vote/<election_id>/send-receipt', methods=['POST'])
@login_required
@voter_required
def send_receipt_to_email(election_id):
    """Send vote receipts to email."""
    election = Election.find_by_election_id(election_id)

    if not election:
        return jsonify({'success': False, 'message': 'Election not found.'}), 404

    if not current_user.has_voted_in(election_id):
        return jsonify({'success': False, 'message': 'You have not voted in this election.'}), 400

    # Get receipts from session
    receipts = session.get('vote_receipts')
    if not receipts:
        return jsonify({'success': False, 'message': 'Receipts are no longer available. They are only shown once after voting.'}), 400

    # Get email from request
    data = request.get_json()
    email = data.get('email', '').strip() if data else ''

    if not email:
        return jsonify({'success': False, 'message': 'Please provide an email address.'}), 400

    # Basic email validation
    if '@' not in email or '.' not in email.split('@')[-1]:
        return jsonify({'success': False, 'message': 'Please provide a valid email address.'}), 400

    # Send email
    result = send_receipt_email(
        to_email=email,
        election_name=election.name,
        receipt_id=receipts.get('receipt_id'),
        timestamp=receipts.get('timestamp')
    )

    if result['success']:
        # Clear receipts from session after successful email
        session.pop('vote_receipts', None)
        session.pop('receipts_viewed', None)

    return jsonify(result)


@voter_bp.route('/elections')
@login_required
@voter_required
def elections():
    """View all elections."""
    all_elections = Election.get_all_elections()
    return render_template('voter/elections.html',
                           elections=all_elections,
                           voter=current_user)

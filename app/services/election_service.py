from datetime import datetime, timedelta
from app.models.election import Election
from app.models.vote import Vote
from app.models.voter import Voter
from app.utils.validators import validate_election_dates
from app.utils.shamir_crypto import ElectionCrypto
from app.services.token_service import TokenService
from app.constants.parties import PR_PARTIES


class ElectionService:
    """Service for handling dual-ballot election management operations."""

    # Fixed 20 parties for PR ballot (imported from constants)
    DEFAULT_PARTIES = PR_PARTIES

    # Shamir's Secret Sharing configuration
    SHAMIR_THRESHOLD = 3  # Minimum shares needed
    SHAMIR_TOTAL_SHARES = 5  # Total shares generated

    @staticmethod
    def create_election(name: str, description: str, start_date: str,
                        end_date: str, candidates: list,
                        parties: list = None,
                        total_pr_seats: int = 110) -> tuple[bool, str, Election, list]:
        """Create a new dual-ballot election with Shamir's Secret Sharing encryption.

        Args:
            name: Election name
            description: Election description
            start_date: Start datetime string (YYYY-MM-DDTHH:MM)
            end_date: End datetime string (YYYY-MM-DDTHH:MM)
            candidates: List of {'name': ..., 'party': ..., 'constituency': ...}
            parties: List of {'name': ...} for PR ballot (uses defaults if not provided)
            total_pr_seats: Total PR seats to allocate (default 110)

        Returns: (success, message, election, shares)
            - shares: List of share dicts to display ONCE (not stored in DB)
        """
        # Validate inputs
        if not name or len(name) < 3:
            return False, "Election name must be at least 3 characters", None, None

        if not description:
            return False, "Election description is required", None, None

        valid, msg = validate_election_dates(start_date, end_date)
        if not valid:
            return False, msg, None, None

        # Validate candidates
        if not candidates or len(candidates) < 3:
            return False, "At least 3 candidates are required (minimum 1 per constituency)", None, None

        # Validate each candidate has required fields
        constituencies_covered = set()
        for i, candidate in enumerate(candidates):
            if not candidate.get('name'):
                return False, f"Candidate {i+1} name is required", None, None
            if not candidate.get('constituency'):
                return False, f"Candidate {i+1} constituency is required", None, None
            if candidate['constituency'] not in Election.VALID_CONSTITUENCIES:
                return False, f"Invalid constituency for candidate {i+1}. Must be one of: {Election.VALID_CONSTITUENCIES}", None, None
            constituencies_covered.add(candidate['constituency'])

        # Ensure at least one candidate per constituency
        if len(constituencies_covered) < len(Election.VALID_CONSTITUENCIES):
            missing = set(Election.VALID_CONSTITUENCIES) - constituencies_covered
            return False, f"Missing candidates for constituencies: {missing}", None, None

        # Use default parties if not provided
        if not parties:
            parties = ElectionService.DEFAULT_PARTIES

        # Validate parties
        if len(parties) < 2:
            return False, "At least 2 parties are required for PR ballot", None, None

        for i, party in enumerate(parties):
            if not party.get('name'):
                return False, f"Party {i+1} name is required", None, None

        try:
            # Parse dates (local time) and convert to UTC for storage
            start_dt_local = datetime.strptime(start_date, '%Y-%m-%dT%H:%M')
            end_dt_local = datetime.strptime(end_date, '%Y-%m-%dT%H:%M')

            # Nepal timezone offset: UTC+5:45
            nepal_offset = timedelta(hours=5, minutes=45)

            # Convert Nepal time to UTC by subtracting the offset
            start_dt = start_dt_local - nepal_offset
            end_dt = end_dt_local - nepal_offset

            # Generate RSA keys and Shamir shares for vote encryption
            crypto = ElectionCrypto(
                threshold=ElectionService.SHAMIR_THRESHOLD,
                total_shares=ElectionService.SHAMIR_TOTAL_SHARES
            )
            public_key, shares, encrypted_key_bundle = crypto.generate_election_keys()

            election = Election.create(
                name=name,
                description=description,
                start_date=start_dt,
                end_date=end_dt,
                candidates=candidates,
                parties=parties,
                total_pr_seats=total_pr_seats,
                public_key=public_key,
                encrypted_key_bundle=encrypted_key_bundle
            )

            return True, f"Election '{name}' created successfully", election, shares
        except Exception as e:
            return False, f"Failed to create election: {str(e)}", None, None

    @staticmethod
    def get_election_stats(election_id: str) -> dict:
        """Get statistics for an election including token stats.

        Returns: {
            'election': Election,
            'total_fptp_votes': int,
            'total_pr_votes': int,
            'registered_voters': int,
            'participation_rate': float,
            'status': str ('upcoming', 'ongoing', 'ended'),
            'tokens_issued': int,
            'tokens_fully_used': int,
            'tokens_pending': int
        }
        """
        election = Election.find_by_election_id(election_id)
        if not election:
            return None

        total_fptp_votes = Vote.count_by_election(election_id, ballot_type='fptp')
        total_pr_votes = Vote.count_by_election(election_id, ballot_type='pr')
        registered_voters = Voter.count_all()

        # Use PR votes for participation rate (since both ballots are cast together)
        participation_rate = 0
        if registered_voters > 0:
            participation_rate = (total_pr_votes / registered_voters) * 100

        if election.has_ended():
            status = 'ended'
        elif election.is_ongoing():
            status = 'ongoing'
        else:
            status = 'upcoming'

        # Get token statistics
        token_stats = TokenService.get_token_stats(election_id)

        return {
            'election': election,
            'total_fptp_votes': total_fptp_votes,
            'total_pr_votes': total_pr_votes,
            'registered_voters': registered_voters,
            'participation_rate': round(participation_rate, 2),
            'status': status,
            'tokens_issued': token_stats['tokens_issued'],
            'tokens_fully_used': token_stats['tokens_fully_used'],
            'tokens_pending': token_stats['tokens_pending']
        }

    @staticmethod
    def get_dashboard_stats() -> dict:
        """Get overall statistics for admin dashboard.

        Returns: {
            'total_voters': int,
            'total_elections': int,
            'active_elections': int,
            'total_votes_cast': int,
            'voters_by_constituency': dict,
            'total_tokens_issued': int,
            'total_tokens_used': int
        }
        """
        from app import get_db
        db = get_db()

        total_voters = Voter.count_all()
        total_elections = Election.count_all()
        active_elections = len(Election.get_active_elections())

        # Count PR votes (one per voter per election)
        total_votes = db.votes.count_documents({'ballot_type': 'pr'})

        # Get voter distribution by constituency
        voters_by_constituency = {}
        for constituency in Election.VALID_CONSTITUENCIES:
            count = db.voters.count_documents({'constituency': constituency})
            voters_by_constituency[constituency] = count

        # Get overall token statistics
        overall_token_stats = TokenService.get_overall_stats()

        return {
            'total_voters': total_voters,
            'total_elections': total_elections,
            'active_elections': active_elections,
            'total_votes_cast': total_votes,
            'voters_by_constituency': voters_by_constituency,
            'total_tokens_issued': overall_token_stats['total_tokens_issued'],
            'total_tokens_used': overall_token_stats['total_tokens_used']
        }

    @staticmethod
    def deactivate_election(election_id: str) -> tuple[bool, str]:
        """Deactivate an election.

        Returns: (success, message)
        """
        election = Election.find_by_election_id(election_id)
        if not election:
            return False, "Election not found"

        try:
            Election.deactivate(election_id)
            return True, "Election deactivated successfully"
        except Exception as e:
            return False, f"Failed to deactivate election: {str(e)}"

    @staticmethod
    def terminate_election(election_id: str) -> tuple[bool, str]:
        """Terminate an ongoing election immediately.

        This ends the election early, allowing results to be viewed.
        Only works on elections that have started but not yet ended.

        Returns: (success, message)
        """
        election = Election.find_by_election_id(election_id)
        if not election:
            return False, "Election not found"

        if not election.has_started():
            return False, "Cannot terminate an election that hasn't started yet"

        if election.has_ended():
            return False, "Election has already ended"

        try:
            Election.terminate(election_id)
            return True, "Election terminated successfully. Results can now be viewed."
        except Exception as e:
            return False, f"Failed to terminate election: {str(e)}"

    @staticmethod
    def add_candidate_to_election(election_id: str, name: str,
                                  party: str, constituency: str) -> tuple[bool, str]:
        """Add a candidate to an existing election.

        Returns: (success, message)
        """
        election = Election.find_by_election_id(election_id)
        if not election:
            return False, "Election not found"

        if election.has_started():
            return False, "Cannot add candidates after election has started"

        if not name:
            return False, "Candidate name is required"

        if not constituency:
            return False, "Candidate constituency is required"

        if constituency not in Election.VALID_CONSTITUENCIES:
            return False, f"Invalid constituency. Must be one of: {Election.VALID_CONSTITUENCIES}"

        try:
            election.add_candidate(name, party or 'Independent', constituency)
            return True, f"Candidate '{name}' added to {constituency} successfully"
        except Exception as e:
            return False, f"Failed to add candidate: {str(e)}"

    @staticmethod
    def add_party_to_election(election_id: str, name: str) -> tuple[bool, str]:
        """Add a party to an existing election's PR ballot.

        Returns: (success, message)
        """
        election = Election.find_by_election_id(election_id)
        if not election:
            return False, "Election not found"

        if election.has_started():
            return False, "Cannot add parties after election has started"

        if not name:
            return False, "Party name is required"

        try:
            election.add_party(name)
            return True, f"Party '{name}' added successfully"
        except Exception as e:
            return False, f"Failed to add party: {str(e)}"

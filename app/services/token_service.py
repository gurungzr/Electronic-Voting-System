from app.models.voter import Voter
from app.models.voting_token import VotingToken
from app.models.election import Election


class TokenService:
    """Service for managing anonymous voting tokens.

    This service handles token issuance, validation, and usage while
    maintaining voter anonymity by never linking tokens to voters in storage.
    """

    @staticmethod
    def issue_token(voter: Voter, election_id: str) -> tuple[bool, str, str]:
        """Issue a new voting token for a voter.

        The token is created WITHOUT any voter reference, maintaining anonymity.
        The voter is only marked as having received a token (not which token).

        Args:
            voter: The voter requesting a token
            election_id: The election to issue token for

        Returns: (success, message, token_id or None)
        """
        # Validate election exists
        election = Election.find_by_election_id(election_id)
        if not election:
            return False, "Election not found", None

        # Check if election is ongoing
        if not election.is_ongoing():
            if election.has_ended():
                return False, "This election has ended", None
            else:
                return False, "This election has not started yet", None

        # Check if voter has already voted
        if voter.has_voted_in(election_id):
            return False, "You have already voted in this election", None

        # Check if voter already has a token issued
        if voter.has_token_for(election_id):
            return False, "A voting token has already been issued for this election", None

        try:
            # Create token WITHOUT voter reference (maintains anonymity)
            token = VotingToken.create(
                election_id=election_id,
                constituency=voter.constituency
            )

            # Mark voter as having received a token (but NOT which token)
            voter.mark_token_issued(election_id)

            return True, "Voting token issued successfully", token.token_id

        except Exception as e:
            return False, f"Failed to issue token: {str(e)}", None

    @staticmethod
    def validate_token(token_id: str, election_id: str,
                       ballot_type: str = None) -> tuple[bool, str, VotingToken]:
        """Validate a voting token.

        Args:
            token_id: The token to validate
            election_id: Expected election ID
            ballot_type: Optional specific ballot type to check

        Returns: (is_valid, message, token or None)
        """
        if not token_id:
            return False, "Token is required", None

        # Find token
        token = VotingToken.find_by_token_id(token_id)
        if not token:
            return False, "Invalid voting token", None

        # Verify token is for correct election
        if token.election_id != election_id:
            return False, "Token is not valid for this election", None

        # Check if token is fully used
        if token.is_fully_used:
            return False, "This voting token has already been used", None

        # If specific ballot type requested, check availability
        if ballot_type:
            if not token.is_valid_for_ballot(ballot_type):
                return False, f"Token has already been used for {ballot_type.upper()} ballot", None

        return True, "Token is valid", token

    @staticmethod
    def use_token_for_ballot(token_id: str, ballot_type: str) -> tuple[bool, str]:
        """Mark a ballot as used on a token.

        Uses atomic MongoDB operation to prevent race conditions.

        Args:
            token_id: The token being used
            ballot_type: The ballot type being cast ('fptp' or 'pr')

        Returns: (success, message)
        """
        if ballot_type not in VotingToken.BALLOT_TYPES:
            return False, f"Invalid ballot type: {ballot_type}"

        token = VotingToken.find_by_token_id(token_id)
        if not token:
            return False, "Invalid voting token"

        if token.is_fully_used:
            return False, "This voting token has already been fully used"

        if not token.is_valid_for_ballot(ballot_type):
            return False, f"Token has already been used for {ballot_type.upper()} ballot"

        # Atomic update
        success = token.mark_ballot_used(ballot_type)
        if not success:
            return False, "Failed to use token - it may have already been used"

        return True, f"Token used for {ballot_type.upper()} ballot"

    @staticmethod
    def get_token_stats(election_id: str) -> dict:
        """Get token statistics for an election.

        Returns: {
            'tokens_issued': int,
            'tokens_fully_used': int,
            'tokens_partial': int,
            'tokens_unused': int,
            'tokens_pending': int,  # issued - fully_used
            'fptp_ballots_cast': int,
            'pr_ballots_cast': int
        }
        """
        stats = VotingToken.get_election_stats(election_id)
        stats['tokens_pending'] = stats['tokens_issued'] - stats['tokens_fully_used']
        return stats

    @staticmethod
    def get_overall_stats() -> dict:
        """Get overall token statistics across all elections.

        Returns: {
            'total_tokens_issued': int,
            'total_tokens_used': int
        }
        """
        return {
            'total_tokens_issued': VotingToken.count_all(),
            'total_tokens_used': VotingToken.count_all_used()
        }

    @staticmethod
    def validate_token_constituency(token_id: str, constituency: str) -> tuple[bool, str]:
        """Validate that a token matches the expected constituency.

        This is used to ensure FPTP votes are cast for the correct constituency.

        Args:
            token_id: The token to validate
            constituency: Expected constituency

        Returns: (is_valid, message)
        """
        token = VotingToken.find_by_token_id(token_id)
        if not token:
            return False, "Invalid voting token"

        if token.constituency != constituency:
            return False, "Token constituency does not match"

        return True, "Token constituency is valid"

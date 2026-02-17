from app.models.voter import Voter
from app.models.vote import Vote
from app.models.election import Election
from app.services.token_service import TokenService
from app.utils.shamir_crypto import ElectionCrypto


class VoteService:
    """Service for handling dual-ballot voting operations (FPTP + PR).

    Votes are encrypted using the election's public key and can only be
    decrypted using Shamir's Secret Sharing when viewing results.
    """

    @staticmethod
    def cast_dual_ballot(voter: Voter, election_id: str,
                         candidate_id: str, party_id: str) -> tuple[bool, str]:
        """Cast both FPTP and PR votes in a single session.

        Args:
            voter: The voter casting the ballot
            election_id: The election to vote in
            candidate_id: Selected FPTP candidate (must be from voter's constituency)
            party_id: Selected PR party

        Returns: (success, message)
        """
        # Validate election exists
        election = Election.find_by_election_id(election_id)
        if not election:
            return False, "Election not found"

        # Check if election is ongoing
        if not election.is_ongoing():
            if election.has_ended():
                return False, "This election has ended"
            else:
                return False, "This election has not started yet"

        # Check if voter has already voted in this election
        if voter.has_voted_in(election_id):
            return False, "You have already voted in this election"

        # Validate FPTP candidate
        candidate = election.get_candidate(candidate_id)
        if not candidate:
            return False, "Invalid candidate selection"

        # Verify candidate is from voter's constituency
        if candidate.get('constituency') != voter.constituency:
            return False, "You can only vote for candidates in your constituency"

        # Validate PR party
        party = election.get_party(party_id)
        if not party:
            return False, "Invalid party selection"

        # Get election's public key for encryption
        if not election.public_key:
            return False, "Election encryption not configured"

        try:
            # Cast encrypted FPTP vote (anonymous)
            Vote.cast_fptp_vote(
                election_id=election_id,
                candidate_id=candidate_id,
                constituency=voter.constituency,
                public_key=election.public_key
            )

            # Cast encrypted PR vote (anonymous)
            Vote.cast_pr_vote(
                election_id=election_id,
                party_id=party_id,
                public_key=election.public_key
            )

            # Mark voter as having voted (doesn't link vote to voter)
            voter.mark_voted(election_id)

            return True, "Your dual ballot has been cast successfully!"
        except Exception as e:
            return False, f"Failed to cast vote: {str(e)}"

    @staticmethod
    def cast_dual_ballot_with_token(voter: Voter, election_id: str,
                                     candidate_id: str, party_id: str,
                                     token_id: str) -> tuple[bool, str, dict]:
        """Cast both FPTP and PR votes using a voting token.

        This method validates the token before accepting votes and uses
        atomic operations to prevent race conditions. Both votes share
        a single receipt ID for unified verification.

        Args:
            voter: The voter casting the ballot
            election_id: The election to vote in
            candidate_id: Selected FPTP candidate (must be from voter's constituency)
            party_id: Selected PR party
            token_id: The voting token to use

        Returns: (success, message, receipt_info)
            receipt_info: {'receipt_id': str, 'timestamp': str} on success
        """
        from datetime import datetime

        # Validate election exists
        election = Election.find_by_election_id(election_id)
        if not election:
            return False, "Election not found", {}

        # Check if election is ongoing
        if not election.is_ongoing():
            if election.has_ended():
                return False, "This election has ended", {}
            else:
                return False, "This election has not started yet", {}

        # Check if voter has already voted in this election
        if voter.has_voted_in(election_id):
            return False, "You have already voted in this election", {}

        # Validate token for this election
        valid, msg, token = TokenService.validate_token(token_id, election_id)
        if not valid:
            return False, msg, {}

        # Validate token constituency matches voter
        valid, msg = TokenService.validate_token_constituency(token_id, voter.constituency)
        if not valid:
            return False, msg, {}

        # Validate FPTP candidate
        candidate = election.get_candidate(candidate_id)
        if not candidate:
            return False, "Invalid candidate selection", {}

        # Verify candidate is from voter's constituency
        if candidate.get('constituency') != voter.constituency:
            return False, "You can only vote for candidates in your constituency", {}

        # Validate PR party
        party = election.get_party(party_id)
        if not party:
            return False, "Invalid party selection", {}

        # Get election's public key for encryption
        if not election.public_key:
            return False, "Election encryption not configured", {}

        try:
            # Generate a single shared receipt for both ballots
            timestamp = datetime.utcnow()
            receipt_id, receipt_hash, timestamp_str = Vote.generate_receipt(election_id, timestamp)

            # Use token for FPTP ballot (atomic operation)
            success, msg = TokenService.use_token_for_ballot(token_id, 'fptp')
            if not success:
                return False, f"FPTP ballot failed: {msg}", {}

            # Cast encrypted FPTP vote with shared receipt
            fptp_vote = Vote.cast_fptp_vote(
                election_id=election_id,
                candidate_id=candidate_id,
                constituency=voter.constituency,
                public_key=election.public_key,
                token_id=token_id,
                receipt_id=receipt_id,
                receipt_hash=receipt_hash,
                timestamp=timestamp,
                timestamp_str=timestamp_str
            )

            # Use token for PR ballot (atomic operation)
            success, msg = TokenService.use_token_for_ballot(token_id, 'pr')
            if not success:
                return False, f"PR ballot failed: {msg}", {}

            # Cast encrypted PR vote with same shared receipt
            pr_vote = Vote.cast_pr_vote(
                election_id=election_id,
                party_id=party_id,
                public_key=election.public_key,
                token_id=token_id,
                receipt_id=receipt_id,
                receipt_hash=receipt_hash,
                timestamp=timestamp,
                timestamp_str=timestamp_str
            )

            # Mark voter as having voted (doesn't link vote to voter)
            voter.mark_voted(election_id)

            # Return single receipt info for voter verification
            receipt_info = {
                'receipt_id': receipt_id,
                'timestamp': timestamp.strftime('%B %d, %Y at %I:%M %p')
            }

            return True, "Your dual ballot has been cast successfully!", receipt_info

        except Exception as e:
            return False, f"Failed to cast vote: {str(e)}", {}

    @staticmethod
    def get_fptp_results(election_id: str) -> tuple[bool, str, dict]:
        """Get FPTP results with winners per constituency.

        Returns: (success, message, results)
        Results format: {
            'constituencies': {
                'Kathmandu': {
                    'candidates': [{candidate_id, name, party, votes}, ...],
                    'winner': {candidate_id, name, party, votes},
                    'total_votes': int
                },
                ...
            },
            'election': Election
        }
        """
        election = Election.find_by_election_id(election_id)
        if not election:
            return False, "Election not found", None

        # Get raw FPTP vote counts by constituency
        vote_counts = Vote.get_fptp_results(election_id)

        # Build results per constituency
        constituencies = {}
        for constituency in Election.VALID_CONSTITUENCIES:
            constituency_candidates = election.get_candidates_by_constituency(constituency)
            constituency_votes = vote_counts.get(constituency, {})

            candidates_results = []
            for candidate in constituency_candidates:
                candidates_results.append({
                    'candidate_id': candidate['candidate_id'],
                    'name': candidate['name'],
                    'party': candidate['party'],
                    'votes': constituency_votes.get(candidate['candidate_id'], 0)
                })

            # Sort by votes descending
            candidates_results.sort(key=lambda x: x['votes'], reverse=True)

            # Determine winner (highest votes)
            winner = candidates_results[0] if candidates_results else None
            total_votes = sum(c['votes'] for c in candidates_results)

            constituencies[constituency] = {
                'candidates': candidates_results,
                'winner': winner,
                'total_votes': total_votes
            }

        return True, "FPTP results retrieved", {
            'constituencies': constituencies,
            'election': election
        }

    @staticmethod
    def get_pr_results(election_id: str) -> tuple[bool, str, dict]:
        """Get PR results with seat allocation using Largest Remainder method.

        Returns: (success, message, results)
        Results format: {
            'parties': [{party_id, name, votes, percentage, seats}, ...],
            'total_votes': int,
            'total_seats': int,
            'election': Election
        }
        """
        election = Election.find_by_election_id(election_id)
        if not election:
            return False, "Election not found", None

        # Get raw PR vote counts
        vote_counts = Vote.get_pr_results(election_id)
        total_votes = sum(vote_counts.values())
        total_seats = election.total_pr_seats

        # Calculate seat allocation using Largest Remainder (Hare quota)
        seat_allocation = VoteService._allocate_pr_seats(vote_counts, total_seats)

        # Build party results
        parties_results = []
        for party in election.parties:
            party_id = party['party_id']
            votes = vote_counts.get(party_id, 0)
            percentage = (votes / total_votes * 100) if total_votes > 0 else 0
            seats = seat_allocation.get(party_id, 0)

            party_result = {
                'party_id': party_id,
                'name': party['name'],
                'votes': votes,
                'percentage': round(percentage, 2),
                'seats': seats
            }
            if party.get('symbol'):
                party_result['symbol'] = party['symbol']
            parties_results.append(party_result)

        # Sort by seats descending, then by votes
        parties_results.sort(key=lambda x: (x['seats'], x['votes']), reverse=True)

        return True, "PR results retrieved", {
            'parties': parties_results,
            'total_votes': total_votes,
            'total_seats': total_seats,
            'election': election
        }

    @staticmethod
    def _allocate_pr_seats(party_votes: dict, total_seats: int) -> dict:
        """Allocate PR seats using Largest Remainder method (Hare quota).

        Args:
            party_votes: {party_id: vote_count, ...}
            total_seats: Total seats to allocate

        Returns: {party_id: seats_allocated, ...}
        """
        if not party_votes:
            return {}

        total_votes = sum(party_votes.values())
        if total_votes == 0:
            return {party_id: 0 for party_id in party_votes}

        # Calculate Hare quota
        quota = total_votes / total_seats

        allocation = {}
        remainders = {}

        # First allocation: integer division by quota
        for party_id, votes in party_votes.items():
            if quota > 0:
                seats = int(votes / quota)
                allocation[party_id] = seats
                remainders[party_id] = (votes / quota) - seats
            else:
                allocation[party_id] = 0
                remainders[party_id] = 0

        # Calculate remaining seats to distribute
        allocated_seats = sum(allocation.values())
        remaining_seats = total_seats - allocated_seats

        # Distribute remaining seats by largest remainder
        sorted_remainders = sorted(remainders.items(), key=lambda x: x[1], reverse=True)

        for party_id, _ in sorted_remainders[:remaining_seats]:
            allocation[party_id] += 1

        return allocation

    @staticmethod
    def get_combined_results(election_id: str) -> tuple[bool, str, dict]:
        """Get combined FPTP and PR results.

        Returns: (success, message, results)
        """
        success_fptp, msg_fptp, fptp_results = VoteService.get_fptp_results(election_id)
        if not success_fptp:
            return False, msg_fptp, None

        success_pr, msg_pr, pr_results = VoteService.get_pr_results(election_id)
        if not success_pr:
            return False, msg_pr, None

        return True, "Combined results retrieved", {
            'fptp': fptp_results,
            'pr': pr_results,
            'election': fptp_results['election']
        }

    @staticmethod
    def get_voter_elections(voter: Voter) -> dict:
        """Get elections categorized for a voter.

        Returns: {
            'active': [elections available to vote],
            'voted': [elections already voted in],
            'upcoming': [elections not started],
            'past': [elections that have ended]
        }
        """
        active_elections = Election.get_active_elections()
        upcoming_elections = Election.get_upcoming_elections()
        past_elections = Election.get_past_elections()

        # Separate active elections into voted and available
        available_to_vote = []
        already_voted = []

        for election in active_elections:
            if voter.has_voted_in(election.election_id):
                already_voted.append(election)
            else:
                available_to_vote.append(election)

        # Also include past elections where voter voted
        for election in past_elections:
            if voter.has_voted_in(election.election_id):
                already_voted.append(election)

        return {
            'active': available_to_vote,
            'voted': already_voted,
            'upcoming': upcoming_elections,
            'past': past_elections
        }

    @staticmethod
    def decrypt_and_get_results(election_id: str, shares: list) -> tuple[bool, str, dict]:
        """Decrypt votes and get combined results using Shamir shares.

        Args:
            election_id: The election ID
            shares: List of (index, value) tuples from election officials

        Returns: (success, message, results)
        """
        election = Election.find_by_election_id(election_id)
        if not election:
            return False, "Election not found", None

        if not election.has_ended():
            return False, "Results are only available after the election has ended", None

        if not election.encrypted_key_bundle:
            return False, "Election encryption data not found", None

        try:
            # Reconstruct both private keys from shares (hybrid PQC)
            crypto = ElectionCrypto()
            rsa_private_key, kyber_private_key = crypto.reconstruct_private_keys(shares, election.encrypted_key_bundle)

            # Get all encrypted votes
            from app import get_db
            db = get_db()
            encrypted_votes = list(db.votes.find({'election_id': election_id}))

            # Decrypt votes and count
            fptp_counts = {}  # {constituency: {candidate_id: count}}
            pr_counts = {}  # {party_id: count}

            for enc_vote in encrypted_votes:
                if not enc_vote.get('encrypted_vote'):
                    continue

                # Decrypt the vote using hybrid decryption
                decrypted = crypto.decrypt_vote(enc_vote['encrypted_vote'], rsa_private_key, kyber_private_key)

                ballot_type = decrypted.get('ballot_type')

                if ballot_type == 'fptp':
                    constituency = decrypted.get('constituency')
                    candidate_id = decrypted.get('candidate_id')

                    if constituency not in fptp_counts:
                        fptp_counts[constituency] = {}
                    if candidate_id not in fptp_counts[constituency]:
                        fptp_counts[constituency][candidate_id] = 0
                    fptp_counts[constituency][candidate_id] += 1

                elif ballot_type == 'pr':
                    party_id = decrypted.get('party_id')

                    if party_id not in pr_counts:
                        pr_counts[party_id] = 0
                    pr_counts[party_id] += 1

            # Build FPTP results
            fptp_results = VoteService._build_fptp_results(election, fptp_counts)

            # Build PR results
            pr_results = VoteService._build_pr_results(election, pr_counts)

            return True, "Results decrypted successfully", {
                'fptp': fptp_results,
                'pr': pr_results,
                'election': election
            }

        except Exception as e:
            return False, f"Failed to decrypt results: {str(e)}", None

    @staticmethod
    def _build_fptp_results(election: Election, vote_counts: dict) -> dict:
        """Build FPTP results structure from decrypted vote counts."""
        constituencies = {}

        for constituency in Election.VALID_CONSTITUENCIES:
            constituency_candidates = election.get_candidates_by_constituency(constituency)
            constituency_votes = vote_counts.get(constituency, {})

            candidates_results = []
            for candidate in constituency_candidates:
                candidates_results.append({
                    'candidate_id': candidate['candidate_id'],
                    'name': candidate['name'],
                    'party': candidate['party'],
                    'votes': constituency_votes.get(candidate['candidate_id'], 0)
                })

            # Sort by votes descending
            candidates_results.sort(key=lambda x: x['votes'], reverse=True)

            # Determine winner
            winner = candidates_results[0] if candidates_results else None
            total_votes = sum(c['votes'] for c in candidates_results)

            constituencies[constituency] = {
                'candidates': candidates_results,
                'winner': winner,
                'total_votes': total_votes
            }

        return {
            'constituencies': constituencies,
            'election': election
        }

    @staticmethod
    def _build_pr_results(election: Election, vote_counts: dict) -> dict:
        """Build PR results structure from decrypted vote counts."""
        total_votes = sum(vote_counts.values())
        total_seats = election.total_pr_seats

        # Calculate seat allocation
        seat_allocation = VoteService._allocate_pr_seats(vote_counts, total_seats)

        # Build party results
        parties_results = []
        for party in election.parties:
            party_id = party['party_id']
            votes = vote_counts.get(party_id, 0)
            percentage = (votes / total_votes * 100) if total_votes > 0 else 0
            seats = seat_allocation.get(party_id, 0)

            party_result = {
                'party_id': party_id,
                'name': party['name'],
                'votes': votes,
                'percentage': round(percentage, 2),
                'seats': seats
            }
            if party.get('symbol'):
                party_result['symbol'] = party['symbol']
            parties_results.append(party_result)

        # Sort by seats descending, then by votes
        parties_results.sort(key=lambda x: (x['seats'], x['votes']), reverse=True)

        return {
            'parties': parties_results,
            'total_votes': total_votes,
            'total_seats': total_seats,
            'election': election
        }

    @staticmethod
    def validate_shares(election_id: str, shares: list) -> tuple[bool, str]:
        """Validate that shares can reconstruct the private key.

        Args:
            election_id: The election ID
            shares: List of (index, value) tuples

        Returns: (success, message)
        """
        election = Election.find_by_election_id(election_id)
        if not election:
            return False, "Election not found"

        if not election.encrypted_key_bundle:
            return False, "Election encryption data not found"

        if len(shares) < 3:
            return False, "At least 3 shares are required"

        try:
            crypto = ElectionCrypto()
            # Try to reconstruct - will fail if shares are invalid
            crypto.reconstruct_private_key(shares, election.encrypted_key_bundle)
            return True, "Shares validated successfully"
        except Exception as e:
            return False, f"Invalid shares: {str(e)}"

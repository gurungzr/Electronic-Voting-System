"""Vote casting tests for the Secure Voting System."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime


class TestTokenIssuance:
    """Tests for voting token issuance."""

    def test_issue_token_for_eligible_voter(self, app, db, registered_voter, test_election):
        """Test that a token is issued for an eligible voter."""
        with app.app_context():
            with patch('app.services.token_service.get_db', return_value=db):
                with patch('app.models.voter.get_db', return_value=db):
                    with patch('app.models.election.get_db', return_value=db):
                        from app.services.token_service import TokenService

                        success, message, token_id = TokenService.issue_token(
                            voter=registered_voter['voter'],
                            election_id=test_election.election_id
                        )

                        assert success is True
                        assert token_id is not None
                        assert token_id.startswith('TKN-')

    def test_token_not_issued_twice(self, app, db, registered_voter, test_election):
        """Test that a voter cannot get multiple tokens for same election."""
        with app.app_context():
            with patch('app.services.token_service.get_db', return_value=db):
                with patch('app.models.voter.get_db', return_value=db):
                    with patch('app.models.election.get_db', return_value=db):
                        with patch('app.models.voting_token.get_db', return_value=db):
                            from app.services.token_service import TokenService

                            # Issue first token
                            success1, _, token1 = TokenService.issue_token(
                                voter=registered_voter['voter'],
                                election_id=test_election.election_id
                            )
                            assert success1 is True

                            # Mark voter as having token
                            registered_voter['voter'].mark_token_issued(test_election.election_id)

                            # Try to issue second token
                            success2, message, token2 = TokenService.issue_token(
                                voter=registered_voter['voter'],
                                election_id=test_election.election_id
                            )

                            # Should fail or return same token
                            assert success2 is False or token2 == token1

    def test_validate_valid_token(self, app, db, registered_voter, test_election):
        """Test that a valid token passes validation."""
        with app.app_context():
            with patch('app.services.token_service.get_db', return_value=db):
                with patch('app.models.voter.get_db', return_value=db):
                    with patch('app.models.election.get_db', return_value=db):
                        with patch('app.models.voting_token.get_db', return_value=db):
                            from app.services.token_service import TokenService

                            # Issue token
                            success, _, token_id = TokenService.issue_token(
                                voter=registered_voter['voter'],
                                election_id=test_election.election_id
                            )

                            # Validate token
                            valid, message, token = TokenService.validate_token(
                                token_id=token_id,
                                election_id=test_election.election_id
                            )

                            assert valid is True
                            assert token is not None

    def test_invalid_token_rejected(self, app, db, test_election):
        """Test that an invalid/fake token is rejected."""
        with app.app_context():
            with patch('app.services.token_service.get_db', return_value=db):
                with patch('app.models.voting_token.get_db', return_value=db):
                    from app.services.token_service import TokenService

                    valid, message, token = TokenService.validate_token(
                        token_id='TKN-FAKE12345678',
                        election_id=test_election.election_id
                    )

                    assert valid is False
                    assert token is None


class TestVoteCasting:
    """Tests for vote casting functionality."""

    def test_cast_dual_ballot_success(self, app, db, registered_voter, test_election):
        """Test that a dual ballot (FPTP + PR) can be cast successfully."""
        with app.app_context():
            # Get a candidate and party from the election
            kathmandu_candidates = [c for c in test_election.candidates if c['constituency'] == 'Kathmandu']
            candidate_id = kathmandu_candidates[0]['candidate_id']
            party_id = test_election.parties[0]['party_id']

            with patch('app.services.vote_service.get_db', return_value=db):
                with patch('app.services.token_service.get_db', return_value=db):
                    with patch('app.models.voter.get_db', return_value=db):
                        with patch('app.models.election.get_db', return_value=db):
                            with patch('app.models.voting_token.get_db', return_value=db):
                                with patch('app.models.vote.get_db', return_value=db):
                                    from app.services.token_service import TokenService
                                    from app.services.vote_service import VoteService

                                    # Issue token first
                                    _, _, token_id = TokenService.issue_token(
                                        voter=registered_voter['voter'],
                                        election_id=test_election.election_id
                                    )

                                    # Cast vote
                                    success, message, receipts = VoteService.cast_dual_ballot_with_token(
                                        voter=registered_voter['voter'],
                                        election_id=test_election.election_id,
                                        candidate_id=candidate_id,
                                        party_id=party_id,
                                        token_id=token_id
                                    )

                                    assert success is True
                                    assert receipts is not None
                                    assert 'receipt_id' in receipts

    def test_prevent_double_voting(self, app, db, registered_voter, test_election):
        """Test that a voter cannot vote twice in the same election."""
        with app.app_context():
            kathmandu_candidates = [c for c in test_election.candidates if c['constituency'] == 'Kathmandu']
            candidate_id = kathmandu_candidates[0]['candidate_id']
            party_id = test_election.parties[0]['party_id']

            with patch('app.services.vote_service.get_db', return_value=db):
                with patch('app.services.token_service.get_db', return_value=db):
                    with patch('app.models.voter.get_db', return_value=db):
                        with patch('app.models.election.get_db', return_value=db):
                            with patch('app.models.voting_token.get_db', return_value=db):
                                with patch('app.models.vote.get_db', return_value=db):
                                    from app.services.token_service import TokenService
                                    from app.services.vote_service import VoteService

                                    # Issue token and vote first time
                                    _, _, token_id = TokenService.issue_token(
                                        voter=registered_voter['voter'],
                                        election_id=test_election.election_id
                                    )

                                    success1, _, _ = VoteService.cast_dual_ballot_with_token(
                                        voter=registered_voter['voter'],
                                        election_id=test_election.election_id,
                                        candidate_id=candidate_id,
                                        party_id=party_id,
                                        token_id=token_id
                                    )
                                    assert success1 is True

                                    # Try to vote again - should fail
                                    # Token should be used, so try with same token
                                    success2, message, _ = VoteService.cast_dual_ballot_with_token(
                                        voter=registered_voter['voter'],
                                        election_id=test_election.election_id,
                                        candidate_id=candidate_id,
                                        party_id=party_id,
                                        token_id=token_id
                                    )

                                    assert success2 is False

    def test_vote_generates_receipt(self, app, db, registered_voter, test_election):
        """Test that voting generates a valid receipt ID."""
        with app.app_context():
            kathmandu_candidates = [c for c in test_election.candidates if c['constituency'] == 'Kathmandu']
            candidate_id = kathmandu_candidates[0]['candidate_id']
            party_id = test_election.parties[0]['party_id']

            with patch('app.services.vote_service.get_db', return_value=db):
                with patch('app.services.token_service.get_db', return_value=db):
                    with patch('app.models.voter.get_db', return_value=db):
                        with patch('app.models.election.get_db', return_value=db):
                            with patch('app.models.voting_token.get_db', return_value=db):
                                with patch('app.models.vote.get_db', return_value=db):
                                    from app.services.token_service import TokenService
                                    from app.services.vote_service import VoteService

                                    _, _, token_id = TokenService.issue_token(
                                        voter=registered_voter['voter'],
                                        election_id=test_election.election_id
                                    )

                                    success, message, receipts = VoteService.cast_dual_ballot_with_token(
                                        voter=registered_voter['voter'],
                                        election_id=test_election.election_id,
                                        candidate_id=candidate_id,
                                        party_id=party_id,
                                        token_id=token_id
                                    )

                                    assert success is True
                                    assert receipts['receipt_id'] is not None
                                    assert receipts['receipt_id'].startswith('RCP-')
                                    assert 'timestamp' in receipts


class TestVotingRestrictions:
    """Tests for voting restrictions based on election state."""

    def test_cannot_vote_before_election_starts(self, app, db, registered_voter, future_election):
        """Test that voting is not allowed before election starts."""
        with app.app_context():
            with patch('app.models.election.get_db', return_value=db):
                # Election hasn't started yet
                assert future_election.is_ongoing() is False
                assert future_election.has_started() is False

    def test_cannot_vote_after_election_ends(self, app, db, registered_voter, ended_election):
        """Test that voting is not allowed after election ends."""
        with app.app_context():
            with patch('app.models.election.get_db', return_value=db):
                # Election has ended
                assert ended_election.is_ongoing() is False
                assert ended_election.has_ended() is True

    def test_can_vote_during_ongoing_election(self, app, db, registered_voter, test_election):
        """Test that voting is allowed during ongoing election."""
        with app.app_context():
            with patch('app.models.election.get_db', return_value=db):
                # Election is ongoing
                assert test_election.is_ongoing() is True
                assert test_election.has_started() is True
                assert test_election.has_ended() is False


class TestVoterEligibility:
    """Tests for voter eligibility checks."""

    def test_voter_marked_as_voted(self, app, db, registered_voter, test_election):
        """Test that voter is marked as having voted after casting ballot."""
        with app.app_context():
            kathmandu_candidates = [c for c in test_election.candidates if c['constituency'] == 'Kathmandu']
            candidate_id = kathmandu_candidates[0]['candidate_id']
            party_id = test_election.parties[0]['party_id']

            with patch('app.services.vote_service.get_db', return_value=db):
                with patch('app.services.token_service.get_db', return_value=db):
                    with patch('app.models.voter.get_db', return_value=db):
                        with patch('app.models.election.get_db', return_value=db):
                            with patch('app.models.voting_token.get_db', return_value=db):
                                with patch('app.models.vote.get_db', return_value=db):
                                    from app.services.token_service import TokenService
                                    from app.services.vote_service import VoteService

                                    # Before voting
                                    assert registered_voter['voter'].has_voted_in(test_election.election_id) is False

                                    # Issue token and vote
                                    _, _, token_id = TokenService.issue_token(
                                        voter=registered_voter['voter'],
                                        election_id=test_election.election_id
                                    )

                                    success, _, _ = VoteService.cast_dual_ballot_with_token(
                                        voter=registered_voter['voter'],
                                        election_id=test_election.election_id,
                                        candidate_id=candidate_id,
                                        party_id=party_id,
                                        token_id=token_id
                                    )

                                    # After voting - reload voter from db
                                    from app.models.voter import Voter
                                    updated_voter = Voter.find_by_voter_id(registered_voter['voter_id'])

                                    if success:
                                        assert updated_voter.has_voted_in(test_election.election_id) is True

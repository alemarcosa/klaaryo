"""Exceptions for the talent_pool managers."""


class CandidateNotFound(Exception):
    """Raised when a candidate with the given PK does not exist."""


class InvalidCandidate(Exception):
    """Raised when candidate data is invalid."""

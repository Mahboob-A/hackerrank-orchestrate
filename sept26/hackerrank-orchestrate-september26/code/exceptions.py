"""Domain-specific exceptions for Buy or Wait financial decision engine."""


class DomainError(Exception):
    """Base exception for all domain errors."""
    pass


class MissingAmountError(DomainError):
    """Raised when an event amount is missing and cannot be resolved."""
    pass


class ExchangeRateNotFoundError(DomainError, LookupError):
    """Raised when a required currency exchange rate is not found."""
    pass


class SchemaValidationError(DomainError, ValueError):
    """Raised when an input record fails schema or domain constraints."""
    pass


class InfeasiblePlanError(DomainError):
    """Raised when a candidate plan breaches cashflow safety invariants."""
    pass

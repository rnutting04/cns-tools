# app/services/letters/exceptions.py
"""
Domain exceptions raised by the letter generation service.

These are translated to HTTP status codes at the route layer.
Keeping them separate from HTTPException means the service can be
called from workers, scripts, or batch jobs without FastAPI in scope.
"""


class LetterServiceError(Exception):
    """Base exception for letter service errors."""


class TemplateNotFound(LetterServiceError):
    pass


class AssociationNotFound(LetterServiceError):
    pass


class ManagerNotFound(LetterServiceError):
    pass


class AccessDenied(LetterServiceError):
    pass


class InvalidTemplateConfiguration(LetterServiceError):
    """Template is missing a required field definition (e.g. association field)."""


class MissingRequiredField(LetterServiceError):
    """User didn't provide a required field."""


class RenderFailed(LetterServiceError):
    """The renderer threw an exception while generating the document."""
# app/services/letters/__init__.py
from app.services.letters.service import (
    LetterGenerationResult,
    generate_letter,
)

__all__ = ["LetterGenerationResult", "generate_letter"]
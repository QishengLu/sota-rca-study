"""v4 metacognitive middleware — opus-4.7-driven, framework-aware.

Entry point: ``MiddlewarePipeline`` (see pipeline.py).
Activation: env ``MIDDLEWARE_VERSION=v4``.
"""

from .config import V4Config
from .pipeline import V4Pipeline
from .state import V4State

__all__ = ["V4Config", "V4Pipeline", "V4State"]

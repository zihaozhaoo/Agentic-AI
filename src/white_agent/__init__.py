"""
White Agent Module

This module provides the interface and data structures for white agents
that participate in the Green Agent evaluation.
"""

from .data_structures import (
    Location,
    StructuredRequest,
    RoutingDecision,
    NaturalLanguageRequest,
    RequestPriority
)
from .base_agent import WhiteAgentBase, DummyWhiteAgent
from .baseline_agents import RandomBaselineAgent, RegexBaselineAgent

__all__ = [
    'Location',
    'StructuredRequest',
    'RoutingDecision',
    'NaturalLanguageRequest',
    'RequestPriority',
    'WhiteAgentBase',
    'DummyWhiteAgent',
    'RandomBaselineAgent',
    'RegexBaselineAgent',
]

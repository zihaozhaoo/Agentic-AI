"""
White Agent Module

This module provides the interface and data structures for white agents
that participate in the Green Agent evaluation.
"""

from white_agent.data_structures import (
    Location,
    StructuredRequest,
    RoutingDecision,
    NaturalLanguageRequest,
    RequestPriority
)
from white_agent.base_agent import WhiteAgentBase, DummyWhiteAgent

__all__ = [
    'Location',
    'StructuredRequest',
    'RoutingDecision',
    'NaturalLanguageRequest',
    'RequestPriority',
    'WhiteAgentBase',
    'DummyWhiteAgent',
]

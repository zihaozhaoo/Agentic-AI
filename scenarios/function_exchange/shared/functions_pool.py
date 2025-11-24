# -*- coding: utf-8 -*-
"""
Registry of callable math functions that both agents use during evaluation.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List


# Comment: Data container that holds metadata about each registered function.
@dataclass
class RegisteredFunction:
    """
    Represents a callable math function with human readable description and
    a sampler used to provide valid inputs for the function.
    """

    name: str
    description: str
    handler: Callable[[float], float]
    sample_input: Callable[[random.Random], float]

    def evaluate(self, x: float) -> float:
        """
        Evaluate the function at x and return a float result.
        """
        return float(self.handler(x))


# Comment: Build the registry with both requested functions.
FUNCTION_REGISTRY: Dict[str, RegisteredFunction] = {
    "sqrt_plus_constant": RegisteredFunction(
        name="sqrt_plus_constant",
        description=(
            "Take the square root of x and add the fixed offset 114514. "
            "The function expects non-negative inputs."
        ),
        handler=lambda x: math.sqrt(x) + 114_514,
        sample_input=lambda rng: round(rng.uniform(1, 1_000_000), 2),
    ),
    "cube_minus_constant": RegisteredFunction(
        name="cube_minus_constant",
        description=(
            "Cube x and subtract the fixed offset 350234. The function accepts "
            "any real number input."
        ),
        handler=lambda x: (x**3) - 350_234,
        sample_input=lambda rng: round(rng.uniform(-10_000, 10_000), 2),
    ),
}


# Comment: Helper that returns the canonical RegisteredFunction.
def get_function(name: str) -> RegisteredFunction:
    """
    Fetch a function by name or raise a ValueError when an invalid name is used.
    """
    if name not in FUNCTION_REGISTRY:
        raise ValueError(
            f"Unknown function '{name}'. Options: {list(FUNCTION_REGISTRY)}"
        )
    return FUNCTION_REGISTRY[name]


# Comment: Randomly select a RegisteredFunction, optionally using a seed for deterministic tests.
def choose_function(name: str | None = None, seed: int | None = None) -> RegisteredFunction:
    """
    Either return the function specified by name or pick one uniformly at random
    using an optional deterministic seed.
    """
    if name:
        return get_function(name)
    rng = random.Random(seed)
    return rng.choice(list(FUNCTION_REGISTRY.values()))


# Comment: Provide a serializable catalog for LLM prompts/logging.
def describe_functions() -> List[Dict[str, str]]:
    """
    Return a list of dictionaries with name and description so that agent prompts
    and logs can summarize the available functions.
    """
    return [
        {"name": fn.name, "description": fn.description}
        for fn in FUNCTION_REGISTRY.values()
    ]


# Comment: Convenience wrapper that evaluates a named function at x.
def evaluate_function(name: str, x: float) -> float:
    """
    Evaluate the requested function and return the float result, enforcing that
    the function exists before dispatching.
    """
    fn = get_function(name)
    return fn.evaluate(x)


# Comment: Generate an input value for a function by name.
def sample_input_for(name: str, seed: int | None = None) -> float:
    """
    Produce a valid input for the specified function using its sampler so the
    orchestrator can test agents deterministically.
    """
    rng = random.Random(seed)
    fn = get_function(name)
    return fn.sample_input(rng)


# Comment: Provide the registry to prompts in a formatted string.
def format_function_menu() -> str:
    """
    Render the registry as a human readable list that can be pasted inside
    an agent prompt or log entry.
    """
    lines = []
    for fn in FUNCTION_REGISTRY.values():
        lines.append(f"- {fn.name}: {fn.description}")
    return "\n".join(lines)


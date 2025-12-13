"""
LLM-based Natural Language Request Generator

This module generates natural language ride requests using LLM APIs
(OpenAI GPT or Anthropic Claude) for more varied and realistic requests.
"""

import os
from typing import Dict, List, Optional, Any
import json
import random
from datetime import datetime


class LLMGenerator:
    """Generates natural language ride requests using LLMs."""

    def __init__(
        self,
        provider: str = "openai",
        api_key: Optional[str] = None,
        model: Optional[str] = None
    ):
        """
        Initialize LLM generator.

        Args:
            provider: "openai" or "anthropic"
            api_key: API key (if None, reads from environment)
            model: Model name (uses default if None)
        """
        self.provider = provider.lower()

        # Set API key
        if api_key is None:
            if self.provider == "openai":
                api_key = os.getenv("OPENAI_API_KEY")
            elif self.provider == "anthropic":
                api_key = os.getenv("ANTHROPIC_API_KEY")

        self.api_key = api_key

        # Set model
        if model is None:
            if self.provider == "openai":
                model = "gpt-4o-mini"  # Cheaper and faster
            elif self.provider == "anthropic":
                model = "claude-3-haiku-20240307"  # Cheaper and faster

        self.model = model

        # Initialize client
        self._init_client()

        # System prompt for generating requests
        self.system_prompt = """You are generating realistic ride-hailing requests for NYC.
Given structured trip information, generate a natural, conversational request a real person would make.

Requirements:
- Be natural and conversational
- Vary the phrasing and style
- Include relevant details when appropriate
- Sometimes use informal language
- Sometimes be more formal or business-like
- Include reasons for trips occasionally
- Use different ways to refer to locations (address, landmark, neighborhood, personal reference)
- When multiple location options are provided, prefer the most accurate one (addresses > POIs > zones)
- Keep it realistic to what someone would actually say

Generate ONLY the request text, nothing else."""

    def _init_client(self):
        """Initialize the LLM client based on provider."""
        try:
            if self.provider == "openai":
                import openai
                self.client = openai.OpenAI(api_key=self.api_key)
            elif self.provider == "anthropic":
                import anthropic
                self.client = anthropic.Anthropic(api_key=self.api_key)
            else:
                raise ValueError(f"Unsupported provider: {self.provider}")
        except ImportError as e:
            print(f"Warning: Could not import {self.provider} library: {e}")
            print("LLM generation will not be available.")
            self.client = None

    def _format_trip_info(self, trip_data: Dict[str, Any]) -> str:
        """Format trip data into a prompt for the LLM."""
        parts = []

        # Origin
        # NOTE: Prioritize address/personal over POI when available
        # POIs are zone-level and may not match actual augmented location
        origin_parts = []
        if trip_data.get('pickup_personal'):
            origin_parts.append(f"Personal location: {trip_data['pickup_personal']}")
        if trip_data.get('pickup_address'):
            origin_parts.append(f"Address: {trip_data['pickup_address']} (MOST ACCURATE)")
        elif trip_data.get('pickup_poi'):
            origin_parts.append(f"POI: {trip_data['pickup_poi']}")
        origin_parts.append(f"Zone: {trip_data['pickup_zone']}")

        parts.append(f"Origin: {', '.join(origin_parts)}")

        # Destination
        dest_parts = []
        if trip_data.get('dropoff_personal'):
            dest_parts.append(f"Personal location: {trip_data['dropoff_personal']}")
        if trip_data.get('dropoff_address'):
            dest_parts.append(f"Address: {trip_data['dropoff_address']} (MOST ACCURATE)")
        elif trip_data.get('dropoff_poi'):
            dest_parts.append(f"POI: {trip_data['dropoff_poi']}")
        dest_parts.append(f"Zone: {trip_data['dropoff_zone']}")

        parts.append(f"Destination: {', '.join(dest_parts)}")

        # Pickup time
        request_time = trip_data.get('requested_pickup_time') or trip_data.get('request_time')
        if request_time:
            if isinstance(request_time, str):
                parts.append(f"Requested pickup time: {request_time}")
            else:
                parts.append(f"Requested pickup time: {request_time.strftime('%I:%M %p, %A')}")

        # Pickup time window
        if trip_data.get('pickup_window_minutes'):
            parts.append(f"Pickup window: ±{trip_data['pickup_window_minutes']} minutes")

        # Arrival time constraint
        if trip_data.get('has_arrival_constraint') and trip_data.get('requested_dropoff_time'):
            dropoff_time = trip_data['requested_dropoff_time']
            if isinstance(dropoff_time, str):
                parts.append(f"Requested arrival time: {dropoff_time}")
            else:
                parts.append(f"Requested arrival time: {dropoff_time.strftime('%I:%M %p')}")

            if trip_data.get('dropoff_window_minutes'):
                parts.append(f"Arrival window: ±{trip_data['dropoff_window_minutes']} minutes")

            if trip_data.get('is_tight_constraint'):
                parts.append("Time constraint: TIGHT - customer is in a hurry")

        # Duration estimate
        if trip_data.get('estimated_duration_minutes'):
            parts.append(f"Estimated duration: {trip_data['estimated_duration_minutes']} minutes")

        # Available time
        if trip_data.get('available_trip_time_minutes'):
            parts.append(f"Available time for trip: {trip_data['available_trip_time_minutes']:.0f} minutes")

        # Passengers
        if trip_data.get('passenger_count'):
            parts.append(f"Passengers: {trip_data['passenger_count']}")

        # Special requirements
        if trip_data.get('wav_request_flag') == 'Y':
            parts.append("Requires wheelchair-accessible vehicle")

        if trip_data.get('shared_request_flag') == 'Y':
            parts.append("Open to shared/pooled ride")

        # Context hints for more realistic generation
        hour = request_time.hour if hasattr(request_time, 'hour') else None
        if hour is not None:
            if 7 <= hour <= 9:
                parts.append("Context: Morning rush hour")
            elif 17 <= hour <= 19:
                parts.append("Context: Evening rush hour")
            elif 22 <= hour or hour <= 5:
                parts.append("Context: Late night/early morning")

        return "\n".join(parts)

    def _call_openai(self, prompt: str) -> str:
        """Call OpenAI API to generate request."""
        if self.client is None:
            raise RuntimeError("OpenAI client not initialized")

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.9,  # Higher temperature for more variety
                max_tokens=150
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            print(f"Error calling OpenAI API: {e}")
            raise

    def _call_anthropic(self, prompt: str) -> str:
        """Call Anthropic API to generate request."""
        if self.client is None:
            raise RuntimeError("Anthropic client not initialized")

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=150,
                temperature=0.9,
                system=self.system_prompt,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            return response.content[0].text.strip()

        except Exception as e:
            print(f"Error calling Anthropic API: {e}")
            raise

    def generate(self, trip_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Generate a natural language request using LLM.

        Args:
            trip_data: Dictionary with trip information

        Returns:
            Dictionary with 'request' and 'generation_method' keys
        """
        if self.client is None:
            raise RuntimeError(f"LLM client for {self.provider} is not available")

        # Format trip information
        prompt = self._format_trip_info(trip_data)

        # Call appropriate API
        if self.provider == "openai":
            request_text = self._call_openai(prompt)
        elif self.provider == "anthropic":
            request_text = self._call_anthropic(prompt)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

        return {
            'request': request_text,
            'generation_method': f'llm_{self.provider}',
            'model': self.model
        }

    def generate_batch(
        self,
        trip_data_list: List[Dict[str, Any]],
        rate_limit_delay: float = 0.5
    ) -> List[Dict[str, str]]:
        """
        Generate multiple requests with rate limiting.

        Args:
            trip_data_list: List of trip data dictionaries
            rate_limit_delay: Delay between API calls in seconds

        Returns:
            List of generated request dictionaries
        """
        import time

        results = []
        for i, trip_data in enumerate(trip_data_list):
            try:
                result = self.generate(trip_data)
                results.append(result)

                if (i + 1) % 10 == 0:
                    print(f"Generated {i + 1} / {len(trip_data_list)} requests...")

                # Rate limiting
                time.sleep(rate_limit_delay)

            except Exception as e:
                print(f"Error generating request {i}: {e}")
                # Add a fallback empty result
                results.append({
                    'request': f"Error: {str(e)}",
                    'generation_method': 'error',
                    'model': self.model
                })

        return results


def main():
    """Example usage of LLM generator."""
    from datetime import datetime

    # Example trip data
    trip_data = {
        'pickup_zone': 'Upper East Side',
        'dropoff_zone': 'JFK Airport',
        'pickup_poi': 'Central Park',
        'dropoff_poi': 'JFK',
        'pickup_personal': 'home',
        'request_time': datetime(2025, 1, 15, 14, 30),
        'estimated_duration_minutes': 45,
        'passenger_count': 2,
        'wav_request_flag': 'N',
        'shared_request_flag': 'N'
    }

    print("LLM-based Natural Language Request Examples:\n")

    # Try OpenAI
    try:
        print("--- Using OpenAI GPT ---")
        openai_generator = LLMGenerator(provider="openai")

        for i in range(3):
            result = openai_generator.generate(trip_data)
            print(f"\nExample {i+1}: {result['request']}")

    except Exception as e:
        print(f"OpenAI generation failed: {e}")
        print("Make sure OPENAI_API_KEY is set in environment")

    print("\n" + "="*80 + "\n")

    # Try Anthropic
    try:
        print("--- Using Anthropic Claude ---")
        anthropic_generator = LLMGenerator(provider="anthropic")

        for i in range(3):
            result = anthropic_generator.generate(trip_data)
            print(f"\nExample {i+1}: {result['request']}")

    except Exception as e:
        print(f"Anthropic generation failed: {e}")
        print("Make sure ANTHROPIC_API_KEY is set in environment")


if __name__ == "__main__":
    main()

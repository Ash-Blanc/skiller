"""
Centralized LLM model factory for Skiller.
Supports Pollinations.ai as a custom OpenAI-compatible provider and Mistral as a fallback.
"""

import os
from typing import Optional
from agno.models.openai import OpenAIChat
from agno.models.mistral import MistralChat


def get_llm_model(model_id: Optional[str] = None):
    """
    Returns an Agno Model instance based on environment configuration.
    
    If USE_POLLINATIONS is true (default), returns an OpenAIChat instance 
    configured for the Pollinations.ai API.
    Otherwise, falls back to MistralChat.
    """
    use_pollinations = os.getenv("USE_POLLINATIONS", "true").lower() == "true"
    
    if use_pollinations:
        # Pollinations.ai is OpenAI-compatible
        # Endpoint: https://text.pollinations.ai/openai
        api_key = os.getenv("POLLINATIONS_API_KEY", "dummy")
        # Default to 'openai' which is gpt-4o-mini on Pollinations
        model = model_id or os.getenv("POLLINATIONS_MODEL", "openai")
        
        # Pollinations supports models like: openai, mistral, p1, etc.
        # See https://pollinations.ai/ for available models
        return OpenAIChat(
            id=model,
            api_key=api_key,
            base_url="https://text.pollinations.ai/openai"
        )
    else:
        # Fallback to Mistral
        model = model_id or os.getenv("MISTRAL_MODEL", "mistral-large-latest")
        return MistralChat(id=model)

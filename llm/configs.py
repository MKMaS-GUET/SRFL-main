from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic
from typing import Dict, Any

ENGINE_CONFIGS: Dict[str, Dict[str, Any]] = {
    "gemini-1.5-pro": {
        "constructor": ChatOpenAI,
        "params": {"model": "gemini-1.5-pro", "temperature": 0}
    },
    "gpt-3.5-turbo": {
        "constructor": ChatOpenAI,
        "params": {"model": "gpt-3.5-turbo", "temperature": 0}
    },
    "gpt-4o-mini": {
        "constructor": ChatOpenAI,
        "params": {"model": "gpt-4o-mini", "temperature": 0}
    },
    "gpt-4-turbo": {
        "constructor": ChatOpenAI,
        "params": {"model": "gpt-4-turbo", "temperature": 0}
    },
    "claude-3-opus-20240229": {
        "constructor": ChatOpenAI,
        "params": {"model": "claude-3-opus-20240229", "temperature": 0}
    },
    "gemini-2.0-flash": {
        "constructor": ChatOpenAI,
        "params": {"model": "gemini-2.0-flash", "temperature": 0}
    },
    "gemini-2.5-pro": {
        "constructor": ChatOpenAI,
        "params": {"model": "gemini-2.5-pro", "temperature": 0}
    }
}

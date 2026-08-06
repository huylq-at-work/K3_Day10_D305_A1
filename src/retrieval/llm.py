from __future__ import annotations

from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from core.config import Settings, resolve_llm

_warned: set[str] = set()


def build_llm(settings: Settings, temperature: float = 0.0):
    provider, model, fallback_reason = resolve_llm(settings)
    if fallback_reason and fallback_reason not in _warned:
        # In mot lan cho moi ly do - build_llm bi goi lai cho tung cau hoi khi cham diem.
        _warned.add(fallback_reason)
        print(f"[llm] CANH BAO: {fallback_reason}")

    if provider == "gemini":
        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=settings.google_api_key,
            temperature=temperature,
        )
    if provider == "openai":
        return ChatOpenAI(
            model=model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            temperature=temperature,
        )
    if provider == "anthropic":
        return ChatAnthropic(
            model=model,
            api_key=settings.anthropic_api_key,
            temperature=temperature,
        )
    if provider == "openrouter":
        return ChatOpenAI(
            model=model,
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            temperature=temperature,
        )
    if provider == "ollama":
        return ChatOllama(
            model=model,
            base_url=settings.ollama_base_url,
            temperature=temperature,
        )
    if provider == "custom":
        return ChatOpenAI(
            model=model,
            api_key=settings.custom_llm_api_key or "unused",
            base_url=settings.custom_llm_base_url,
            temperature=temperature,
        )
    raise RuntimeError(f"Unsupported LLM provider: {settings.llm_provider}")

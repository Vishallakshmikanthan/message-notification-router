"""Unit tests for Phase 8 Prompt System."""

import pytest
from router.application.prompts.context_compressor import ContextCompressor
from router.application.prompts.prompt_cache import PromptCache
from router.application.prompts.prompt_loader import PromptLoader
from router.application.prompts.prompt_manager import PromptManager
from router.application.prompts.prompt_version import PromptVersion
from router.application.prompts.token_optimizer import TokenOptimizer


def test_prompt_version():
    pv = PromptVersion.from_string("system_prompt", "system", "1.0.0")
    assert pv.major == 1
    assert pv.minor == 0
    assert pv.patch == 0
    assert pv.full_id == "system_prompt@1.0.0"


def test_prompt_loader():
    loader = PromptLoader()
    template = loader.load("system_prompt", 1)
    assert template.version.prompt_id == "system_prompt"
    assert template.version.version_string == "1.0.0"
    assert "ROUTING ACTIONS" in template.raw_content


def test_prompt_cache():
    cache = PromptCache()
    prompt = "System prompt text"
    hit, fp = cache.check("test_provider", prompt)
    assert not hit

    cache.store("test_provider", prompt, "system_prompt", "1.0.0")
    hit_again, fp2 = cache.check("test_provider", prompt)
    assert hit_again
    assert fp == fp2


def test_token_optimizer():
    optimizer = TokenOptimizer()
    signals = {
        "urgency_score": 0.85,
        "spam_score": 0.02,
        "is_quiet_hours": True,
        "sender_is_vip": False,
    }
    encoded = optimizer.encode_signals(signals)
    assert "urgency:0.85" in encoded
    assert "spam:0.02" in encoded
    assert "dnd:true" in encoded


def test_context_compressor():
    compressor = ContextCompressor()
    compressed = compressor.compress(
        system_text="System prompt",
        message_text="Hello, this is a test message.",
        signal_dict={"urgency_score": 0.9},
        rag_snippets=["Snippet 1", "Snippet 2"],
    )
    assert "System prompt" in compressed.system_text
    assert "user_message_content" in compressed.message_text


def test_prompt_manager():
    manager = PromptManager()
    built = manager.build_classification(
        message_text="Urgent meeting change!",
        signal_dict={"urgency_score": 0.95, "sender_is_vip": True},
    )
    assert built.system_prompt != ""
    assert built.user_prompt != ""
    assert built.estimated_tokens > 0

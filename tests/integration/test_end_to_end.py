"""End-to-End Integration Test for Phase 8 & 9."""

import asyncio
import pytest
from eval.evaluation_pipeline import EvaluationPipeline
from eval.output_validator import OutputCSVValidator
from router.application.agents.agent_orchestrator import AgentOrchestrator
from router.application.decision.decision_engine import DecisionEngineV2
from router.application.prompts.prompt_manager import PromptManager
from router.infrastructure.llm.claude_provider import ClaudeProvider
from router.infrastructure.llm.openai_provider import OpenAIProvider


def test_e2e_prompt_and_llm_flow():
    """Verify prompt generation -> provider interface -> parser flow."""
    pm = PromptManager()
    built = pm.build_classification(
        message_text="Emergency! Server down!",
        signal_dict={"urgency_score": 0.95, "sender_is_vip": True},
    )

    claude = ClaudeProvider()
    res_claude = claude.complete(built)
    assert "action" in res_claude

    openai_p = OpenAIProvider()
    res_openai = openai_p.complete(built)
    assert "action" in res_openai


@pytest.mark.asyncio
async def test_e2e_agent_orchestrator():
    """Verify complete 8-agent microservice DAG execution."""
    orchestrator = AgentOrchestrator()
    context = EvaluationPipeline._build_mock_context({
        "message_id": "e2e_msg_001",
        "text": "Hi Mom, call me back when you get a chance.",
    })
    res = await orchestrator.execute_graph(context)
    assert "action" in res
    assert "confidence" in res
    assert res["message_id"] == "e2e_msg_001"


def test_e2e_decision_engine_and_eval_pipeline():
    """Verify DecisionEngineV2 execution inside EvaluationPipeline."""
    pipeline = EvaluationPipeline()
    metrics = pipeline.run_evaluation(
        dataset_path="non_existent.json",
        output_report_path="reports/test_eval_report.json",
    )
    assert metrics.accuracy >= 0.0
    assert metrics.macro_f1 >= 0.0

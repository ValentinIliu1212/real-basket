"""Minimal CLI to test the agent without the UI: `poetry run real-basket-cli "your question"`."""

import sys

from real_basket.agents.guardrail import unverified_figures, warning_text
from real_basket.core import llm


def main() -> None:
    prompt = " ".join(sys.argv[1:]) or "Steigen die Grundlebenshaltungskosten schneller als die Inflation?"
    issues = llm.config_issues()
    for warning in issues["warnings"]:
        print(f"Warning: {warning}", file=sys.stderr)
    if issues["errors"]:
        raise SystemExit("LLM provider not configured: " + " ".join(issues["errors"]) + " See .env.example.")

    from real_basket.agents.orchestrator import create_orchestrator

    agent = create_orchestrator()
    try:
        answer = str(agent(prompt))
        print(answer)
        note = warning_text(unverified_figures(answer, agent.messages, prompt))
        if note:
            print(f"\n{note}", file=sys.stderr)
    finally:
        agent.cleanup()        # stop the MCP server subprocess


if __name__ == "__main__":
    main()

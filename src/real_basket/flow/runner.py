"""CLI for the non-deterministic monitoring flow.

    poetry run real-basket-flow --trigger schedule
    poetry run real-basket-flow --trigger question --goal "Why is rent rising faster than the CPI?"
    poetry run real-basket-flow --trigger price_alert --goal "Fuel prices jumped" --approve interactive
"""

from __future__ import annotations

import argparse
import sys

from real_basket.flow.graph import auto_approver, cli_approver, deferred_approver, run_flow
from real_basket.schemas.flow import Trigger

DEFAULT_GOALS = {
    Trigger.SCHEDULE: "Monthly monitoring: essential living cost inflation vs official CPI.",
    Trigger.QUESTION: "Are essential living costs rising faster than official inflation, and why?",
    Trigger.PRICE_ALERT: "A price alert was raised: check whether essential inflation deviates from the CPI.",
}
APPROVERS = {"deferred": deferred_approver, "auto": auto_approver, "interactive": cli_approver}


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):  # Windows consoles: allow €, Ø, emojis
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description="Run one RealBasket monitoring flow.")
    p.add_argument("--trigger", choices=[t.value for t in Trigger], default=Trigger.SCHEDULE.value)
    p.add_argument("--goal", default="")
    p.add_argument("--approve", choices=list(APPROVERS), default="deferred",
                   help="human-in-the-loop: deferred (decide later in the UI), auto (demo) or interactive")
    args = p.parse_args(argv)

    trigger = Trigger(args.trigger)
    ctx = run_flow(args.goal or DEFAULT_GOALS[trigger], trigger=trigger, approver=APPROVERS[args.approve])

    print(f"\nRun {ctx.run_id}: {ctx.run_status.value} (confidence {ctx.confidence})")
    print("Path: " + " -> ".join(ctx.path))
    for d, s in ctx.status.items():
        print(f"  {d:<9} {s.value:<9} attempts={ctx.attempts.get(d, 0)} sources={ctx.tried_sources.get(d, [])}")
    if ctx.report:
        print("\n" + ctx.report.get("final_markdown", ""))
    if ctx.published_files:
        print("\nPublished: " + ", ".join(ctx.published_files))
    print(f"\nAudit trail: {ctx.store.run_dir(ctx.run_id) / 'audit.jsonl'}")
    return 0 if ctx.run_status.value in ("published", "pending_approval") else 1


if __name__ == "__main__":
    raise SystemExit(main())

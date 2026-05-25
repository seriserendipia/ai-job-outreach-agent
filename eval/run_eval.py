"""Eval: does the self-reflection loop actually improve email quality?

Runs the graph twice on the same inputs — once with the reflection loop disabled
(MAX_REVISIONS=0, writer fires once) and once enabled (MAX_REVISIONS=2) — and
prints the Critic's rubric scores for each. The whole point of the Writer<->Critic
loop is that the "ON" run should score at least as well as the "OFF" run.

Requires OPENAI_API_KEY and TAVILY_API_KEY (a full graph run includes the
recruiter search step).

    cd eval && python run_eval.py
"""
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import config  # noqa: E402
from app.graph.graph import build_graph  # noqa: E402

SAMPLES = Path(__file__).parent / "samples"


def run_once(resume: str, page: str, max_revisions: int) -> dict:
    """Build a fresh graph with the given revision budget and run it end to end."""
    config.MAX_REVISIONS = max_revisions
    graph = build_graph()
    return graph.invoke(
        {"resume_text": resume, "page_text": page, "user_message": ""},
        config={"configurable": {"thread_id": uuid.uuid4().hex}},
    )


def report(tag: str, state: dict) -> None:
    critique = state.get("critique")
    print(f"\n=== {tag} ===")
    print(f"revisions performed : {state.get('revision_count', 0)}")
    if critique is None:
        print("(no critique produced)")
        return
    print(f"specificity         : {critique.specificity}/5")
    print(f"tone                : {critique.tone}/5")
    print(f"no placeholders     : {critique.no_placeholders}")
    print(f"length ok           : {critique.length_ok}")
    print(f"no hallucination    : {critique.no_hallucination}")
    print(f"passed              : {critique.passed}")


def main() -> None:
    resume = (SAMPLES / "resume.txt").read_text(encoding="utf-8")
    page = (SAMPLES / "job_posting.txt").read_text(encoding="utf-8")

    print("Running graph WITHOUT the reflection loop (MAX_REVISIONS=0)…")
    off_state = run_once(resume, page, 0)

    print("Running graph WITH the reflection loop (MAX_REVISIONS=2)…")
    on_state = run_once(resume, page, 2)

    report("reflection OFF", off_state)
    report("reflection ON", on_state)


if __name__ == "__main__":
    main()

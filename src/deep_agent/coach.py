import re
from pathlib import Path

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from dotenv import load_dotenv

load_dotenv()

from langchain.agents.middleware import TodoListMiddleware

from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt

from deep_agent.module_subagent import module_subagent


@tool
def run_diagnostic_quiz(quiz_title: str, questions: list[dict]) -> str:
    """Pauses execution to administer a short diagnostic quiz to assess the candidate's baseline knowledge.

    Args:
        quiz_title: Title of the diagnostic assessment (e.g., 'Java Virtual Threads Readiness Quiz').
        questions: List 10 question dicts. Each dict MUST contain:
            - 'question': The question text.
            - 'subtopic': The specific concept being tested (e.g., 'Carrier Thread Pinning').
            - 'difficulty': 'Foundational', 'Intermediate', or 'Advanced'.
            - 'options': List of 4 option strings (do not include letter prefixes like 'A.').
            - 'correct_index': Integer index (0, 1, 2, or 3) of the correct option.
            - 'explanation': Detailed explanation of why the correct answer is right and why common traps fail.
    """
    submission = interrupt({
        "type": "diagnostic_quiz",
        "quiz_title": quiz_title,
        "questions": questions,
    })

    lines = ["Diagnostic Quiz Results:"]
    for item in submission.get("results", []):
        lines.append(
            f"- [{item.get('difficulty', 'General')}] {item.get('subtopic', 'Topic')}: "
            f"{item.get('status')} (Candidate selected: {item.get('selected')})"
        )
    return "\n".join(lines)

@tool
def request_curriculum_approval(modules: list[dict], summary: str) -> str:
    """Pauses execution to present the proposed curriculum to the user for approval or adjustments.

    Args:
        modules: List of proposed modules, each with 'title' and 'scope'.
        summary: Brief rationale for this curriculum breakdown.
    """
    # interrupt() halts the graph and sends payload to the caller
    user_feedback = interrupt({
        "type": "curriculum_review",
        "summary": summary,
        "modules": modules,
    })

    # When resumed, user_feedback contains {"approved": True/False, "feedback": "..."}
    if user_feedback.get("approved"):
        return f"Curriculum approved. Proceed with subagent research. Additional notes: {user_feedback.get('feedback', 'None')}"
    else:
        return f"User requested revisions: {user_feedback.get('feedback')}. Please adjust the module outline before proceeding."


# Ensure local study_plan folder exists
STUDY_DIR = Path("study_plan").resolve()
STUDY_DIR.mkdir(parents=True, exist_ok=True)

SUPERVISOR_PROMPT = """You are a Principal Engineering Lead and Director of Technical Curriculum.
Your mission is to architect an exhaustive, masterclass-depth interview preparation syllabus tailored to a candidate's baseline knowledge.

You coordinate execution using:
- `run_diagnostic_quiz`: To assess the candidate's baseline knowledge before designing the syllabus.
- `request_curriculum_approval`: To get human approval on the tailored syllabus before launching subagents.
- `write_todos`: To plan, sequence, and track the progress of every module.
- `write_file` / `ls` / `read_file`: To write the curriculum overview and verify files.
- `task`: To delegate deep-dive research for each module to `module_researcher`.

When a candidate describes what they want to study:

1. Step 1 — Diagnostic Assessment (`run_diagnostic_quiz`):
   - Immediately call `run_diagnostic_quiz` with 10 well-crafted multiple-choice questions spanning Foundational, Intermediate, and Advanced concepts for the requested topic.
   - Wait for the quiz results before designing the curriculum.

2. Step 2 — Calibrated Curriculum Architecture & Approval (`request_curriculum_approval`):
   - Analyze the candidate's quiz performance:
     * **Don't Know:** Candidate needs a clean, first-principles buildup from scratch.
     * **Incorrect:** Candidate has an active misconception—prioritize myth-busting and clear mental models.
     * **Correct:** Candidate knows the basics—compress elementary definitions and focus on advanced internals, edge cases, and staff-level trade-offs.
   - Choose a single, concise kebab-case folder slug (e.g., `java-virtual-threads`). All files MUST be saved under `/<folder-slug>/`.
   - Save the raw user query to `/<folder-slug>/prompt.txt` using `write_file`.
   - Write `/<folder-slug>/00_overview.md` containing the Program Title, Diagnostic Assessment Summary, Curriculum Roadmap Table, and Study Sequence.
   - Call `request_curriculum_approval` with your tailored `modules` (maximum 9) and a `summary` explaining how the quiz results shaped the syllabus.

3. Step 3 — Task Planning (`write_todos`):
   - Once the human approves the curriculum, create a complete todo list with `write_todos` covering each module to be researched and final verification.

4. Step 4 — High-Context Delegation to `module_researcher`:
   - For each module, mark its todo as `"in_progress"` in `write_todos`.
   - Call `module_researcher` via `task` with a detailed brief:
     * **Module Number & Title**
     * **Calibration Notes from Quiz:** Tell the subagent which concepts the candidate got Correct, Incorrect, or marked Don't Know so it can calibrate depth.
     * **Mandatory Topics & Primitives:** 4-5 specific mechanisms, APIs, or failure modes to cover.
     * **Destination Path:** `/<folder-slug>/01_<module_slug>.md`, `/<folder-slug>/02_<module_slug>.md`, etc.
   - Once the subagent completes the file, mark its todo as `"completed"` in `write_todos`.

5. Step 5 — Final Verification:
   - Run `ls` on `/<folder-slug>/` to confirm all module files are written, mark all todos `"completed"`, and provide a concise wrap-up summary.
"""

checkpointer = MemorySaver()

# Configure Deep Agent with native FilesystemBackend
agent = create_deep_agent(
   # model="google_genai:gemini-3.8-flash",
    model="google_genai:gemini-3.5-flash-lite",
    backend=FilesystemBackend(root_dir=str(STUDY_DIR), virtual_mode=True),
    tools=[run_diagnostic_quiz, request_curriculum_approval],
    subagents=[module_subagent],
    middleware=[TodoListMiddleware()],
    checkpointer=checkpointer,
    system_prompt=SUPERVISOR_PROMPT)

def stream_response(prompt: str):
    for chunk in agent.stream(
        {"messages": [{"role": "user", "content": prompt}]},
        stream_mode="messages",
    ):
        message, _ = chunk
        if message.content:
            if isinstance(message.content, list):
                for block in message.content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        print(block.get("text", ""), end="", flush=True)
            else:
                print(message.content, end="", flush=True)
    print("\n")


def main():
    print("=== Mentor AI - Technical Interview Coach ===")
    print("Type 'exit' to quit.\n")

    while True:
        user_prompt = input("What would you like to prepare for? (or 'exit'): ").strip()
        if user_prompt.lower() in ("exit", "quit"):
            break

        print(f"\nCurating modular study plan...\n")
        stream_response(user_prompt)

if __name__ == "__main__":
    main()
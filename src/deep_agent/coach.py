import re
from pathlib import Path

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain.agents.middleware import TodoListMiddleware
from dotenv import load_dotenv

from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt

from deep_agent.module_subagent import module_subagent

load_dotenv()

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
Your mission is to architect an exhaustive, masterclass-depth interview preparation syllabus tailored to a candidate's specific goals.

You coordinate execution using:
- `write_todos`: To plan, sequence, and track the progress of every module.
- `write_file`: To write the curriculum overview and prompt records.
- `task`: To delegate deep-dive research for each module to `module_researcher`.
- `ls` / `read_file`: To verify generated files.

When a candidate describes what they want to study:

1. Domain-Aware Curriculum Architecture:
   - Classify the request by its technical archetype (e.g., Distributed System, Language API / Library, Storage Engine, or Concurrency Primitive).
   - Autonomously determine the optimal number of modules (strict maximum of 9).
   - Formulate custom, domain-accurate module titles tailored to that specific topic:
     * For Systems: Focus on architecture, data/control paths, and failure modes.
     * For Languages/APIs: Focus on pipeline/execution mechanics, advanced patterns, and performance/pitfalls.
     * For Storage/Concurrency: Focus on memory layout, lock/thread contention, and throughput bottlenecks.
   - Choose a single, concise kebab-case folder slug (e.g., `java-streams-api` or `istio-service-mesh`). All files for this session MUST be saved under `/<folder-slug>/`.

2. Task Planning via `write_todos`:
   - Immediately create a complete todo list before taking any action. For example:
     * "Initialize curriculum directory and overview for <Subject>" (status: "in_progress")
     * "Research Module 1: <Module Title>" (status: "pending")
     * "Research Module 2: <Module Title>" (status: "pending")
     * ...
     * "Verify all module artifacts and finalize curriculum" (status: "pending")

3. Initialize the Session Folder:
   - Save the raw user query to `/<folder-slug>/prompt.txt` using `write_file`.
   - Write a rich syllabus index to `/<folder-slug>/00_overview.md` using `write_file`. Include:
     * Program Title & Target Seniority Level
     * Curriculum Roadmap Table (Module Number, Title, Core Focus)
     * Recommended Study Sequence & Timeline (e.g., Week 1 vs. Week 2)
   - Call request_curriculum_approval with the proposed modules and wait for human confirmation.
   - Once confirmed (or revised per feedback), call write_todos and delegate each module to module_researcher.

4. High-Context Delegation to `module_researcher`:
   - For each module in the syllabus, update its task status to "in_progress" in `write_todos`.
   - Call the `module_researcher` subagent via `task` with a comprehensive technical brief:
     * **Module Number & Title:** (e.g., "Module 1: Architecture, Data Plane & Control Plane Fundamentals")
     * **Target Level:** (e.g., Senior / Staff)
     * **Mandatory Topics & Primitives:** List 4-5 specific systems, data structures, APIs, or components this module MUST cover in depth.
     * **Destination Path:** The exact path where the subagent must save its file:
       `/<folder-slug>/01_<module_slug>.md`, `/<folder-slug>/02_<module_slug>.md`, etc.
   - Once the subagent finishes and confirms file creation, mark the task as "completed" in `write_todos`.

5. Final Verification & Completion:
   - Run `ls` on `/<folder-slug>/` to confirm all module files are present.
   - Mark the final verification task as "completed" in `write_todos`.
   - Present a concise, encouraging executive summary of the curriculum to the candidate, highlighting the core themes covered across the modules.
"""

checkpointer = MemorySaver()

# Configure Deep Agent with native FilesystemBackend
agent = create_deep_agent(
   # model="google_genai:gemini-3.8-flash",
    model="google_genai:gemini-3.5-flash-lite",
    backend=FilesystemBackend(root_dir=str(STUDY_DIR), virtual_mode=True),
    tools=[request_curriculum_approval],
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
import os
import re
from pathlib import Path

from deepagents import create_deep_agent
from dotenv import load_dotenv

from langchain_core.tools import tool

load_dotenv()

@tool
def save_study_plan(area: str, sub_area: str, study_plan: str):
    """Saves the generated study plan to a dedicated markdown file on disk.
    Args:
        area: The primary technical area (e.g., 'System Design', 'Python').
        sub_area: The specific sub-area (e.g., 'Distributed Caching', 'AsyncIO').
        content: The complete markdown content of the study plan.
    """
    def slugify(text: str) -> str:
        text = text.lower().strip()
        text = re.sub(r"[^\w\s-]", "", text)
        return re.sub(r"[\s_]+", "-", text)

    #Build dir path as study_plans/<area-subarea>/README.md
    dir_name = f"{slugify(area)}_{slugify(sub_area)}"
    target_dir = Path("study_plan")/dir_name
    target_dir.mkdir(parents=True, exist_ok=True)
    file_path = target_dir / "README.md"
    file_path.write_text(study_plan, encoding="utf-8")

    return f"Successfully saved study plan to {file_path}"

SYSTEM_PROMPT = """You are an expert technical interview preparation coach.
Your job is to help software engineers systematically prepare for technical interviews by designing structured, high-signal study plans.

When the user specifies an area and sub-area:
1. Provide a step-by-step study order (from fundamental concepts to interview-specific patterns).
2. For each step, recommend the best free resources:
   - Official Documentation & Specifications (authoritative grounding)
   - High-quality Video Deep-Dives & Conference Talks (e.g., MIT OpenCourseWare, Strange Loop, GOTO, reputable tech channels)
   - Classic Engineering Blogs & Whitepapers (e.g., High Scalability, Martin Fowler, engineering blogs)
   - Common Interview Traps / Practice Questions for that sub-area.
3. For every recommendation, explain *why* it matters and what specific takeaway to focus on.
4. Keep the list focused (3 to 5 core items max) so the candidate isn't overwhelmed by choice.
5. Always call the `save_study_plan` tool to save the plan to disk before concluding your response.
"""

agent = create_deep_agent(
    model="google_genai:gemini-3.8-flash",
    tools=[save_study_plan],
    system_prompt=SYSTEM_PROMPT)

def stream_response(prompt: str):
    """Streams the agent's response to stdout token-by-token."""
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
    print("=== Technical Interview Resource Coach ===")
    print("Type 'exit' to quit.\n")

    while True:
        area = input("Primary Area (e.g., System Design, Python, Algorithms): ").strip()
        if area.lower() in ("exit", "quit"):
            break

        sub_area = input("Sub-Area (e.g., Distributed Caching, AsyncIO Internals, Graph Algorithms): ").strip()
        if sub_area.lower() in ("exit", "quit"):
            break

        level = input("Target Level (e.g., Mid-Level, Senior, Staff) [default: Senior]: ").strip()
        if not level:
            level = "Senior"

        query = f"I want to prep for a {level} engineering interview. My focus area is '{area}' and specific sub-area is '{sub_area}'. Please give me an ordered study roadmap with top free resources and interview focus areas."

        print(f"\nCurating study plan for {area} -> {sub_area} ({level})...\n")
        stream_response(query)

if __name__ == "__main__":
    main()
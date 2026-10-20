import re
from pathlib import Path

from deepagents import create_deep_agent
from dotenv import load_dotenv

from langchain_core.tools import tool
from deep_agent.module_subagent import module_subagent

load_dotenv()

@tool
def save_study_plan(title: str, study_plan: str):
    """Saves the generated study plan to a dedicated markdown file on disk.
    Args:
        title: A concise, human-readable 3 to 5 word title summarizing the topic (e.g., 'Redis Rate Limiting', 'JVM Garbage Collection Tuning').
        study_plan: The complete markdown content of the plan.
    """
    def slugify(text: str) -> str:
        text = text.lower().strip()
        text = re.sub(r"[^\w\s-]", "", text)
        return re.sub(r"[\s_]+", "-", text)

    #Build dir path as study_plans/<area-subarea>/README.md
    dir_name = f"{slugify(title)}"
    target_dir = Path("study_plan")/dir_name
    target_dir.mkdir(parents=True, exist_ok=True)

    # Save a small metadata file or ensure the README starts with the title
    file_path = target_dir / "README.md"
    # If the LLM didn't already include the title as an H1, prepend it
    content = study_plan if study_plan.startswith("# ") else f"# {title}\n\n{study_plan}"
    file_path.write_text(content, encoding="utf-8")
    return f"Successfully saved study plan to {file_path}"

SUPERVISOR_PROMPT = """You are a lead technical interview curriculum architect.
Your job is to design comprehensive, modular technical interview preparation programs.

When a candidate describes what they want to study:

1. Analyze & Deconstruct:
   - Identify the core domain, specific technologies, and the candidate's target seniority level (default to Senior if not specified).
   - Break the subject down into 2 to 3 progressive learning modules (e.g., Module 1: Architectural Foundations, Module 2: System Internals & Trade-offs, Module 3: Production Pitfalls & Interview Scenarios).

2. Delegate Research to Subagent:
   - For each module in the syllabus, invoke the `module_researcher` subagent using the `task` tool.
   - In each task prompt, specify:
     * The module title and core focus
     * The target seniority level
     * Specific sub-topics or concepts this module must cover

3. Assemble the Master Study Plan:
   - Generate a concise 3 to 5 word title for the entire roadmap (e.g., 'Redis Rate Limiting Architecture').
   - Combine the returned reports from each subagent into a single cohesive Markdown study guide.
   - Include a high-level syllabus overview and recommended study schedule at the top.

4. Save and Conclude:
   - Always call the `save_study_plan` tool with the generated title and the full assembled Markdown document.
   - Present a concise summary of the module breakdown to the user and confirm that the plan has been saved to disk.
"""

# SYSTEM_PROMPT = """You are an expert technical interview preparation coach.
# Your job is to help software engineers systematically prepare for technical interviews by designing structured, high-signal study plans.
#
# Based on the user prompt:
# 1. Provide a step-by-step study order (from fundamental concepts to interview-specific patterns).
# 2. For each step, recommend the best free resources:
#    - Official Documentation & Specifications (authoritative grounding)
#    - High-quality Video Deep-Dives & Conference Talks (e.g., MIT OpenCourseWare, Strange Loop, GOTO, reputable tech channels)
#    - Classic Engineering Blogs & Whitepapers (e.g., High Scalability, Martin Fowler, engineering blogs)
#    - Common Interview Traps / Practice Questions for that sub-area.
# 3. For every recommendation, explain *why* it matters and what specific takeaway to focus on.
# 4. Keep the list focused (3 to 5 core items max) so the candidate isn't overwhelmed by choice.
# 5. Generate a concise, professional 3 to 5 word title for the session.
# 6. Always call the `save_study_plan` tool with your generated title and the complete study plan.
# """

# SYSTEM_PROMPT = """You are an expert technical interview coach. Design structured, high-signal study plans for a given area/sub-area.
#
# Requirements:
# 1. Provide a step-by-step study order (fundamentals to interview patterns).
# 2. Recommend 3-5 core free resources across: Official Docs, Video Deep-Dives, Engineering Blogs/Whitepapers, and Interview Traps.
# 3. For each resource, provide a brief 1-sentence takeaway/focus.
# 4. Generate a 3-5 word professional title.
# 5. Critical: Always invoke `save_study_plan` using the generated title and complete study plan. Do not summarize or chat before calling the tool.
# """

agent = create_deep_agent(
   # model="google_genai:gemini-3.8-flash",
    model="google_genai:gemini-3.5-flash-lite",
    tools=[save_study_plan],
    subagents=[module_subagent],
    system_prompt=SUPERVISOR_PROMPT)

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
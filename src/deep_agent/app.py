import uuid
from pathlib import Path
import streamlit as st
from langgraph.types import Command
from deep_agent.coach import agent

st.set_page_config(page_title="Mentor AI", layout="wide")

STUDY_DIR = Path("study_plan")
STUDY_DIR.mkdir(parents=True, exist_ok=True)

def get_existing_plans():
    plans = {}
    for topic_folder in sorted(STUDY_DIR.iterdir()):
        if not topic_folder.is_dir():
            continue

        md_files = sorted(topic_folder.glob("*.md"))
        if not md_files:
            continue

        prompt_file = topic_folder / "prompt.txt"
        user_prompt = prompt_file.read_text(encoding="utf-8") if prompt_file.exists() else None

        overview_file = topic_folder / "00_overview.md"
        first_file = overview_file if overview_file.exists() else md_files[0]
        first_line = first_file.read_text(encoding="utf-8").splitlines()[0] if first_file.exists() else ""
        title = first_line.lstrip("# ").strip() if first_line.startswith("# ") else topic_folder.name.replace("-", " ").title()

        modules = {
            f.stem.replace("_", " ").title(): f.read_text(encoding="utf-8")
            for f in md_files
        }

        plans[topic_folder.name] = {
            "title": title,
            "user_prompt": user_prompt,
            "modules": modules,
        }
    return plans

# ----------------- Initialize Session State -----------------
if "chats" not in st.session_state:
    st.session_state.chats = get_existing_plans()

if "active_chat" not in st.session_state:
    st.session_state.active_chat = None

if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

if "pending_interrupt" not in st.session_state:
    st.session_state.pending_interrupt = None

if "current_prompt" not in st.session_state:
    st.session_state.current_prompt = None

# ----------------- Helper: Stream & Catch Interrupts -----------------
def run_agent_stream(stream_input):
    """Runs or resumes the agent stream, updating todos and catching HITL interrupts."""
    config = {"configurable": {"thread_id": st.session_state.thread_id}}
    pending_interrupt = None

    with st.status("🎯 Architecting and researching study plan...", expanded=True) as status_box:
        todo_placeholder = st.empty()

        for mode, data in agent.stream(
            stream_input,
            stream_mode=["values", "updates"],
            config=config,
        ):
            # 1. Update live Todo checklist from state values
            if mode == "values" and isinstance(data, dict):
                todos = data.get("todos", [])
                if todos:
                    todo_lines = []
                    for item in todos:
                        status = item.get("status")
                        content = item.get("content")
                        if status == "completed":
                            todo_lines.append(f"- ✅ ~~{content}~~")
                        elif status == "in_progress":
                            todo_lines.append(f"- ⏳ **{content}**")
                        else:
                            todo_lines.append(f"- ⚪ {content}")
                    todo_placeholder.markdown("\n".join(todo_lines))

            # 2. Catch Human-in-the-Loop interrupt event
            elif mode == "updates" and isinstance(data, dict):
                if "__interrupt__" in data:
                    pending_interrupt = data["__interrupt__"][0].value

        if pending_interrupt:
            status_box.update(label="⏸️ Paused for curriculum review", state="running", expanded=False)
        else:
            status_box.update(label="✅ Study plan complete!", state="complete", expanded=False)

    # Transition state based on whether the graph paused or finished
    if pending_interrupt:
        st.session_state.pending_interrupt = pending_interrupt
        st.rerun()
    else:
        st.session_state.pending_interrupt = None
        st.session_state.chats = get_existing_plans()
        folders = [f for f in STUDY_DIR.iterdir() if f.is_dir() and list(f.glob("*.md"))]
        if folders:
            newest = max(folders, key=lambda f: f.stat().st_mtime)
            if st.session_state.current_prompt and not (newest / "prompt.txt").exists():
                (newest / "prompt.txt").write_text(str(st.session_state.current_prompt), encoding="utf-8")
            st.session_state.chats = get_existing_plans()
            st.session_state.active_chat = newest.name
        st.session_state.current_prompt = None
        st.rerun()


# ----------------- Sidebar -----------------
with st.sidebar:
    st.title("Mentor AI")
    if st.button("➕ New Chat", use_container_width=True):
        st.session_state.active_chat = None
        st.session_state.pending_interrupt = None
        st.session_state.current_prompt = None
        st.session_state.thread_id = str(uuid.uuid4())
        st.rerun()

    st.subheader("Your Study Plans")
    for slug, plan_data in st.session_state.chats.items():
        if st.button(plan_data["title"], key=slug, use_container_width=True):
            st.session_state.active_chat = slug
            st.session_state.pending_interrupt = None
            st.rerun()


# ----------------- Main View -----------------
# Case 1: Viewing a completed study plan
if st.session_state.active_chat and st.session_state.active_chat in st.session_state.chats:
    plan = st.session_state.chats[st.session_state.active_chat]
    st.title(f"📖 {plan['title']}")

    if plan.get("user_prompt"):
        with st.chat_message("user"):
            st.markdown(f"**Your Goal:** {plan['user_prompt']}")

    st.divider()

    module_labels = list(plan["modules"].keys())
    if module_labels:
        tabs = st.tabs(module_labels)
        for tab, label in zip(tabs, module_labels):
            with tab:
                st.markdown(plan["modules"][label])

    st.caption("🔒 Read-only mode. Click '+ New Chat' in the sidebar to start another session.")

# Case 2: New Session / Human-in-the-Loop Review
else:
    st.title("🎯 New Interview Study Session")

    # Subcase 2A: Agent is paused waiting for curriculum approval
    if st.session_state.pending_interrupt:
        if st.session_state.current_prompt:
            with st.chat_message("user"):
                st.write(st.session_state.current_prompt)

        review_data = st.session_state.pending_interrupt
        with st.container(border=True):
            st.subheader("📋 Proposed Curriculum Review")
            if review_data.get("summary"):
                st.markdown(review_data["summary"])

            st.markdown("#### Modules to Research:")
            for idx, mod in enumerate(review_data.get("modules", []), start=1):
                if isinstance(mod, dict):
                    mod_title = mod.get("title", f"Module {idx}")
                    mod_scope = mod.get("scope") or mod.get("description", "")
                    st.markdown(f"**{idx}. {mod_title}**  \n{mod_scope}")
                else:
                    st.markdown(f"**{idx}.** {mod}")

            st.divider()
            feedback = st.text_area(
                "Optional adjustments or specific topics to include:",
                placeholder="e.g., Add a deep-dive on EnvoyFilter debugging to Module 2, or combine Modules 1 and 2.",
            )

            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Approve & Start Research", type="primary", use_container_width=True):
                    try:
                        run_agent_stream(
                            Command(resume={"approved": True, "feedback": feedback.strip()})
                        )
                    except Exception as err:
                        st.error(f"Error resuming study plan: {err}")

            with col2:
                if st.button("✏️ Request Revisions", use_container_width=True):
                    if not feedback.strip():
                        st.warning("Please enter your requested changes in the text box above before clicking Request Revisions.")
                    else:
                        try:
                            run_agent_stream(
                                Command(resume={"approved": False, "feedback": feedback.strip()})
                            )
                        except Exception as err:
                            st.error(f"Error revising curriculum: {err}")

    # Subcase 2B: Initial prompt entry
    else:
        st.write("Describe what you want to prepare for. The agent will propose a modular curriculum for your review before generating the full guides.")

        user_prompt = st.chat_input("e.g., Senior backend interview on Istio service mesh and traffic routing")

        if user_prompt:
            st.session_state.thread_id = str(uuid.uuid4())
            st.session_state.current_prompt = str(user_prompt)

            with st.chat_message("user"):
                st.write(user_prompt)

            try:
                run_agent_stream({"messages": [{"role": "user", "content": str(user_prompt)}]})
            except Exception as err:
                st.error(f"Error generating study plan: {err}")

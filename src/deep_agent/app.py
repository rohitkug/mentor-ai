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

# Quiz-specific state
if "quiz_idx" not in st.session_state:
    st.session_state.quiz_idx = 0

if "quiz_answers" not in st.session_state:
    st.session_state.quiz_answers = {}

if "quiz_checked" not in st.session_state:
    st.session_state.quiz_checked = False


def reset_quiz_state():
    st.session_state.quiz_idx = 0
    st.session_state.quiz_answers = {}
    st.session_state.quiz_checked = False


# ----------------- Helper: Stream & Catch Interrupts -----------------
def run_agent_stream(stream_input):
    """Runs or resumes the agent stream, updating todos and catching HITL interrupts."""
    config = {"configurable": {"thread_id": st.session_state.thread_id}}
    pending_interrupt = None

    with st.status("🎯 Working on your study plan...", expanded=True) as status_box:
        todo_placeholder = st.empty()

        for mode, data in agent.stream(
            stream_input,
            stream_mode=["values", "updates"],
            config=config,
        ):
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

            elif mode == "updates" and isinstance(data, dict):
                if "__interrupt__" in data:
                    pending_interrupt = data["__interrupt__"][0].value

        if pending_interrupt:
            int_type = pending_interrupt.get("type", "")
            label = "📝 Ready for diagnostic quiz" if int_type == "diagnostic_quiz" else "⏸️ Paused for curriculum review"
            status_box.update(label=label, state="running", expanded=False)
        else:
            status_box.update(label="✅ Study plan complete!", state="complete", expanded=False)

    if pending_interrupt:
        st.session_state.pending_interrupt = pending_interrupt
        if pending_interrupt.get("type") == "diagnostic_quiz":
            reset_quiz_state()
        st.rerun()
    else:
        st.session_state.pending_interrupt = None
        reset_quiz_state()
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
        reset_quiz_state()
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

# Case 2: Active Session (Quiz, Curriculum Review, or Initial Input)
else:
    st.title("🎯 New Interview Study Session")

    if st.session_state.current_prompt:
        with st.chat_message("user"):
            st.write(st.session_state.current_prompt)

    interrupt_data = st.session_state.pending_interrupt

    # ----------------- Subcase 2A: Diagnostic Quiz UI -----------------
    if interrupt_data and interrupt_data.get("type") == "diagnostic_quiz":
        questions = interrupt_data.get("questions", [])
        total_q = len(questions)
        q_idx = st.session_state.quiz_idx

        with st.container(border=True):
            st.subheader(f"🧠 {interrupt_data.get('quiz_title', 'Diagnostic Readiness Quiz')}")
            st.caption("Let's assess your baseline so we can skip what you already know and focus deeply on your gaps.")

            # Step tracker badges & progress bar
            badges = []
            for i in range(total_q):
                if i in st.session_state.quiz_answers:
                    st_status = st.session_state.quiz_answers[i]["status"]
                    badges.append("✅" if st_status == "Correct" else ("🤷" if st_status == "Don't Know" else "❌"))
                elif i == q_idx:
                    badges.append("🔵")
                else:
                    badges.append("⚪")
            st.markdown(f"**Progress:** {'  '.join(badges)} &nbsp; **({q_idx + 1} / {total_q})**")
            st.progress((q_idx + 1) / max(total_q, 1))

            q = questions[q_idx]
            subtopic = q.get("subtopic", f"Concept {q_idx + 1}")
            difficulty = q.get("difficulty", "Core")
            st.markdown(f"**`{difficulty}` · `{subtopic}`**")
            st.markdown(f"#### {q_idx + 1}. {q.get('question', '')}")

            raw_options = q.get("options", [])
            letters = ["A", "B", "C", "D"]
            formatted_options = [
                f"{letters[i]}. {opt}" if not str(opt).startswith(f"{letters[i]}.") else str(opt)
                for i, opt in enumerate(raw_options[:4])
            ]
            dont_know_label = "🤷 Don't Know (Cover this from scratch in my study plan)"
            all_choices = formatted_options + [dont_know_label]

            # Normalize correct_index safely
            raw_correct = q.get("correct_index", 0)
            if isinstance(raw_correct, str):
                correct_idx = {"A": 0, "B": 1, "C": 2, "D": 3}.get(
                    raw_correct.strip().upper(),
                    int(raw_correct) if raw_correct.strip().isdigit() else 0,
                )
            else:
                correct_idx = int(raw_correct)
            correct_idx = max(0, min(correct_idx, len(formatted_options) - 1))

            # Default to "Don't Know" (last index) so user never has to guess blindly
            selected_choice = st.radio(
                "Choose your answer:",
                options=all_choices,
                index=len(all_choices) - 1,
                key=f"quiz_radio_{q_idx}",
                disabled=st.session_state.quiz_checked,
            )

            # Step 1: Check Answer button
            if not st.session_state.quiz_checked:
                if st.button("Check Answer", type="primary"):
                    chosen_idx = all_choices.index(selected_choice)
                    if chosen_idx == len(all_choices) - 1:
                        status = "Don't Know"
                    elif chosen_idx == correct_idx:
                        status = "Correct"
                    else:
                        status = "Incorrect"

                    st.session_state.quiz_answers[q_idx] = {
                        "subtopic": subtopic,
                        "difficulty": difficulty,
                        "status": status,
                        "selected": selected_choice,
                    }
                    st.session_state.quiz_checked = True
                    st.rerun()

            # Step 2: Show Explanation & Next/Finish button
            else:
                ans = st.session_state.quiz_answers[q_idx]
                explanation = q.get("explanation", "")
                correct_text = formatted_options[correct_idx]

                if ans["status"] == "Correct":
                    st.success(f"**Correct!**\n\n{explanation}")
                elif ans["status"] == "Don't Know":
                    st.info(
                        f"**Marked as 'Don't Know' — we will build this from first principles in your guide.**\n\n"
                        f"**Answer Preview:** {correct_text}\n\n{explanation}"
                    )
                else:
                    st.error(
                        f"**Not quite.** The correct answer is **{correct_text}**.\n\n{explanation}"
                    )

                if q_idx < total_q - 1:
                    if st.button("Next Question ➡️", type="primary"):
                        st.session_state.quiz_idx += 1
                        st.session_state.quiz_checked = False
                        st.rerun()
                else:
                    if st.button("🎯 Finish Quiz & Generate Tailored Curriculum", type="primary"):
                        results_list = [
                            st.session_state.quiz_answers[i]
                            for i in sorted(st.session_state.quiz_answers.keys())
                        ]
                        try:
                            run_agent_stream(Command(resume={"results": results_list}))
                        except Exception as err:
                            st.error(f"Error submitting quiz results: {err}")

    # ----------------- Subcase 2B: Curriculum Review UI -----------------
    elif interrupt_data and interrupt_data.get("type") == "curriculum_review":
        with st.container(border=True):
            st.subheader("📋 Proposed Curriculum Review")
            if interrupt_data.get("summary"):
                st.markdown(interrupt_data["summary"])

            st.markdown("#### Modules to Research:")
            for idx, mod in enumerate(interrupt_data.get("modules", []), start=1):
                if isinstance(mod, dict):
                    mod_title = mod.get("title", f"Module {idx}")
                    mod_scope = mod.get("scope") or mod.get("description", "")
                    st.markdown(f"**{idx}. {mod_title}**  \n{mod_scope}")
                else:
                    st.markdown(f"**{idx}.** {mod}")

            st.divider()
            feedback = st.text_area(
                "Optional adjustments or specific topics to include:",
                placeholder="e.g., Add a deep-dive on carrier thread pinning to Module 2, or combine Modules 1 and 2.",
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

    # ----------------- Subcase 2C: Initial Prompt Input -----------------
    else:
        st.write(
            "Describe what you want to prepare for. We'll start with a quick 4–5 question diagnostic quiz "
            "to calibrate your study plan to your exact knowledge gaps."
        )

        user_prompt = st.chat_input("e.g., Help me prepare for an upcoming Java interview on Java Virtual Threads")

        if user_prompt:
            st.session_state.thread_id = str(uuid.uuid4())
            st.session_state.current_prompt = str(user_prompt)
            reset_quiz_state()

            with st.chat_message("user"):
                st.write(user_prompt)

            try:
                run_agent_stream({"messages": [{"role": "user", "content": str(user_prompt)}]})
            except Exception as err:
                st.error(f"Error starting session: {err}")

from pathlib import Path
import streamlit as st
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

if "chats" not in st.session_state:
    st.session_state.chats = get_existing_plans()

if "active_chat" not in st.session_state:
    st.session_state.active_chat = None

with st.sidebar:
    st.title("Mentor AI")
    if st.button("➕ New Chat", use_container_width=True):
        st.session_state.active_chat = None
        st.rerun()

    st.subheader("Your Study Plans")
    for slug, plan_data in st.session_state.chats.items():
        if st.button(plan_data["title"], key=slug, use_container_width=True):
            st.session_state.active_chat = slug
            st.rerun()

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
else:
    st.title("🎯 New Interview Study Session")
    st.write("Describe what you want to prepare for. The agent will orchestrate modular research directly into the study directory.")

    user_prompt = st.chat_input("e.g., Senior backend interview on Istio service mesh and traffic routing")

    if user_prompt:
        with st.chat_message("user"):
            st.write(user_prompt)

        try:
            with st.spinner("Orchestrating research across modules..."):
                agent.invoke({"messages": [{"role": "user", "content": user_prompt}]})

                st.session_state.chats = get_existing_plans()
                folders = [f for f in STUDY_DIR.iterdir() if f.is_dir() and list(f.glob("*.md"))]
                if folders:
                    newest = max(folders, key=lambda f: f.stat().st_mtime)
                    if not (newest / "prompt.txt").exists():
                        (newest / "prompt.txt").write_text(str(user_prompt), encoding="utf-8")
                    st.session_state.chats = get_existing_plans()
                    st.session_state.active_chat = newest.name

                st.rerun()
        except Exception as err:
            st.error(f"Error generating study plan: {err}")

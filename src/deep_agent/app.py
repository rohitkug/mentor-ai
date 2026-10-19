import os
from pathlib import Path
import streamlit as st
from deep_agent.coach import agent

st.set_page_config(page_title="Mentor AI", layout="wide")

STUDY_DIR = Path("study_plan")
STUDY_DIR.mkdir(parents=True, exist_ok=True)

# ----------------- Helper: Load Existing Plans from Disk -----------------
def get_existing_plans():
    """Scans study_plan/ directory and parses the title from each README.md."""
    plans = {}
    for folder in sorted(STUDY_DIR.iterdir()):
        readme = folder / "README.md"
        if folder.is_dir() and readme.exists():
            content = readme.read_text(encoding="utf-8")
            # Extract first heading '# Title' if present, or format the folder slug
            first_line = content.splitlines()[0] if content else ""
            title = (
                first_line.lstrip("# ").strip()
                if first_line.startswith("# ")
                else folder.name.replace("-", " ").title()
            )
            plans[folder.name] = {
                "title": title,
                "content": content,
            }
    return plans

# ----------------- Initialize Session State -----------------
if "chats" not in st.session_state:
    st.session_state.chats = get_existing_plans()

if "active_chat" not in st.session_state:
    st.session_state.active_chat = None

# ----------------- Sidebar (Past Chats & New Chat) -----------------
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

# ----------------- Main View -----------------
# Case 1: Viewing a saved chat (Read-only)
if st.session_state.active_chat and st.session_state.active_chat in st.session_state.chats:
    plan = st.session_state.chats[st.session_state.active_chat]
    st.title(f"📖 {plan['title']}")
    st.markdown(plan["content"])
    st.caption("🔒 This plan is complete (read-only mode). Click '+ New Chat' to generate another.")

# Case 2: New Natural Language Chat
else:
    st.title("🎯 New Interview Study Session")
    st.write(
        "Describe what you want to prepare for in your own words. "
        "Feel free to include specific technologies, problem spaces, or your target seniority level."
    )

    user_prompt = st.chat_input(
        "e.g., Staff backend interview on Redis cache invalidation strategies and stampede prevention"
    )

    if user_prompt:
        with st.chat_message("user"):
            st.write(user_prompt)

        with st.spinner("Curating resources and saving your study plan..."):
            query = (
                f"{user_prompt}\n\n"
                f"Please generate the study plan and save it to disk using the save_study_plan tool."
            )
            agent.invoke({"messages": [{"role": "user", "content": query}]})

            # Refresh all plans from disk
            st.session_state.chats = get_existing_plans()

            # Find the most recently created or modified plan folder
            folders = [f for f in STUDY_DIR.iterdir() if f.is_dir() and (f / "README.md").exists()]
            if folders:
                newest_folder = max(folders, key=lambda f: (f / "README.md").stat().st_mtime)
                st.session_state.active_chat = newest_folder.name

            st.rerun()

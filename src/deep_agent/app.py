import os
from pathlib import Path
import streamlit as st
from deep_agent.coach import agent  # Re-use your configured deep-agent

st.set_page_config(page_title="Mentor AI", layout="wide")

STUDY_DIR = Path("study_plan")
STUDY_DIR.mkdir(parents=True, exist_ok=True)


# ----------------- Helper: Load Existing Plans from Disk -----------------
def get_existing_plans():
    plans = {}
    for folder in STUDY_DIR.iterdir():
        readme = folder / "README.md"
        if folder.is_dir() and readme.exists():
            plans[folder.name] = readme.read_text(encoding="utf-8")
    return plans


# ----------------- Initialize Session State -----------------
if "chats" not in st.session_state:
    st.session_state.chats = get_existing_plans()

if "active_chat" not in st.session_state:
    st.session_state.active_chat = None  # None means starting a new chat

if "onboarding_step" not in st.session_state:
    st.session_state.onboarding_step = "area"  # area -> sub_area -> level -> done
    st.session_state.current_data = {}

# ----------------- Sidebar (Past Chats & New Chat) -----------------
with st.sidebar:
    st.title("Mentor AI")
    if st.button("➕ New Chat", use_container_width=True):
        st.session_state.active_chat = None
        st.session_state.onboarding_step = "area"
        st.session_state.current_data = {}
        st.rerun()

    st.subheader("Your Study Plans")
    for chat_title in sorted(st.session_state.chats.keys()):
        if st.button(chat_title, key=chat_title, use_container_width=True):
            st.session_state.active_chat = chat_title
            st.rerun()

# ----------------- Main View -----------------
# Case 1: Viewing a saved chat (Read-only)
if st.session_state.active_chat:
    st.title(f"📖 {st.session_state.active_chat}")
    plan_content = st.session_state.chats[st.session_state.active_chat]
    st.markdown(plan_content)
    st.caption("🔒 This plan is complete (read-only mode). Click '+ New Chat' to generate another.")

# Case 2: Onboarding Flow for a New Chat
else:
    st.title("🎯 New Interview Study Session")

    step = st.session_state.onboarding_step
    data = st.session_state.current_data

    if step == "area":
        area = st.chat_input("Enter Primary Area (e.g., System Design, Java, Python):")
        if area:
            data["area"] = area.strip()
            st.session_state.onboarding_step = "sub_area"
            st.rerun()
        st.info("Step 1 of 3: What primary technical area do you want to prepare for?")

    elif step == "sub_area":
        st.write(f"**Primary Area:** {data['area']}")
        sub_area = st.chat_input(f"Enter Sub-Area for {data['area']} (e.g., Distributed Caching):")
        if sub_area:
            data["sub_area"] = sub_area.strip()
            st.session_state.onboarding_step = "level"
            st.rerun()
        st.info("Step 2 of 3: What specific sub-area or topic should we focus on?")

    elif step == "level":
        st.write(f"**Primary Area:** {data['area']}")
        st.write(f"**Sub-Area:** {data['sub_area']}")
        level = st.chat_input("Enter Target Level (e.g., Mid-Level, Senior, Staff) [default: Senior]:")
        if level is not None:
            data["level"] = level.strip() or "Senior"
            st.session_state.onboarding_step = "generating"
            st.rerun()
        st.info("Step 3 of 3: What is your target level?")

    elif step == "generating":
        st.write(f"**Generating plan for:** {data['area']} -> {data['sub_area']} ({data['level']})")

        with st.spinner("Curating resources and saving your study plan..."):
            query = (
                f"I want to prep for a {data['level']} engineering interview. "
                f"Area: '{data['area']}', Sub-area: '{data['sub_area']}'. "
                f"Please generate the study plan and save it to disk using the save_study_plan tool."
            )
            response = agent.invoke({"messages": [{"role": "user", "content": query}]})

            # Refresh chats from disk to pick up the newly saved folder
            st.session_state.chats = get_existing_plans()

            # Set active chat to the new folder
            expected_name = f"{data['area'].lower().replace(' ', '-')}-{data['sub_area'].lower().replace(' ', '-')}"
            st.session_state.active_chat = expected_name if expected_name in st.session_state.chats else next(
                iter(st.session_state.chats))
            st.rerun()

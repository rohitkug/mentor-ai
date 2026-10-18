# Mentor AI: Technical Interview Prep Coach

**Mentor AI** is an autonomous interview preparation assistant powered by the [deepagents](https://github.com/langchain-ai/deepagents) harness and Google Gemini (`gemini-3.8-flash`). It systematically guides engineers through interview preparation by designing structured, high-signal study plans with free, authoritative resources and saving them directly to disk.

---

## Capabilities

* **Curated Study Roadmaps:** Generates ordered, step-by-step learning sequences tailored to your target engineering level (Mid-Level, Senior, Staff).
* **High-Signal Free Resources:** Focuses on official documentation, conference talks/deep-dives, classic engineering blogs, and common interview traps.
* **Autonomous Disk Persistence:** Leverages an agentic tool (`save_study_plan`) that automatically creates formatted study guides in `study_plan/<area>_<subarea>/README.md`.
* **Streamlit Web Interface:**
  * **Sidebar History:** Scans the `study_plan/` directory on startup so you can browse all previous sessions in read-only mode.
  * **Guided Session Creation:** A 3-step conversational flow for selecting Primary Area, Sub-Area, and Target Seniority.
* **CLI Mode:** Includes a terminal runner with real-time streaming output.

---

## Tech Stack

* **Runtime & Package Manager:** [uv](https://docs.astral.sh/uv/) (Python >= 3.12)
* **Agent Harness:** [deepagents](https://github.com/langchain-ai/deepagents)
* **Model Provider:** [langchain-google-genai](https://github.com/langchain-ai/langchain-google) (Google Gemini 3.8 Flash)
* **Frontend:** [Streamlit](https://streamlit.io/)
* **Environment:** `python-dotenv`

---

## Project Structure

```text
mentor-ai/
├── src/
│   └── deep_agent/
│       ├── __init__.py
│       ├── coach.py       # Core agent definition, prompt, and CLI runner
│       └── app.py         # Streamlit web application
├── study_plan/            # Generated study plans saved by the agent
│   └── java_flight-recorder/
│       └── README.md
├── pyproject.toml         # Project dependencies and script entrypoints
├── uv.lock                # Deterministic dependency lockfile
└── .env                   # API keys (not tracked in Git)
```

---

## Getting Started

### 1. Prerequisites
* [uv](https://docs.astral.sh/uv/getting-started/installation/) installed on your machine:
  ```bash
  brew install uv
  ```
* A Google Gemini API key from [Google AI Studio](https://aistudio.google.com/).

### 2. Configure Environment
Create a `.env` file in the root directory:
```bash
echo "GOOGLE_API_KEY=your_gemini_api_key_here" > .env
```

### 3. Install Dependencies
Sync and install dependencies into your local virtual environment:
```bash
uv sync
```

---

## Running the Application

### Option A: Web Interface (Streamlit)
Launch the browser UI:
```bash
uv run streamlit run src/deep_agent/app.py
```
Open [http://localhost:8501](http://localhost:8501) in your browser.

### Option B: Terminal CLI
Run the interactive command-line coach:
```bash
uv run deep-agent
```
*(or run directly via `uv run python -m deep_agent.coach`)*

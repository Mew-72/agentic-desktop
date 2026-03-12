# Jarvis — ADK Multi-Agent Assistant

A powerful, browser-based, AI-powered multi-agent system built with [Google ADK](https://google.github.io/adk-docs/) and the Gemini 2.5 API.

Jarvis acts as an autonomous router that delegates tasks to specialized sub-agents based on your objective.

## 🤖 The Agents

1. **Jarvis (Root Agent)**: The central orchestrator. It understands your intent and routes your request to the best specialist for the job.
2. **Terminal Assistant**: Executes shell commands, safely runs local scripts, and manages reusable terminal workflows.
3. **Coder Assistant**: Advanced coding specialist powered by `gemini-2.5-pro` with a high Thinking Budget. Specializes in writing, reading, and refactoring local code files.
4. **GitHub Assistant**: Manages GitHub repositories, reads issues, and interacts with PRs via the official GitHub MCP Server.
5. **Researcher Assistant**: Deep-reasoning agent (`gemini-2.5-pro`) for gathering information, answering questions, and synthesizing data.
6. **Browser Assistant**: Automates web browsers, interacts with sites, and scrapes information using the Playwright MCP server. *(Currently in Preview)*

## ⚡ Features

- **Multi-Agent Routing** — Seamless handoffs between specialized AI agents.
- **Thinking Budgets** — Complex agents (Coder, Researcher) are configured with extended token budgets for deeper reasoning.
- **Safe Execution** — Terminal commands are presented for your approval before running.
- **MCP Integration** — Connects to external Context via the Model Context Protocol (GitHub, Playwright).

## 🚀 Setup

1. **Install Dependencies** (inside a virtual environment):
   ```bash
   pip install google-adk python-dotenv
   ```

2. **Configure Environment Variables**:
   Create a `.env` file in the `myagent/` directory with:
   ```env
   GOOGLE_API_KEY="your-gemini-api-key"
   GITHUB_PERSONAL_ACCESS_TOKEN="your-github-token"
   GITHUB_HOST="https://github.com"
   ```

3. **Launch the ADK Web UI**:
   ```bash
   adk web
   ```

4. Open the browser at the URL shown (usually `http://localhost:8000`) and select **jarvis** from the agent dropdown.

## 📁 Project Structure

```text
myagent/
├── __init__.py          # Exports the root Jarvis agent
├── agent.py             # Defines the Router & orchestrates sub-agents
├── prompt.py            # Decision logic and rules for Jarvis
├── .env                 # API Keys
├── agents/              # The Sub-Agent Specialists
│   ├── terminal/
│   ├── github/
│   ├── coder/
│   ├── researcher/
│   └── browser/
└── tools/               # Shared Agent Tools
    ├── shell_tool.py    # CLI execution & safety layer
    └── workflow_tool.py # Workflow saving & execution
```

## 💡 Usage Examples

- `"Write a python script that calculates the fibonacci sequence and save it."` -> (Routes to Coder)
- `"Check my system info and save it to a workflow."` -> (Routes to Terminal)
- `"Read the latest issues on my microsoft/playwright-mcp repo."` -> (Routes to GitHub)
- `"Explain the difference between Pydantic v1 and v2."` -> (Routes to Researcher)


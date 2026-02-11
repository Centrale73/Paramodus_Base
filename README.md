# Agentic Workspace

**Agentic Workspace** is a desktop-native AI assistant that brings together multiple LLM providers and a robust, local RAG (Retrieval-Augmented Generation) system into a single, private interface.

Built with **Agno** (formerly PhiData) and **pywebview**, it runs locally as a native application, allowing you to chat with your documents using your preferred AI models without relying on browser tabs or complex cloud vector stores.

## 🚀 Key Features

*   **Multi-Model Support**: Switch seamlessly between top providers:
    *   **OpenAI** (GPT-4o)
    *   **Anthropic** (Claude 3.5 Sonnet)
    *   **Google** (Gemini 2.0 Flash)
    *   **Perplexity** (Sonar Pro)
    *   **Groq** (Llama 3, Mixtral)
    *   **xAI** (Grok)
    *   **OpenRouter** (Access to DeepSeek, Qwen, etc.)
*   **Local & Free RAG**: Integrated **LanceDB** vector database with **FastEmbed** runs entirely on your machine.
    *   No API costs for embeddings or vector storage.
    *   Private document storage.
*   **Document Ingestion**: Ingest and chat with your files directly:
    *   PDFs (`.pdf`)
    *   Spreadsheets (`.csv`)
    *   Code & Text (`.txt`, `.md`, `.py`, `.js`, `.json`)
*   **Persistent Memory**:
    *   **Smart History**: Conversations are saved to a local SQLite database (`~/.myapp/memory.db`).
    *   **User Memories**: The agent learns and remembers details about you across sessions.
*   **Desktop Native**: Lightweight windowed experience with real-time streaming and markdown rendering.

## 🛠️ Tech Stack

*   **Agent Framework**: [Agno](https://github.com/agno-ai/agno)
*   **GUI**: [pywebview](https://pywebview.flowrl.com/)
*   **Vector Database**: [LanceDB](https://lancedb.com/) (Local)
*   **Embeddings**: [FastEmbed](https://qdrant.github.io/fastembed/) (Local CPU-first inference)
*   **Frontend**: HTML5, CSS3, Vanilla JS

## 📦 Installation

### Prerequisites
*   Python 3.10+
*   Git

### Steps

1.  **Clone the repository**
    ```bash
    git clone -b Multiple https://github.com/Lmao53and2/agentic_workspace.git
    cd agentic_workspace
    ```

2.  **Create a virtual environment**
    ```bash
    python -m venv venv
    # Windows
    venv\Scripts\activate
    # Mac/Linux
    source venv/bin/activate
    ```

3.  **Install dependencies**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configuration**
    Create a `.env` file in the root directory and add the keys for the providers you intend to use:
    ```ini
    # Add the keys you need (you don't need all of them)
    OPENAI_API_KEY=sk-...
    ANTHROPIC_API_KEY=sk-ant-...
    GOOGLE_API_KEY=...
    PERPLEXITY_API_KEY=pplx-...
    GROQ_API_KEY=gsk_...
    XAI_API_KEY=...
    OPENROUTER_API_KEY=sk-or-...
    ```

## 🖥️ Usage

Run the application:
```bash
python app.py
```

### Managing Knowledge (RAG)
The application creates a local folder at `~/.myapp/lancedb` to store your vectorized documents.
*   **Ingest**: Use the UI to select files (PDF, code, CSV). The system automatically chunks and embeds them using `BAAI/bge-small-en-v1.5` (running locally).
*   **Chat**: Once ingested, simply ask questions about your documents. The agent automatically retrieves relevant context.

## 🧠 Project Structure

*   `app.py`: Entry point. Initializes the `ApiBridge` and the `pywebview` window.
*   `agents/workspace_agent.py`: Core logic. Configures the Agno agent, handles multi-provider switching, and manages the LanceDB connection.
*   `api/bridge.py`: Communication layer between the Python backend and JavaScript frontend.
*   `database.py`: SQLite utility for chat history.
*   `ui/`: Frontend assets (HTML/CSS/JS).

## 🔮 Roadmap

*   [ ] Multi-agent collaboration (Researcher + Coder agents).
*   [ ] Voice input/output integration.
*   [ ] One-click executable generation (EXE/DMG).

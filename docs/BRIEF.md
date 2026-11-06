# Financial Analyst Q&A Assistant Prototype


## Overview
Analysts at NovaBridge Finance, a boutique investment advisory firm, spend hours manually sifting through public market data, news articles, and regulatory filings to answer client questions. This process is slow, inefficient, and risks missing key information. To address this, NovaBridge wants to prototype an internal tool that uses modern AI techniques to provide quick, synthesized answers to complex financial questions, backed by verifiable sources.

## Deliverables
- A public GitHub repository or a single GitHub Gist URL containing your complete solution.
- A backend service written in Python that exposes an API to answer questions based on ingested financial documents.
- A simple frontend web interface (React or plain HTML/CSS/JS) that allows a user to ask a question and see the generated answer with its sources.
- A `README.md` file explaining your design choices, trade-offs, how to set up the project, and how to run it.
- A log or export of your conversations with any AI assistants (e.g., GitHub Copilot Chat, ChatGPT) used during the project.

## Suggested tools / libraries
- Python Web Framework: FastAPI or Flask
- AI/LLM Orchestration: LangChain or LlamaIndex
- Vector Store: ChromaDB, FAISS, or similar
- LLM: Ollama (for local models like Llama 3) or a free-tier API (e.g., Groq, OpenAI)
- Frontend: React with Vite, or plain HTML/CSS/JavaScript
- API Interaction: `fetch` API or `axios`
- Containerization (Optional): Docker

## On AI assistants & follow-up
- We encourage you to use AI assistants. This task tests your judgment and ability to verify AI-generated code, not your ability to memorize syntax.
- You must commit the full, unedited conversation log from any AI assistant you use (e.g., VS Code's 'Export Chat Session' for Copilot, ChatGPT conversation link/export). In your README, briefly describe which tools you used and for what parts of the project.
- Be prepared to walk us through any part of the code you submit and explain the design choices and trade-offs in depth during the technical interview.
- Focus on a clean, working prototype. We value good design, clear reasoning, and a functional end-to-end system over complex, half-finished features.

## How to submit
Reply to this email with **one** public GitHub repository or gist URL containing your solution.

<!-- AI-EVALUATOR:PRESCREEN-META {"language":"Python","dueDays":10,"timeBudgetHours":8} -->
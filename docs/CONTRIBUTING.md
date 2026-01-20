# Contributing to Skiller 🤝

We welcome contributions to Skiller! Here's how to get started.

## 🛠️ Development Setup

Skiller uses `uv` for dependency management.

1. **Clone the repo:**
   ```bash
   git clone https://github.com/yourusername/skiller.git
   cd skiller
   ```

2. **Install dependencies:**
   ```bash
   uv sync
   ```

3. **Activate virtual environment:**
   ```bash
   source .venv/bin/activate
   ```

## 🧪 Running Tests

Ensure your `.env` file is set up with valid API keys (Mistral, etc.).

```bash
# Run all tests
pytest tests/
```

## 🧩 Adding New Features

### Adding a New Tool
1. Create a new tool file in `app/tools/`.
2. Inherit from `agno.tools.Toolkit`.
3. Register your tool methods.

### Modifying Agents
- Agents are located in `app/agents/`.
- `SkillOrchestrator` uses Agno's `KnowledgeTools` for RAG.
- `SkillGenerator` uses `MistralChat` for extraction.

## 📝 Code Style

- We follow standard Python PEP 8 guidelines.
- Use type hints for all function arguments and return values.
- Keep agent instructions in `prompts/` managed by LangWatch if possible, or inline if simple.

## 📦 Pull Request Process

1. Fork the repository.
2. Create a feature branch (`git checkout -b feat/amazing-feature`).
3. Commit your changes (`git commit -m 'feat: Add amazing feature'`).
4. Push to the branch (`git push origin feat/amazing-feature`).
5. Open a Pull Request.

Happy coding! 🚀

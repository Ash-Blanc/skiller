# Skiller 🧠
> **Turn your X (Twitter) network into a powerful team of AI experts.**

**Skiller** is an advanced AI agent that "clones" the expertise of the people you follow on X. It analyzes their posts to understand their unique insights, communication style, and core skills, effectively turning your social graph into a usable **Skill Network**.

You can then task this network to solve complex problems, and Skiller will orchestrate the perfect "expert" from your connections to get the job done.

---

## ✨ Features

- **🕸️ Network Scraping**: Automatically finds and analyzes profiles you follow on X.
- **🧠 Skill Generation**: Extracts "Skill Profiles" (expertise, style, unique insights) from raw posts using advanced LLM analysis.
- **🔍 RAG-Powered Search**: Uses local LanceDB with hybrid search (semantic + keyword) for intelligent skill retrieval.
- **☁️ Optional Cloud Sync**: Optionally sync skills to Supermemory for cross-device access.
- **🤖 Intelligent Orchestration**: Uses Think → Search → Analyze reasoning cycle to select the best expert.
- **🔌 Extensible Architecture**: Built on **Agno**, allowing for easy addition of new tools and capabilities.

---

## 🛠️ Prerequisites

Before you begin, ensure you have the following API keys:

- **Mistral API Key**: For the core LLM intelligence and embeddings.
- **LangWatch API Key**: For prompt management and monitoring.
- **Firecrawl API Key**: For scraping X profiles and posts.
- **(Optional) Supermemory API Key**: For cloud sync of skills.
- **(Optional) X / Twitter API Keys**: For more robust data fetching.

---

   

2. **Add your API Keys:**
   Open `.env` and fill in your keys:
   
   # LLM Provider
   MISTRAL_API_KEY=...

   # Monitoring & Prompts
   LANGWATCH_API_KEY=...

   # Scraping & Memory
   
---

## 🖥️ Usage

# Build skills from the people @user follows
skiller build-network-skills --username "user_handle" --max-following 10 --posts-per-user 5
skiller execute-task "Analyze the latest trends in LLM reasoning based on my network's insights"

graph TD
    User[User] -->|build-network-skills| Scraper[X Scraper Agent]
    Scraper -->|Get Posts| Firecrawl[Firecrawl / X API]
    Scraper -->|Raw Posts| Generator[Skill Generator Agent]
    Generator -->|Extract| Profile[Skill Profile]
    Profile -->|Save| Local[Local File System]
    Profile -->|Index| Mem[Supermemory Vector DB]
    
    
## 🛡️ License

[MIT](LICENSE)

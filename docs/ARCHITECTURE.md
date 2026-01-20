# Skiller Architecture Documentation 🏗️

Skiller is designed to turn your social network into a usable "Skill Network" of AI agents. It does this by scraping profiles, analyzing their posts to understand their expertise, and then creating a digital "clone" of that expertise that you can query.

## High-Level Architecture

```mermaid
graph TD
    User([User]) -->|1. build-network-skills| CLI[CLI (main.py)]
    CLI -->|2. Get Filters| XScraper[XScraperAgent]
    XScraper -->|3. Scrape Profile & Posts| Firecrawl[Firecrawl / X Toolkit]
    
    XScraper -->|4. Raw Posts Data| SkillGen[SkillGenerator]
    SkillGen -->|5. Analyze & Extract| Mistral[Mistral LLM]
    Mistral -->|6. Skill Profile| SkillGen
    
    SkillGen -->|7. Save Profile| LocalFS[File System (skills/)]
    SkillGen -->|8. Index Embeddings| LanceDB[(LanceDB Vector DB)]
    LanceDB -.->|Sync (Optional)| Supermemory[(Supermemory Cloud)]
    
    User -->|9. execute-task| CLI
    CLI -->|10. Delegate| Orchestrator[SkillOrchestrator]
    Orchestrator -->|11. RAG Search| LanceDB
    Orchestrator -->|12. Select Expert| Expert[Expert Agent]
    Expert -->|13. Final Result| User
```

---

## 🔍 1. The Core Agents

There are **three main agents** that drive the system. Each has a specific responsibility:

### **1. `XScraperAgent`** (The Recruiter)
- **Role**: Finds talent.
- **Location**: `app/agents/x_scraper.py`
- **What it does**:
  - Connects to X (Twitter) using Tweepy or Firecrawl.
  - Fetches the accounts you follow.
  - **Filtering Logic**:
    - **Verified**: Filters for blue-tick accounts (default).
    - **Human Classifier**: Uses heuristics (bio keywords like "dad", "husband", "views my own") and an LLM classifier to filter out organizations and bots.
  - Scrapes the last ~10 posts for each surviving candidate.

### **2. `SkillGenerator`** (The Profiler)
- **Role**: Analyzes talent.
- **Location**: `app/agents/skill_generator.py`
- **What it does**:
  - Takes raw post data.
  - Feeds it to **Mistral Large** with a prompt to extract:
    - **Core Expertise**: "React", "Venture Capital", "Biohacking"
    - **Communication Style**: "Direct, sarcastic, uses lots of emojis"
    - **Unique Insights**: "Believes AI will replace junior devs"
  - **Saves** this profile as a `SKILL.md` file locally in `skills/`.
  - **Indexes** this profile into the **LanceDB** vector database.

### **3. `SkillOrchestrator`** (The Manager)
- **Role**: Assigns tasks.
- **Location**: `app/agents/orchestrator.py`
- **What it does**:
  - Uses **RAG (Retrieval-Augmented Generation)** to find the right expert.
    1. **Think**: "The user is asking about web scraping. I need an expert on scraping/Python."
    2. **Search**: Queries the **LanceDB** database for skills matching "web scraping".
    3. **Analyze**: "I found `@firecrawl_dev`. They look perfect."
  - Loads that specific skill and executes the task *as if* it were that expert.

---

## 💾 2. The Storage Layer

### **File System (`skills/`)**
- Each expert gets a folder: `skills/username/`.
- Inside is a `SKILL.md` file containing the "prompt instructions" (System Prompt).
- **Benefit**: Human-readable, version-controllable, easily editable.

### **Vector Database (`data/skill_db/`)**
- **LanceDB**: A local, high-performance vector DB.
- **Location**: `data/skill_db/`
- **What it stores**: Vector embeddings of the skills for semantic search.
- **Benefit**: Fast, offline-first semantic retrieval.

### **Cloud Sync (Optional)**
- **Supermemory**: An external memory service.
- **Usage**: Enabled via `--cloud-sync`.
- **Benefit**: Backup and syncing across devices.

---

## 🚀 3. The CLI (`app/main.py`)

The CLI connects all components:

- `build-network-skills`: Runs the Scraper -> Generator pipeline.
- `execute-task`: Runs the Orchestrator with RAG.
- `sync`: A maintenance tool to re-index local `SKILL.md` files into LanceDB.

"""
AgentOS server for Skiller.
Exposes the Skiller agent and custom API endpoints via FastAPI.
"""
import glob
from typing import Optional, List
from pydantic import BaseModel
from fastapi import APIRouter, BackgroundTasks
from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.os import AgentOS
from dotenv import load_dotenv

from app.agents.orchestrator import SkillOrchestrator
from app.agents.x_scraper import XScraperAgent
from app.agents.skill_generator import SkillGenerator
from app.tools.supermemory_tool import SupermemoryToolkit
from app.knowledge.skill_knowledge import get_skill_knowledge
from app.utils.state import (
    load_network_state,
    save_network_state,
    get_pending_handles,
    mark_handle_processed
)

# Load environment variables
load_dotenv()

# =============================================================================
# Pydantic Models for API
# =============================================================================

class BuildNetworkRequest(BaseModel):
    username: Optional[str] = None
    handles: Optional[List[str]] = None  # Manual handles, bypasses scraping
    batch_size: float = 0.2
    refresh: bool = False
    max_following: int = 100
    posts_per_user: int = 5
    include_unverified: bool = False
    include_orgs: bool = False
    cloud_sync: bool = False

class ExecuteTaskRequest(BaseModel):
    task: str

class SyncRequest(BaseModel):
    rebuild: bool = False
    list_skills: bool = False
    cloud_sync: bool = False
    skills_dir: str = "skills"

class StatusResponse(BaseModel):
    total_following: int
    processed: int
    pending: int
    last_updated: Optional[str]

class BuildResponse(BaseModel):
    status: str
    message: str
    processed_count: int = 0
    remaining_count: int = 0

class TaskResponse(BaseModel):
    result: str

class SyncResponse(BaseModel):
    status: str
    message: str
    skills: Optional[List[str]] = None

# =============================================================================
# Custom API Router
# =============================================================================

router = APIRouter(prefix="/api", tags=["Skiller API"])

@router.get("/status", response_model=StatusResponse)
async def get_status():
    """Get current network processing status."""
    state = load_network_state()
    pending = get_pending_handles(state)
    return StatusResponse(
        total_following=len(state.get("following_handles", [])),
        processed=len(state.get("processed_handles", [])),
        pending=len(pending),
        last_updated=state.get("last_updated")
    )

@router.post("/execute-task", response_model=TaskResponse)
async def execute_task(request: ExecuteTaskRequest):
    """Execute a task using the best available expert skill."""
    orchestrator = SkillOrchestrator()
    result = orchestrator.run_task(request.task)
    return TaskResponse(result=result)

@router.post("/sync", response_model=SyncResponse)
async def sync_skills(request: SyncRequest):
    """Sync and manage the skill knowledge base."""
    skill_files = glob.glob(f"{request.skills_dir}/*/SKILL.md")
    skill_names = [f.split("/")[-2] for f in skill_files]
    
    if request.list_skills:
        return SyncResponse(
            status="success",
            message=f"Found {len(skill_names)} skills",
            skills=skill_names
        )
    
    messages = []
    
    if request.rebuild:
        knowledge = get_skill_knowledge()
        indexed = 0
        for skill_file in skill_files:
            try:
                knowledge.add_content(path=skill_file)
                indexed += 1
            except Exception:
                pass
        messages.append(f"Rebuilt knowledge base with {indexed} skills")
    
    if request.cloud_sync:
        try:
            supermemory = SupermemoryToolkit()
            synced = 0
            for skill_file in skill_files:
                try:
                    with open(skill_file, 'r') as f:
                        content = f.read()
                    supermemory.add_skill_to_memory(content)
                    synced += 1
                except Exception:
                    pass
            messages.append(f"Synced {synced} skills to cloud")
        except Exception as e:
            messages.append(f"Cloud sync failed: {e}")
    
    return SyncResponse(
        status="success",
        message="; ".join(messages) if messages else "No action taken",
        skills=skill_names
    )

def _process_batch(
    username: str,
    batch: List[str],
    posts_per_user: int,
    cloud_sync: bool,
    state: dict
):
    """Background task to process a batch of handles."""
    scraper = XScraperAgent()
    generator = SkillGenerator()
    supermemory = None
    
    if cloud_sync:
        try:
            supermemory = SupermemoryToolkit()
        except Exception:
            pass
    
    for handle in batch:
        posts = scraper.get_posts_for_handle(handle, count=posts_per_user)
        if not posts or len(posts) < 50:
            state = mark_handle_processed(state, handle)
            save_network_state(state)
            continue
        
        try:
            skill_profile = generator.generate_skill(
                person_name=handle,
                x_handle=handle,
                posts=posts
            )
            
            if skill_profile and not isinstance(skill_profile, str):
                generator.save_skill(skill_profile)
                
                if supermemory:
                    try:
                        skill_json = skill_profile.model_dump_json()
                        supermemory.add_skill_to_memory(skill_json)
                    except Exception:
                        pass
        except Exception:
            pass
        
        state = mark_handle_processed(state, handle)
        save_network_state(state)

@router.post("/build-network-skills", response_model=BuildResponse)
async def build_network_skills(
    request: BuildNetworkRequest,
    background_tasks: BackgroundTasks
):
    """
    Build skills from X network.
    Processing happens in the background; use /status to track progress.
    """
    state = load_network_state()
    
    # Handle manual handles input
    if request.handles:
        state["following_handles"] = request.handles
        state["processed_handles"] = []
        save_network_state(state)
        username = request.username or "manual"
    else:
        if not request.username:
            return BuildResponse(
                status="error",
                message="Username is required when not providing manual handles"
            )
        username = request.username
        
        need_fetch = request.refresh or not state.get("following_handles")
        
        if need_fetch:
            scraper = XScraperAgent()
            verified_only = not request.include_unverified
            humans_only = not request.include_orgs
            
            following_handles = scraper.get_following_profiles(
                username,
                verified_only=verified_only,
                humans_only=humans_only
            )
            
            if not following_handles:
                return BuildResponse(
                    status="error",
                    message="No following handles found. Check if profile is private/accessible."
                )
            
            state["following_handles"] = following_handles[:request.max_following]
            if not request.refresh:
                state["processed_handles"] = []
            save_network_state(state)
    
    # Calculate batch
    pending = get_pending_handles(state)
    if not pending:
        return BuildResponse(
            status="complete",
            message="All profiles have been processed!",
            processed_count=len(state.get("processed_handles", [])),
            remaining_count=0
        )
    
    batch_count = max(1, int(len(pending) * request.batch_size))
    batch = pending[:batch_count]
    
    # Start background processing
    background_tasks.add_task(
        _process_batch,
        username,
        batch,
        request.posts_per_user,
        request.cloud_sync,
        state
    )
    
    return BuildResponse(
        status="processing",
        message=f"Started processing {len(batch)} profiles in background",
        processed_count=len(state.get("processed_handles", [])),
        remaining_count=len(pending)
    )

# =============================================================================
# Initialize AgentOS with Custom Routes
# =============================================================================

# Initialize the orchestrator to get the configured agent
orchestrator = SkillOrchestrator()
expert_agent = orchestrator.selector_agent

# Configure the agent for AgentOS
expert_agent.name = "skiller-expert"
expert_agent.description = "An AI expert orchestrator that finds and executes tasks using your network's skills."
expert_agent.storage = SqliteDb("data/agentos.db")

# Create a base FastAPI app with custom routes
from fastapi import FastAPI

base_app = FastAPI(
    title="Skiller API",
    version="0.1.0",
    description="Turn your X network into a team of AI experts.",
)
base_app.include_router(router)

# Create the AgentOS instance with the base app
agentos = AgentOS(
    agents=[expert_agent],
    base_app=base_app,
)

# Export the FastAPI app for uvicorn
app = agentos.get_app()


if __name__ == "__main__":
    agentos.serve(app="app.os:app", reload=True)
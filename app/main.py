import os
import typer
import asyncio
from typing import Optional
from dotenv import load_dotenv

from app.agents.x_scraper import XScraperAgent
from app.agents.skill_generator import SkillGenerator
from app.agents.orchestrator import SkillOrchestrator
from app.tools.supermemory_tool import SupermemoryToolkit

# Load environment variables
load_dotenv()

app = typer.Typer(
    help="Skiller - Turn your X network into a team of AI experts",
    context_settings={"help_option_names": ["-h", "--help"]}
)

@app.command()
def build_network_skills(
    username: Optional[str] = typer.Argument(None, help="The X username to analyze"),
    max_following: int = typer.Option(10, help="Maximum number of profiles to process"),
    posts_per_user: int = typer.Option(5, help="Number of posts to analyze per user"),
    include_unverified: bool = typer.Option(False, "--include-unverified", help="Include unverified accounts (default: verified only)"),
    include_orgs: bool = typer.Option(False, "--include-orgs", help="Include organization accounts (default: humans only)")
):
    """
    Scrapes the user's network, analyzes profiles, and saves skills to Supermemory.
    """
    if username is None:
        username = typer.prompt("👤 What is the X username to analyze?")

    print(f"🚀 Starting skill extraction for network of @{username}...")
    
    scraper = XScraperAgent()
    generator = SkillGenerator()
    supermemory = SupermemoryToolkit()
    
    # 1. Get following list
    verified_only = not include_unverified
    humans_only = not include_orgs
    
    filter_parts = []
    if verified_only:
        filter_parts.append("verified")
    if humans_only:
        filter_parts.append("humans only")
    filter_msg = f" ({', '.join(filter_parts)})" if filter_parts else ""
    
    print(f"🔍 Fetching following list for @{username}{filter_msg}...")
    following_handles = scraper.get_following_profiles(username, verified_only=verified_only, humans_only=humans_only)
    
    if not following_handles:
        print("⚠️ No following handles found. Trying a fallback or check if profile is private/accessible.")
        # Optional: Add a manual list for testing if scraping fails
        # following_handles = ["example_expert"]
        return

    print(f"✅ Found {len(following_handles)} profiles. Processing top {max_following}...")
    
    for i, handle in enumerate(following_handles[:max_following]):
        print(f"\n[{i+1}/{max_following}] Processing @{handle}...")
        
        # 2. Get posts
        posts = scraper.get_posts_for_handle(handle, count=posts_per_user)
        if not posts or len(posts) < 50: # Arbitrary small length check for empty/error
            print(f"   ⚠️ Could not scrape sufficient posts for @{handle}. Skipping.")
            continue
            
        # 3. Generate Skill Profile
        print(f"   🧠 Analyzing expertise...")
        try:
            skill_profile = generator.generate_skill(
                person_name=handle, # We might not have the display name, using handle
                x_handle=handle,
                posts=posts
            )
            
            if skill_profile:
                # 4. Save to Supermemory
                print(f"   💾 Saving skill to Supermemory...")
                # Convert Pydantic model to JSON string
                skill_json = skill_profile.model_dump_json()
                supermemory_result = supermemory.add_skill_to_memory(skill_json)
                
                # 5. Save locally as Agno Skill
                print(f"   📂 Saving skill locally as Agno Skill...")
                skill_path = generator.save_skill(skill_profile)
                print(f"   ✅ Saved locally to: {skill_path}")
                print(f"   ✅ {supermemory_result}")
            else:
                print("   ❌ Failed to generate skill profile.")
                
        except Exception as e:
            print(f"   ❌ Error processing @{handle}: {e}")

    print("\n🎉 Network skill building complete!")

@app.command()
def execute_task(task: str):
    """
    Executes a task using the best available expert skill from the network.
    """
    print(f"🤖 Received task: {task}")
    print("🔍 Searching for the best expert...")
    
    orchestrator = SkillOrchestrator()
    result = orchestrator.run_task(task)
    
    print("\n" + "="*50)
    print("RESULT")
    print("="*50)
    print(result)
    print("="*50)

if __name__ == "__main__":
    app()
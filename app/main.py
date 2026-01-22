import os
import typer
import asyncio
from typing import Optional
from dotenv import load_dotenv

from app.agents.x_scraper import XScraperAgent
from app.agents.skill_generator import SkillGenerator
from app.agents.orchestrator import SkillOrchestrator
from app.tools.supermemory_tool import SupermemoryToolkit
from app.utils.state import (
    load_network_state,
    save_network_state,
    get_pending_handles,
    mark_handle_processed,
    clear_network_state
)

# Load environment variables
load_dotenv()

app = typer.Typer(
    help="Skiller - Turn your X network into a team of AI experts",
    context_settings={"help_option_names": ["-h", "--help"]}
)

@app.command()
def build_network_skills(
    username: Optional[str] = typer.Argument(None, help="The X username to analyze"),
    handles: Optional[str] = typer.Option(None, "--handles", help="Comma-separated list of handles to process directly (bypasses scraping)"),
    batch_size: float = typer.Option(0.2, "--batch-size", "-b", help="Fraction of pending profiles to process (0.0-1.0)"),
    refresh: bool = typer.Option(False, "--refresh", "-r", help="Force refresh of following list"),
    max_following: int = typer.Option(100, help="Maximum total profiles to track"),
    posts_per_user: int = typer.Option(5, help="Number of posts to analyze per user"),
    include_unverified: bool = typer.Option(False, "--include-unverified", help="Include unverified accounts"),
    include_orgs: bool = typer.Option(False, "--include-orgs", help="Include organization accounts"),
    cloud_sync: bool = typer.Option(False, "--cloud-sync", help="Also sync skills to Supermemory cloud")
):
    """
    Scrapes the user's network, analyzes profiles, and generates AI skills.
    Uses lazy loading to process profiles in batches across multiple runs.
    """
    # Handle manual handles input
    if handles:
        manual_handles = [h.strip().replace('@', '') for h in handles.split(',') if h.strip()]
        print(f"📝 Using manually provided handles: {len(manual_handles)} profiles")
        
        # Update state with manual handles
        state = load_network_state()
        state["following_handles"] = manual_handles
        state["processed_handles"] = []
        save_network_state(state)
        username = username or "manual"
    else:
        if username is None:
            username = typer.prompt("👤 What is the X username to analyze?")

    print(f"🚀 Starting skill extraction for network of @{username}...")
    
    # Load existing state
    state = load_network_state()
    
    # Check if we need to fetch (refresh or no cached list)
    need_fetch = (refresh or not state.get("following_handles")) and not handles
    
    scraper = XScraperAgent()
    generator = SkillGenerator()
    
    # Optional: Supermemory cloud sync
    supermemory = None
    if cloud_sync:
        try:
            supermemory = SupermemoryToolkit()
            print("☁️ Cloud sync enabled (Supermemory)")
        except Exception as e:
            print(f"⚠️ Could not initialize Supermemory: {e}")
            print("   Continuing with local storage only...")
    
    # Fetch following list if needed
    if need_fetch:
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
            print("⚠️ No following handles found. Check if profile is private/accessible.")
            return
        
        # Update state with new following list (trim to max_following)
        state["following_handles"] = following_handles[:max_following]
        if refresh:
            # On refresh, keep processed handles but they'll be skipped
            print(f"🔄 Refreshed following list. {len(state['following_handles'])} profiles tracked.")
        else:
            state["processed_handles"] = []
            print(f"✅ Found {len(state['following_handles'])} profiles. Tracking for batch processing.")
        save_network_state(state)
    else:
        print(f"📋 Using cached following list ({len(state['following_handles'])} profiles)")
    
    # Calculate batch
    pending = get_pending_handles(state)
    if not pending:
        print("🎉 All profiles have been processed! Use --refresh to re-fetch.")
        return
    
    batch_count = max(1, int(len(pending) * batch_size))
    batch = pending[:batch_count]
    
    print(f"📦 Processing batch: {len(batch)} of {len(pending)} pending profiles ({batch_size*100:.0f}%)")
    
    for i, handle in enumerate(batch):
        print(f"\n[{i+1}/{len(batch)}] Processing @{handle}...")
        
        # Try to get enriched profile data (profile + highlights + tweets)
        enriched_data = None
        if scraper.scrapebadger and scraper.scrapebadger.is_available():
            print(f"   📊 Fetching enriched profile data...")
            try:
                enriched_data = scraper.scrapebadger.get_enriched_profile(handle, max_tweets=posts_per_user)
            except Exception as e:
                print(f"   ⚠️ Enriched profile fetch failed: {e}")
        
        # Generate Skill Profile
        print(f"   🧠 Analyzing expertise...")
        try:
            # Use enriched skill generation if we have enriched data
            if enriched_data and enriched_data.get("profile") and (enriched_data.get("tweets") or enriched_data.get("highlights")):
                print(f"   ✨ Using enriched data (profile + highlights + tweets)")
                skill_profile = generator.generate_enriched_skill(
                    profile=enriched_data["profile"],
                    highlights=enriched_data.get("highlights", []),
                    tweets=enriched_data.get("tweets", [])
                )
            else:
                # Fallback to basic method
                print(f"   📝 Using basic data (tweets only)")
                posts = scraper.get_posts_for_handle(handle, count=posts_per_user)
                if not posts or len(posts) < 50:
                    print(f"   ⚠️ Could not scrape sufficient posts for @{handle}. Marking as processed.")
                    state = mark_handle_processed(state, handle)
                    save_network_state(state)
                    continue
                    
                skill_profile = generator.generate_skill(
                    person_name=handle,
                    x_handle=handle,
                    posts=posts
                )
            
            if skill_profile and not isinstance(skill_profile, str):
                print(f"   💾 Saving skill and indexing for RAG...")
                skill_path = generator.save_skill(skill_profile)
                print(f"   ✅ Indexed and saved to: {skill_path}")
                
                if supermemory:
                    try:
                        skill_json = skill_profile.model_dump_json()
                        result = supermemory.add_skill_to_memory(skill_json)
                        print(f"   ☁️  {result}")
                    except Exception as e:
                        print(f"   ⚠️ Cloud sync failed: {e}")
            else:
                error_msg = skill_profile if isinstance(skill_profile, str) else "Unknown error"
                print(f"   ❌ Failed to generate valid skill profile: {error_msg}")
                
        except Exception as e:
            print(f"   ❌ Error processing @{handle}: {e}")
        
        # Mark as processed regardless of success/failure
        state = mark_handle_processed(state, handle)
        save_network_state(state)

    remaining = len(pending) - len(batch)
    print(f"\n🎉 Batch complete! {remaining} profiles remaining. Run again to continue.")

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


@app.command()
def sync(
    rebuild: bool = typer.Option(False, "--rebuild", "-r", help="Rebuild the knowledge base from scratch"),
    username: Optional[str] = typer.Option(None, "--username", "-u", help="X username to fetch fresh followings from (uses ScrapeBadger)"),
    list_skills: bool = typer.Option(False, "--list", "-l", help="List all indexed skills"),
    cloud_sync: bool = typer.Option(False, "--cloud-sync", "-c", help="Sync all skills to Supermemory cloud"),
    from_file: Optional[str] = typer.Option(None, "--from-file", "-f", help="Path to file containing handles (one per line)"),
    skills_dir: str = typer.Option("skills", help="Directory containing skill files")
):
    """
    Sync and manage the skill knowledge base.
    
    Use this command to:
    - Rebuild completely from X: skiller sync -r -u <username>
    - Rebuild from file: skiller sync -r -f handles.txt
    - Re-index existing skills: skiller sync -r
    - List all indexed skills: skiller sync -l
    - Sync to cloud: skiller sync -c
    """
    import glob
    import shutil
    from app.knowledge.skill_knowledge import get_skill_knowledge
    
    print("🔄 Skill Sync Manager")
    print("-" * 40)
    
    # Handle full rebuild from X username (fetch fresh followings via ScrapeBadger)
    if rebuild and username:
        print(f"\n🔥 Full rebuild requested for @{username}")
        print("   Fetching fresh followings from ScrapeBadger (no cache)...")
        
        # 1. Clear existing skills directory
        if os.path.exists(skills_dir):
            skill_count = len(glob.glob(f"{skills_dir}/*/SKILL.md"))
            print(f"   🗑️  Deleting {skill_count} existing skill files...")
            shutil.rmtree(skills_dir)
        os.makedirs(skills_dir, exist_ok=True)
        
        # 2. Clear network state
        print("   🗑️  Clearing network state...")
        clear_network_state()
        
        # 3. Clear LanceDB knowledge base
        db_path = "data/skill_db"
        if os.path.exists(db_path):
            print("   🗑️  Clearing knowledge base...")
            shutil.rmtree(db_path)
        
        # 4. Fetch fresh followings from ScrapeBadger API (NO CACHE!)
        print(f"\n🌐 Fetching followings for @{username} via ScrapeBadger API...")
        scraper = XScraperAgent()
        
        # Use ScrapeBadger to get fresh followings
        handles = scraper.get_following_profiles(username, verified_only=True, humans_only=True)
        
        if not handles:
            print("   ❌ Failed to fetch followings. Check ScrapeBadger API key and username.")
            return
        
        print(f"   ✅ Retrieved {len(handles)} handles from ScrapeBadger")
        
        # 5. Initialize state with fresh handles
        state = load_network_state()
        state["following_handles"] = handles
        state["processed_handles"] = []
        state["source"] = f"scrapebadger:{username}"
        save_network_state(state)
        
        print(f"\n✅ Rebuild complete! State initialized with {len(handles)} fresh handles.")
        print("   Run 'skiller build-network-skills' to generate skills.")
        return
    
    # Handle full rebuild with file import
    if rebuild and from_file:
        print(f"\n🔥 Full rebuild requested with handles from: {from_file}")
        
        # 1. Clear existing skills directory
        if os.path.exists(skills_dir):
            skill_count = len(glob.glob(f"{skills_dir}/*/SKILL.md"))
            print(f"   🗑️  Deleting {skill_count} existing skill files...")
            shutil.rmtree(skills_dir)
        os.makedirs(skills_dir, exist_ok=True)
        
        # 2. Clear network state
        print("   🗑️  Clearing network state...")
        clear_network_state()
        
        # 3. Clear LanceDB knowledge base
        db_path = "data/skill_db"
        if os.path.exists(db_path):
            print("   🗑️  Clearing knowledge base...")
            shutil.rmtree(db_path)
        
        # 4. Read handles from file
        try:
            with open(from_file, 'r') as f:
                handles = [line.strip().replace('@', '') for line in f if line.strip() and not line.startswith('#')]
            print(f"   📋 Loaded {len(handles)} handles from file")
        except FileNotFoundError:
            print(f"   ❌ File not found: {from_file}")
            return
        except Exception as e:
            print(f"   ❌ Error reading file: {e}")
            return
        
        # 5. Initialize state with handles
        state = load_network_state()
        state["following_handles"] = handles
        state["processed_handles"] = []
        save_network_state(state)
        
        print(f"\n✅ Rebuild complete! State initialized with {len(handles)} handles.")
        print("   Run 'skiller build-network-skills' to generate skills.")
        return
    
    # Find all SKILL.md files
    skill_files = glob.glob(f"{skills_dir}/*/SKILL.md")
    print(f"📁 Found {len(skill_files)} skill files in '{skills_dir}/'")
    
    if list_skills:
        print("\n📋 Indexed Skills:")
        for i, skill_file in enumerate(skill_files, 1):
            skill_name = skill_file.split("/")[-2]
            print(f"   {i}. {skill_name}")
        return
    
    if rebuild:
        print("\n🔨 Rebuilding knowledge base...")
        
        # Get fresh knowledge base
        knowledge = get_skill_knowledge()
        
        indexed = 0
        for skill_file in skill_files:
            skill_name = skill_file.split("/")[-2]
            try:
                knowledge.add_content(path=skill_file)
                print(f"   ✅ Indexed: {skill_name}")
                indexed += 1
            except Exception as e:
                print(f"   ❌ Failed to index {skill_name}: {e}")
        
        print(f"\n✨ Rebuilt knowledge base with {indexed} skills")
    
    if cloud_sync:
        print("\n☁️ Syncing to Supermemory cloud...")
        try:
            supermemory = SupermemoryToolkit()
            synced = 0
            for skill_file in skill_files:
                skill_name = skill_file.split("/")[-2]
                try:
                    with open(skill_file, 'r') as f:
                        content = f.read()
                    result = supermemory.add_skill_to_memory(content)
                    print(f"   ☁️ Synced: {skill_name}")
                    synced += 1
                except Exception as e:
                    print(f"   ❌ Failed to sync {skill_name}: {e}")
            print(f"\n✨ Synced {synced} skills to cloud")
        except Exception as e:
            print(f"❌ Could not initialize Supermemory: {e}")
    
    if not rebuild and not cloud_sync and not list_skills:
        print("\nUsage examples:")
        print("  skiller sync --list                          # List all skills")
        print("  skiller sync --rebuild                       # Rebuild knowledge base")
        print("  skiller sync --rebuild --from-file handles.txt  # Full rebuild from file")
        print("  skiller sync --cloud-sync                    # Sync to Supermemory")
        print("  skiller sync -r -c                           # Rebuild + cloud sync")


if __name__ == "__main__":
    app()
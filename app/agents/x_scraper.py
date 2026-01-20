from typing import List, Dict
from agno.agent import Agent
from agno.models.mistral import MistralChat
from app.tools.x_scraping_tool import XScrapingToolkit
import langwatch

class XScraperAgent:
    def __init__(self, model_id: str = "mistral-large-latest"):
        self.prompt_config = langwatch.prompts.get("x_following_finder")
        self.x_tools = XScrapingToolkit()
        
        self.agent = Agent(
            model=MistralChat(id=model_id),
            tools=[self.x_tools],
            instructions=self.prompt_config.prompt,
            markdown=True
        )

    def get_following_profiles(self, username: str, verified_only: bool = True) -> List[str]:
        """
        Gets the list of handles the user follows.
        :param username: The X username to analyze.
        :param verified_only: If True, only return verified (blue tick) accounts.
        """
        if verified_only:
            prompt = f"Find the handles followed by @{username} that have a verified blue checkmark. Return ONLY a comma-separated list of verified handles, nothing else."
        else:
            prompt = f"Find the handles followed by @{username}. Return ONLY a comma-separated list of handles, nothing else."
        
        response = self.agent.run(prompt)
        
        # Parse the response
        content = response.content
        if not content:
            return []
            
        handles = [h.strip().replace('@', '') for h in content.split(',') if h.strip()]
        return handles

    def get_posts_for_handle(self, handle: str, count: int = 10) -> str:
        """
        Gets recent posts for a specific handle.
        """
        # We use the raw output from scraping, the skill generator will process it.
        return self.x_tools.get_user_posts(handle, count)
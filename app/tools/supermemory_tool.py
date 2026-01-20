import os
from typing import List, Optional, Any
from supermemory import Supermemory
from pydantic import BaseModel
from agno.tools import Toolkit

class SupermemoryToolkit(Toolkit):
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(name="supermemory")
        self.api_key = api_key or os.getenv("SUPERMEMORY_API_KEY")
        if not self.api_key:
            raise ValueError("SUPERMEMORY_API_KEY not found")
        self.client = Supermemory(api_key=self.api_key)
        
        self.register(self.add_skill_to_memory)
        self.register(self.search_skills)

    def add_skill_to_memory(self, skill_profile_json: str) -> str:
        """
        Adds a skill profile to Supermemory.
        :param skill_profile_json: The JSON string of the SkillProfile.
        """
        try:
            # Use memories.add() as per Supermemory SDK
            response = self.client.memories.add(
                content=skill_profile_json
            )
            return f"Successfully added skill to memory. ID: {getattr(response, 'id', 'unknown')}"
        except Exception as e:
            return f"Error adding to supermemory: {str(e)}"

    def search_skills(self, query: str) -> str:
        """
        Searches Supermemory for relevant skills based on a query.
        :param query: The search query (e.g., "AI agent expertise").
        """
        try:
            response = self.client.memories.search(
                query=query
            )
            # Assuming response is a list of memories
            results = []
            for memory in getattr(response, 'memories', []):
                results.append(memory.content)
            return "\n---\n".join(results) if results else "No relevant skills found."
        except Exception as e:
            return f"Error searching supermemory: {str(e)}"

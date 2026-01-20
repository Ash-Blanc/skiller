"""
Skill Knowledge Base using LanceDB for RAG-enhanced skill retrieval.
"""
import os
from typing import Optional
from agno.knowledge.knowledge import Knowledge
from agno.knowledge.embedder.mistral import MistralEmbedder
from agno.vectordb.lancedb import LanceDb
from agno.vectordb.search import SearchType


def get_skill_knowledge(
    db_path: str = "data/skill_db",
    table_name: str = "skills",
    search_type: SearchType = SearchType.hybrid,
    max_results: int = 5,
) -> Knowledge:
    """
    Initialize the skill knowledge base with LanceDB.
    
    Args:
        db_path: Path to store the LanceDB database
        table_name: Name of the table in LanceDB
        search_type: Type of search (hybrid, vector, or keyword)
        max_results: Maximum number of results to return
        
    Returns:
        Knowledge: Configured knowledge base instance
    """
    # Ensure the data directory exists
    os.makedirs(db_path, exist_ok=True)
    
    # Initialize LanceDB with Mistral embeddings
    vector_db = LanceDb(
        table_name=table_name,
        uri=db_path,
        embedder=MistralEmbedder(),  # Uses MISTRAL_API_KEY from env
        search_type=search_type,
    )
    
    return Knowledge(
        vector_db=vector_db,
        max_results=max_results,
    )


# Singleton instance for reuse
_skill_knowledge: Optional[Knowledge] = None


def get_shared_skill_knowledge() -> Knowledge:
    """
    Get a shared singleton instance of the skill knowledge base.
    This prevents recreating the knowledge base for each operation.
    """
    global _skill_knowledge
    if _skill_knowledge is None:
        _skill_knowledge = get_skill_knowledge()
    return _skill_knowledge

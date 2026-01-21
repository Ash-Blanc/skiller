import sys
import os
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

load_dotenv()

from app.knowledge.skill_knowledge import get_skill_knowledge
from mistralai.utils.retries import RetryConfig

def verify_retry_config():
    print("Verifying embedder configuration...")
    knowledge = get_skill_knowledge()
    embedder = knowledge.vector_db.embedder
    
    # Access the client (this triggers creation if lazily loaded, but we passed it manually)
    client = embedder.client
    
    # Inspect configuration
    retry_config = client.sdk_configuration.retry_config
    
    if not retry_config:
        print("❌ FAIL: No retry config found!")
        return
    
    if not isinstance(retry_config, RetryConfig):
        print(f"❌ FAIL: retry_config is not RetryConfig instance: {type(retry_config)}")
        return
        
    print(f"✅ Retry Config Strategy: {retry_config.strategy}")
    print(f"✅ Retry Config Backoff Initial: {retry_config.backoff.initial_interval}")
    
    # Verify 429 is handled (we know embeddings.py handles it if retry_config is set)
    # We can't check 'status_codes' on RetryConfig directly as it's separate in Retries class,
    # but the presence of RetryConfig ensures 429 is retried in embeddings.py
    
    print("\nTesting API call...")
    try:
        embedding = embedder.get_embedding("test")
        if embedding and len(embedding) > 0:
            print("✅ API Call Successful")
            print(f"   Embedding length: {len(embedding)}")
        else:
            print("❌ FAIL: API Call returned empty/None")
    except Exception as e:
        print(f"❌ FAIL: API Call raised exception: {e}")

if __name__ == "__main__":
    verify_retry_config()

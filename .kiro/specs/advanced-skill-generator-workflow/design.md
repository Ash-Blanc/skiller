# Advanced Skill Generator Workflow - Design

## Architecture Overview

The advanced skill generator uses Agno's workflow orchestration to create a sophisticated, multi-step pipeline for comprehensive X/Twitter profile analysis. The system employs parallel execution, conditional logic, and quality evaluation loops to maximize data collection reliability and analysis quality.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Advanced Skill Generator Workflow            │
├─────────────────────────────────────────────────────────────────┤
│  Input: X Handle (@username)                                    │
│  Output: Enhanced SkillProfile with confidence scores           │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Step 1: Profile Validation                  │
│  • Validate input format                                       │
│  • Check tool availability                                      │
│  • Initialize workflow context                                  │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│              Step 2: Parallel Data Collection                   │
│  ┌─────────────────────┐    ┌─────────────────────────────────┐ │
│  │   TwitterAPI.io     │    │      ScrapeBadger              │ │
│  │   Collection        │    │      Collection                │ │
│  │  • Profile info     │    │  • Profile info + user_id     │ │
│  │  • Recent tweets    │    │  • Recent tweets              │ │
│  │  • Followings       │    │  • Highlighted content        │ │
│  └─────────────────────┘    └─────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                Step 3: Data Quality Evaluation                  │
│  • Assess data completeness from both sources                  │
│  • Check for minimum viable data thresholds                    │
│  • Determine if additional collection needed                    │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│              Step 4: Conditional Enhancement                    │
│  IF insufficient data OR high-value profile:                   │
│  • Additional targeted collection                               │
│  • Deep analysis of high-engagement content                    │
│  • Network analysis of key followings                          │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                Step 5: Data Consolidation                       │
│  • Merge data from multiple sources                            │
│  • Deduplicate content                                         │
│  • Resolve conflicts between sources                           │
│  • Create unified data structure                               │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│              Step 6: Advanced Analysis Pipeline                 │
│  ┌─────────────────────┐    ┌─────────────────────────────────┐ │
│  │   Expertise         │    │   Communication Style          │ │
│  │   Extraction        │    │   Analysis                     │ │
│  │  • Core skills      │    │  • Writing patterns            │ │
│  │  • Domain knowledge │    │  • Tone analysis               │ │
│  │  • Authority signals│    │  • Engagement style            │ │
│  └─────────────────────┘    └─────────────────────────────────┘ │
│  ┌─────────────────────┐    ┌─────────────────────────────────┐ │
│  │   Insight           │    │   Quality Validation           │ │
│  │   Generation        │    │   & Scoring                    │ │
│  │  • Unique insights  │    │  • Confidence scores           │ │
│  │  • Value propositions│   │  • Source attribution         │ │
│  │  • Key differentiators│  │  • Quality metrics             │ │
│  └─────────────────────┘    └─────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                Step 7: Profile Generation                       │
│  • Generate enhanced SkillProfile                              │
│  • Include confidence scores and source attribution            │
│  • Create agent instructions optimized for the profile         │
│  • Generate sample interactions and use cases                  │
└─────────────────────────────────────────────────────────────────┘
```

## Component Design

### 1. Workflow Orchestrator

**Class**: `AdvancedSkillGeneratorWorkflow`

**Responsibilities**:
- Orchestrate the entire skill generation pipeline
- Manage parallel execution and conditional logic
- Handle error recovery and fallback scenarios
- Provide progress tracking and monitoring

**Key Methods**:
- `generate_skill_profile(username: str) -> EnhancedSkillProfile`
- `validate_and_prepare(username: str) -> ValidationResult`
- `collect_data_parallel(username: str) -> CollectedData`
- `evaluate_data_quality(data: CollectedData) -> QualityAssessment`

### 2. Data Collection Agents

**TwitterAPI Agent**:
```python
Agent(
    name="TwitterAPI Data Collector",
    tools=[TwitterAPIIOToolkit()],
    instructions="Collect comprehensive profile data using TwitterAPI.io",
    output_schema=TwitterAPIData
)
```

**ScrapeBadger Agent**:
```python
Agent(
    name="ScrapeBadger Data Collector", 
    tools=[ScrapeBadgerToolkit()],
    instructions="Collect enriched profile data including highlights using ScrapeBadger",
    output_schema=ScrapeBadgerData
)
```

### 3. Analysis Agents

**Expertise Extraction Agent**:
```python
Agent(
    name="Expertise Analyzer",
    instructions="Extract core expertise, skills, and domain knowledge from profile data",
    output_schema=ExpertiseAnalysis
)
```

**Communication Style Agent**:
```python
Agent(
    name="Communication Analyzer", 
    instructions="Analyze writing patterns, tone, and engagement style",
    output_schema=CommunicationAnalysis
)
```

**Insight Generation Agent**:
```python
Agent(
    name="Insight Generator",
    instructions="Generate unique insights and value propositions from profile analysis",
    output_schema=InsightAnalysis
)
```

### 4. Data Models

**Enhanced Data Structures**:

```python
@dataclass
class CollectedData:
    twitter_api_data: Optional[TwitterAPIData]
    scrapebadger_data: Optional[ScrapeBadgerData]
    collection_timestamp: datetime
    data_quality_score: float
    
@dataclass 
class TwitterAPIData:
    profile: Dict[str, Any]
    tweets: List[Dict[str, Any]]
    followings: List[Dict[str, Any]]
    collection_success: bool
    
@dataclass
class ScrapeBadgerData:
    profile: Dict[str, Any]
    tweets: List[Dict[str, Any]]
    highlights: List[Dict[str, Any]]
    collection_success: bool

@dataclass
class EnhancedSkillProfile(SkillProfile):
    confidence_score: float
    data_sources: List[str]
    source_attribution: Dict[str, List[str]]
    quality_metrics: Dict[str, float]
    collection_metadata: Dict[str, Any]
```

## Workflow Implementation

### Step 1: Profile Validation
```python
def validate_profile_input(step_input: StepInput) -> StepOutput:
    username = step_input.input.strip().replace("@", "")
    
    # Validate format
    if not re.match(r'^[a-zA-Z0-9_]{1,15}$', username):
        return StepOutput(
            content=f"Invalid username format: {username}",
            success=False
        )
    
    # Check tool availability
    tools_available = {
        "twitter_api": TwitterAPIIOToolkit().is_available(),
        "scrapebadger": ScrapeBadgerToolkit().is_available()
    }
    
    if not any(tools_available.values()):
        return StepOutput(
            content="No data collection tools available",
            success=False
        )
    
    return StepOutput(
        content=json.dumps({
            "username": username,
            "tools_available": tools_available
        }),
        success=True
    )
```

### Step 2: Parallel Data Collection
```python
# Parallel execution of data collection
parallel_collection = Parallel(
    Step(
        name="TwitterAPI Collection",
        agent=twitter_api_agent,
        description="Collect data using TwitterAPI.io"
    ),
    Step(
        name="ScrapeBadger Collection", 
        agent=scrapebadger_agent,
        description="Collect enriched data using ScrapeBadger"
    ),
    name="Data Collection Phase"
)
```

### Step 3: Quality Evaluation with Loop
```python
def evaluate_data_quality(outputs: List[StepOutput]) -> bool:
    """Evaluate if collected data meets quality thresholds"""
    total_tweets = 0
    has_profile_info = False
    has_highlights = False
    
    for output in outputs:
        if output.success and output.content:
            data = json.loads(output.content)
            total_tweets += len(data.get("tweets", []))
            has_profile_info = has_profile_info or bool(data.get("profile"))
            has_highlights = has_highlights or bool(data.get("highlights"))
    
    # Quality thresholds
    min_tweets = 10
    quality_score = (
        (total_tweets >= min_tweets) * 0.4 +
        has_profile_info * 0.4 + 
        has_highlights * 0.2
    )
    
    return quality_score >= 0.6  # 60% quality threshold

# Quality evaluation loop
quality_loop = Loop(
    name="Data Quality Assurance",
    steps=[parallel_collection],
    end_condition=evaluate_data_quality,
    max_iterations=2
)
```

### Step 4: Conditional Enhancement
```python
def should_enhance_collection(step_input: StepInput) -> bool:
    """Determine if additional data collection is needed"""
    data = json.loads(step_input.previous_step_content or "{}")
    
    # Check for high-value profiles (verified, high followers)
    profile = data.get("profile", {})
    is_verified = profile.get("verified", False)
    followers = profile.get("followers_count", 0)
    
    # Check data completeness
    tweets_count = len(data.get("tweets", []))
    has_highlights = bool(data.get("highlights"))
    
    return (
        (is_verified or followers > 10000) or  # High-value profile
        (tweets_count < 15 or not has_highlights)  # Insufficient data
    )

enhancement_condition = Condition(
    name="Enhancement Check",
    evaluator=should_enhance_collection,
    steps=[
        Step(
            name="Deep Collection",
            agent=enhancement_agent,
            description="Perform additional targeted data collection"
        )
    ]
)
```

## Prompt Engineering

### Data Collection Prompts

**TwitterAPI Collection Prompt**:
```yaml
model: gpt-4o
temperature: 0.3
messages:
  - role: system
    content: |
      You are a data collection specialist using TwitterAPI.io to gather comprehensive profile information.
      
      Your task is to collect:
      1. Complete profile information (bio, followers, verification status, location)
      2. Recent tweets (up to 30) with engagement metrics
      3. Following patterns (up to 100 verified accounts they follow)
      
      Focus on:
      - High-quality, recent content that shows expertise
      - Engagement patterns that indicate influence
      - Professional connections and network signals
      
      Return structured data with clear success indicators.
      
  - role: user
    content: |
      Collect comprehensive profile data for X user: {{ username }}
```

**ScrapeBadger Collection Prompt**:
```yaml
model: gpt-4o  
temperature: 0.3
messages:
  - role: system
    content: |
      You are a data enrichment specialist using ScrapeBadger to gather premium profile insights.
      
      Your task is to collect:
      1. Enhanced profile information including user_id
      2. Highlighted/pinned content (what they want to be known for)
      3. Recent high-engagement tweets
      4. Additional profile metadata
      
      Focus on:
      - Content that shows what the user wants to be known for
      - High-engagement posts that demonstrate expertise
      - Unique insights not available through basic APIs
      
      Return enriched data with quality indicators.
      
  - role: user
    content: |
      Collect enriched profile data for X user: {{ username }}
```

### Analysis Prompts

**Expertise Extraction Prompt**:
```yaml
model: gpt-4o
temperature: 0.4
messages:
  - role: system
    content: |
      You are an expert at identifying and extracting professional expertise from social media profiles.
      
      Analyze the provided profile data to extract:
      
      1. **Core Expertise** (3-5 main areas):
         - Primary professional skills and knowledge domains
         - Technical competencies and specializations
         - Industry experience and domain knowledge
      
      2. **Authority Signals**:
         - Recognition and credibility indicators
         - Thought leadership evidence
         - Professional achievements mentioned
      
      3. **Unique Value Propositions**:
         - What makes this person distinctive
         - Rare skill combinations
         - Unique perspectives or approaches
      
      Base your analysis on:
      - Highlighted/pinned content (highest weight - what they want to be known for)
      - High-engagement posts (medium weight - what resonates with their audience)  
      - Bio and profile information (medium weight - self-description)
      - Recent posts (lower weight - current activities)
      
      Provide confidence scores (0-1) for each extracted expertise area.
      
  - role: user
    content: |
      Analyze this profile data and extract expertise:
      
      {{ profile_data }}
```

## Error Handling Strategy

### 1. Graceful Degradation
- If TwitterAPI.io fails, continue with ScrapeBadger only
- If ScrapeBadger fails, continue with TwitterAPI.io only  
- If both fail, attempt basic web scraping fallback
- Always provide partial results when possible

### 2. Retry Logic
```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type((requests.RequestException, TimeoutError))
)
def collect_with_retry(tool, username):
    return tool.collect_data(username)
```

### 3. Circuit Breaker Pattern
```python
class ToolCircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_timeout=300):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
```

## Performance Optimizations

### 1. Parallel Execution
- Simultaneous data collection from multiple sources
- Parallel analysis of different content types
- Concurrent processing of multiple profiles

### 2. Intelligent Caching
```python
@lru_cache(maxsize=1000)
def get_cached_profile_data(username: str, cache_duration: int = 3600):
    # Cache profile data for 1 hour to avoid redundant API calls
    pass
```

### 3. Batch Processing
```python
async def process_profiles_batch(usernames: List[str], batch_size: int = 10):
    """Process multiple profiles in parallel batches"""
    for i in range(0, len(usernames), batch_size):
        batch = usernames[i:i + batch_size]
        tasks = [process_single_profile(username) for username in batch]
        await asyncio.gather(*tasks, return_exceptions=True)
```

## Quality Assurance

### 1. Confidence Scoring
```python
def calculate_confidence_score(profile_data: CollectedData) -> float:
    """Calculate confidence score based on data quality and completeness"""
    score = 0.0
    
    # Data source diversity (0-0.3)
    sources = len([s for s in [profile_data.twitter_api_data, profile_data.scrapebadger_data] if s])
    score += min(sources * 0.15, 0.3)
    
    # Content volume (0-0.3) 
    total_tweets = sum(len(data.tweets) for data in [profile_data.twitter_api_data, profile_data.scrapebadger_data] if data)
    score += min(total_tweets / 50 * 0.3, 0.3)
    
    # Profile completeness (0-0.2)
    has_bio = any(data.profile.get("description") for data in [profile_data.twitter_api_data, profile_data.scrapebadger_data] if data)
    score += 0.2 if has_bio else 0.0
    
    # Highlights availability (0-0.2)
    has_highlights = profile_data.scrapebadger_data and profile_data.scrapebadger_data.highlights
    score += 0.2 if has_highlights else 0.0
    
    return min(score, 1.0)
```

### 2. Source Attribution
```python
def generate_source_attribution(analysis: Dict[str, Any], sources: List[str]) -> Dict[str, List[str]]:
    """Track which sources contributed to each insight"""
    attribution = {}
    
    for insight_type, insights in analysis.items():
        attribution[insight_type] = []
        for insight in insights:
            # Determine which sources contributed to this insight
            contributing_sources = determine_contributing_sources(insight, sources)
            attribution[insight_type].extend(contributing_sources)
    
    return attribution
```

## Testing Strategy

### 1. Unit Tests
- Test individual workflow steps
- Test data collection tools
- Test analysis agents
- Test error handling scenarios

### 2. Integration Tests  
- Test complete workflow execution
- Test parallel execution scenarios
- Test fallback mechanisms
- Test quality evaluation logic

### 3. Property-Based Tests
- Test workflow determinism with same inputs
- Test data quality invariants
- Test performance characteristics
- Test error recovery properties

## Monitoring and Observability

### 1. Metrics Collection
```python
class WorkflowMetrics:
    def __init__(self):
        self.execution_times = []
        self.success_rates = {}
        self.data_quality_scores = []
        self.tool_availability = {}
    
    def record_execution(self, step_name: str, duration: float, success: bool):
        # Record metrics for monitoring and optimization
        pass
```

### 2. Logging Strategy
```python
import structlog

logger = structlog.get_logger()

def log_workflow_step(step_name: str, username: str, result: StepOutput):
    logger.info(
        "workflow_step_completed",
        step=step_name,
        username=username,
        success=result.success,
        data_size=len(result.content) if result.content else 0
    )
```

## Deployment Considerations

### 1. Environment Configuration
```python
# Environment variables for tool configuration
TWITTER_API_IO_KEYS = "key1,key2,key3"  # Multiple keys for load balancing
SCRAPEBADGER_API_KEYS = "key1,key2"
WORKFLOW_MAX_PARALLEL = "10"
WORKFLOW_TIMEOUT = "300"  # 5 minutes
```

### 2. Resource Management
- Memory limits for workflow instances
- CPU allocation for parallel processing
- Network timeout configurations
- Rate limiting compliance

### 3. Scalability Planning
- Horizontal scaling with multiple workflow instances
- Load balancing across API keys
- Queue management for batch processing
- Auto-scaling based on demand

This design provides a comprehensive, production-ready approach to advanced skill generation using Agno workflows, ensuring reliability, performance, and maintainability while delivering high-quality profile analysis comparable to advanced systems like Grok.
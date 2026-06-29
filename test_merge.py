from reddit_marketing.agents.strategy import plan_strategy
from reddit_marketing.llm_handler import get_llm
import os
from dotenv import load_dotenv
from reddit_marketing.config import ProjectBrief

load_dotenv()
api_key = os.getenv("GROQ_API_KEY")
llm = get_llm("Groq", "llama-3.3-70b-versatile", api_key)
brief = ProjectBrief(brand_name="Test", description="Test", target_audience="Test", features=[], voice_tone="Test")

scored_opportunities = [
    {
        "url": "https://www.reddit.com/r/fitness/",
        "title": "Create a post in r/fitness",
        "subreddit": "fitness",
        "opportunity_type": "new_post"
    }
]

res = plan_strategy(llm, brief, scored_opportunities)
print(res)

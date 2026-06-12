from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_groq import ChatGroq

from dotenv import load_dotenv
load_dotenv()
import asyncio
import os
async def main():
    client=MultiServerMCPClient(
        {
            "math":{
                "command": os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".venv", "bin", "python")),
                "args":[os.path.join(os.path.dirname(__file__), "mathserver.py")], 
                "transport":"stdio",
            
            
            },
            "weather": {
                "url": "http://localhost:8000/mcp", 
                "transport": "streamable_http",
            }

        }
    )
    os.environ["GROQ_API_KEY"]=os.getenv("GROQ_API_KEY")

    tools=await client.get_tools()
    model=ChatGroq(model="llama-3.1-8b-instant")
    agent=create_react_agent(
        model,tools
    )

    math_response = await agent.ainvoke(
        {"messages": [{"role": "user", "content": "First add 3 and 5. Then multiply the result by 12."}]}
    )

    print("Math response:", math_response['messages'][-1].content)

    weather_response = await agent.ainvoke(
        {"messages": [{"role": "user", "content": "Use the provided 'get_weather' tool to find the weather in California. Do NOT use brave_search. Do NOT use any tools that are not explicitly provided to you."}]}
    )
    print("Weather response:", weather_response['messages'][-1].content)

asyncio.run(main())
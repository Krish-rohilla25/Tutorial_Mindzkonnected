from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI


GROQ_DEFAULT_MODEL = "qwen/qwen3-32b"
GEMINI_DEFAULT_MODEL = "gemini-2.5-flash"

GROQ_MODELS = [
    "qwen/qwen3-32b",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
]

GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-3.5-flash",
]


def get_llm(provider, model_name, api_key):
    """
    Return the correct LangChain LLM object based on the provider.

    provider: 'Groq' or 'Gemini'
    model_name: the model string (e.g. 'llama3-8b-8192')
    api_key: the API key the user entered in the UI

    Returns a LangChain chat model.
    """
    if provider == "Groq":
        llm = ChatGroq(
            model=model_name,
            api_key=api_key,
            temperature=0,
        )
        return llm

    elif provider == "Gemini":
        llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            temperature=0,
        )
        return llm

    else:
        raise ValueError(f"Unknown provider: {provider}. Use 'Groq' or 'Gemini'.")

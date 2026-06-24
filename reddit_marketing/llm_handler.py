from langchain.chat_models import init_chat_model


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

DEFAULT_PROVIDER = "Groq"
DEFAULT_MODEL = "qwen/qwen3-32b"


def get_llm(provider, model_name, api_key):
    """
    Return a LangChain chat model for the given provider.

    provider:   'Groq' or 'Gemini'
    model_name: e.g. 'qwen/qwen3-32b'
    api_key:    the user's API key
    """
    if provider not in ["Groq", "Gemini"]:
        raise ValueError(f"Unknown provider: {provider}. Use 'Groq' or 'Gemini'.")

    model_provider = "groq" if provider == "Groq" else "google_genai"
    return init_chat_model(
        model=model_name,
        model_provider=model_provider,
        api_key=api_key,
        temperature=0.7,
    )

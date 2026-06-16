from langchain_core.messages import HumanMessage, SystemMessage


def build_prompt(question, context_chunks):
    """
    Build the messages list that will be sent to the LLM.

    The system message instructs the model to only use the provided context.
    The human message contains the context and the user's question.

    question: the user's question string
    context_chunks: list of text strings retrieved from the vector store

    Returns a list of LangChain message objects.
    """
    context = "\n\n".join(context_chunks)

    system_message = SystemMessage(
        content=(
            "You are a helpful assistant that answers questions based only on "
            "the provided document context. If the answer is not in the context, "
            "say that you could not find the answer in the document. "
            "Give clear, direct, textual answers. Do not make things up."
        )
    )

    human_message = HumanMessage(
        content=(
            f"Context from the document:\n\n{context}\n\n"
            f"Question: {question}"
        )
    )

    return [system_message, human_message]


def get_answer(llm, question, context_chunks):
    """
    Run the RAG chain: build a prompt from the question and retrieved context,
    call the LLM, and return the answer as a string.

    llm: a LangChain chat model
    question: string
    context_chunks: list of strings from the vector store

    Returns the answer string.
    """
    messages = build_prompt(question, context_chunks)
    response = llm.invoke(messages)

    # Some newer Gemini models return content as a list of parts
    content = response.content
    if isinstance(content, list):
        return "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )

    return content


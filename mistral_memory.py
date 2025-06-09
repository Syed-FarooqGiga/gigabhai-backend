import logging
from mistral_handler import get_mistral_response

logger = logging.getLogger(__name__)

async def summarize_chat_memory(messages: list) -> list:
    """
    Use Mistral to select and compress the 10 most important messages from the last 100 messages.
    Returns a list of summarized/important messages.
    """
    summarization_prompt = {
        "role": "system",
        "content": (
            "You are a helpful assistant. The following is a conversation history. "
            "Select the 10 most important messages (user or assistant) that best capture the context, "
            "and summarize or compress them if possible. ALWAYS include any key facts, numbers, measurements, medical details, symptoms, diagnoses, or user questions. "
            "NEVER omit any numbers, measurements, or important details about the user's health, medical conditions, or personal facts, and every important detail which can be used to answer the user's questions "
            "Return the result as a list of message objects in JSON, each with a 'role' (user or assistant) and 'content'. Do not include any explanations. "
            "If you can merge similar messages, do so."
        )
    }
    # Only keep USER messages for summarization (do not include bot responses)
    formatted_msgs = [
        {"role": m["role"], "content": m["content"]}
        for m in messages if "role" in m and "content" in m and m["role"] == "user"
    ]
    # Prepend the summarization prompt
    summarization_input = [summarization_prompt] + formatted_msgs
    try:
        summary_response = await get_mistral_response(summarization_input)
        logger.info(f"Raw summary response from Mistral: {summary_response}")  # Log for debugging
        import json
        # Guard: Only parse if response looks like a JSON list
        if not summary_response or not summary_response.strip().startswith("["):
            logger.warning("Summary response is empty or not a JSON list, using fallback.")
            logger.info(f"Fallback context (last 20 messages): {formatted_msgs[-20:]}")
            return formatted_msgs[-20:]  # fallback: last 20 messages
        try:
            summary = json.loads(summary_response)
        except Exception as parse_err:
            logger.warning(f"Failed to parse summary as JSON: {parse_err}")
            summary = None
        # Validate summary is a list of dicts with role/content and not empty
        if isinstance(summary, list) and summary and all(
            isinstance(m, dict) and "role" in m and "content" in m for m in summary
        ):
            return summary
        else:
            logger.warning("Summarization output not in expected format or empty, using fallback.")
            return formatted_msgs[-20:]  # fallback: last 20 messages
    except Exception as e:
        logger.error(f"Failed to summarize chat memory: {e}")
        return formatted_msgs[-20:]  # fallback: last 20 messages

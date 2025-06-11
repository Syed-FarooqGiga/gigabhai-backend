import httpx
from config import MISTRAL_API_KEY, MISTRAL_API_URL

async def get_mistral_response(messages: list):
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Separate system messages from conversation history
    system_messages = [msg for msg in messages if msg.get('role') == 'system']
    conversation_messages = [msg for msg in messages if msg.get('role') != 'system']
    
    # Get the latest user message (should be the last message in the list)
    latest_user_message = next(
        (msg for msg in reversed(conversation_messages) if msg.get('role') == 'user'),
        None
    )
    
    # If we have a system message, use it as context
    system_prompt = ""
    if system_messages:
        system_prompt = "\n".join([msg.get('content', '') for msg in system_messages if msg.get('content')])
    
    # Prepare the final messages list with clear instructions
    final_messages = []
    
    # Add system prompt if it exists
    if system_prompt:
        final_messages.append({
            "role": "system",
            "content": system_prompt
        })
    
    # Add context from conversation history (excluding the latest user message)
    if len(conversation_messages) > 1:
        context_messages = conversation_messages[:-1]  # All messages except the last one
        final_messages.append({
            "role": "system",
            "content": "Here is the conversation history for context. Only reference these messages if they are relevant to the current question:\n" + 
                       "\n".join([f"{msg.get('role').capitalize()}: {msg.get('content')}" for msg in context_messages])
        })
    
    # Add the latest user message with clear instructions
    if latest_user_message:
        final_messages.append({
            "role": "user",
            "content": f"Current message to respond to (only respond to this, only use context if needed): {latest_user_message.get('content')}"
        })
    
    # Prepare the payload
    payload = {
        "model": "mistral-large-latest",
        "messages": final_messages,
        "temperature": 0.7,
        "max_tokens": 500,
        "top_p": 0.9,
        "frequency_penalty": 0.5,
        "presence_penalty": 0.5
    }
    import time
    max_retries = 3
    delay = 0.5  # seconds
    max_total_time = 25.0  # seconds
    start_time = time.monotonic()
    import logging
    logger = logging.getLogger("mistral_handler")
    for attempt in range(max_retries):
        try:
            # If we've spent too long, abort
            if time.monotonic() - start_time > max_total_time:
                return "Sorry, the AI is taking too long to respond. Please try again later."
            call_start = time.monotonic()
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(MISTRAL_API_URL, headers=headers, json=payload)
            call_duration = time.monotonic() - call_start
            logger.info(f"Mistral API call took {call_duration:.2f} seconds (attempt {attempt+1})")
            # Check for error responses
            if response.status_code == 429:
                if attempt < max_retries - 1 and (time.monotonic() - start_time + delay) < max_total_time:
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, max_total_time - (time.monotonic() - start_time))
                    continue
                return "Rate limit exceeded. Please try again in a few seconds."
            elif response.status_code != 200:
                error_msg = response.text
                import logging
                logging.getLogger("mistral_handler").error(f"Mistral API error {response.status_code}: {error_msg}")
                return f"Error from Mistral API: {error_msg}"
            # Parse successful response and extract only the assistant's message
            response_json = response.json()
            # Ensure we return a clean response format
            if 'choices' in response_json and len(response_json['choices']) > 0:
                # Extract the message content from the first choice
                message = response_json['choices'][0].get('message', {})
                # Return just the content if it's an assistant message
                if message.get('role') == 'assistant':
                    return message.get('content', '')
                return message.get('content', '') if message else ''
            return ""
        except asyncio.TimeoutError:
            return "Sorry, the AI is taking too long to respond. Please try again later."
        except Exception as e:
            logger.error(f"Error in get_mistral_response: {str(e)}", exc_info=True)
            return "Sorry, the AI is taking too long to respond. Please try again later."
    return "Sorry, the AI is taking too long to respond. Please try again later."

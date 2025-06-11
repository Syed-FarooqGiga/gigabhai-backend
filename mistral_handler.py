import httpx
from config import MISTRAL_API_KEY, MISTRAL_API_URL

async def get_mistral_response(messages: list):
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }
    # Optimize messages and ensure proper formatting
    optimized_messages = []
    seen_messages = set()  # To avoid duplicate messages
    
    for msg in messages:
        if not isinstance(msg, dict) or 'role' not in msg or 'content' not in msg:
            continue
            
        # Clean and format the content
        content = str(msg['content']).strip()
        if not content:  # Skip empty messages
            continue
            
        # Create a unique key for this message to detect duplicates
        msg_key = f"{msg['role']}:{content[:100]}"
        if msg_key in seen_messages:
            continue
            
        seen_messages.add(msg_key)
        optimized_messages.append({
            'role': msg['role'],
            'content': content
        })
    
    # Ensure we don't exceed context window
    max_messages = 30  # Keep last 30 messages for context
    if len(optimized_messages) > max_messages:
        optimized_messages = optimized_messages[-max_messages:]
    
    payload = {
        "model": "mistral-large-latest",
        "messages": optimized_messages,
        "temperature": 0.7,  # Slightly more creative
        "max_tokens": 50000000,   # Limit response length
        "top_p": 0.9,
        "frequency_penalty": 0.5,  # Reduce repetition
        "presence_penalty": 0.5   # Encourage topic variety
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

import httpx
from config import MISTRAL_API_KEY, MISTRAL_API_URL

async def get_mistral_response(messages: list):
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }
    # Optimize messages: strip whitespace from content, only keep 'role' and 'content'
    optimized_messages = []
    for msg in messages:
        if isinstance(msg, dict) and 'role' in msg and 'content' in msg:
            optimized_messages.append({
                'role': msg['role'],
                'content': str(msg['content']).strip()
            })
    payload = {
        "model": "mistral-small",  # Changed to a faster model
        "messages": optimized_messages
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
            # Parse successful response
            response_json = response.json()
            if 'choices' not in response_json or not response_json['choices']:
                return "Invalid response from Mistral API"
            return response_json["choices"][0]["message"]["content"]
        except httpx.ReadTimeout:
            return "Sorry, the AI is taking too long to respond. Please try again later."
        except Exception as e:
            if attempt < max_retries - 1 and (time.monotonic() - start_time + delay) < max_total_time:
                await asyncio.sleep(delay)
                delay = min(delay * 2, max_total_time - (time.monotonic() - start_time))
                continue
            return f"Error communicating with Mistral API: {str(e)}"
    return "Sorry, the AI is taking too long to respond. Please try again later."

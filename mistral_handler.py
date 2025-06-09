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
        "model": "mistral-medium",
        "messages": optimized_messages
    }
    max_retries = 5
    delay = 1  # seconds
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(MISTRAL_API_URL, headers=headers, json=payload)
                # Check for error responses
                if response.status_code == 429:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(delay)
                        delay *= 2  # exponential backoff
                        continue
                    return "Rate limit exceeded. Please try again in a few seconds."
                elif response.status_code != 200:
                    error_msg = response.json().get('error', {}).get('message', 'Unknown error occurred')
                    return f"Error from Mistral API: {error_msg}"
                # Parse successful response
                response_json = response.json()
                if 'choices' not in response_json or not response_json['choices']:
                    return "Invalid response from Mistral API"
                return response_json["choices"][0]["message"]["content"]
        except httpx.ReadTimeout:
            return "Sorry, the AI is taking too long to respond. Please try again later."
        except Exception as e:
            if attempt < max_retries - 1:
                await asyncio.sleep(delay)
                delay *= 2
                continue
            return f"Error communicating with Mistral API: {str(e)}"
    return f"An error occurred while processing your request: Unknown error"

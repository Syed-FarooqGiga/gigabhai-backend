import httpx
from config import MISTRAL_API_KEY, MISTRAL_API_URL

async def get_mistral_response(messages: list):
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "mistral-medium",
        "messages": messages
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(MISTRAL_API_URL, headers=headers, json=payload)
            
            # Check for error responses
            if response.status_code == 429:
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
        return f"An error occurred while processing your request: {str(e)}"

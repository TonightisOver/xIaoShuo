import requests
import json
import time

URL = "http://127.0.0.1:15721/v1/messages"
HEADERS = {
    "x-api-key": "PROXY_MANAGED",
    "anthropic-version": "2023-06-01",
    "content-type": "application/json",
    "anthropic-beta": "prompt-caching-2024-07-31" # For prompt caching
}

# 1. Test Prompt Caching and Truncation
payload = {
    "model": "glm-5.2",
    "max_tokens": 4096,
    "system": [
        {
            "type": "text",
            "text": "You are a helpful assistant. " * 500, # Big context to cache
            "cache_control": {"type": "ephemeral"}
        }
    ],
    "messages": [
        {"role": "user", "content": "Please write a 2000-word essay about the history of artificial intelligence, including detailed timelines and key figures. Do not stop until you have provided a very long and detailed response."}
    ],
    "stream": True
}

print("Sending request to proxy...")
start_time = time.time()
try:
    response = requests.post(URL, headers=HEADERS, json=payload, stream=True)
    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        print(response.text)
    else:
        print("Connected, reading stream...")
        token_count = 0
        cache_creation = 0
        cache_read = 0
        
        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        if data.get("type") == "message_start":
                            usage = data.get("message", {}).get("usage", {})
                            cache_creation = usage.get("cache_creation_input_tokens", 0)
                            cache_read = usage.get("cache_read_input_tokens", 0)
                            print(f"Initial Usage: {usage}")
                        elif data.get("type") == "content_block_delta":
                            token_count += 1
                        elif data.get("type") == "message_stop":
                            print("\n\nStream finished properly with message_stop.")
                        elif data.get("type") == "error":
                            print(f"\n\nAPI ERROR mid-stream: {data}")
                    except json.JSONDecodeError:
                        print(f"\nMalformed JSON in stream: {data_str}")
        
        duration = time.time() - start_time
        print(f"\n--- Test Results ---")
        print(f"Time taken: {duration:.2f} seconds")
        print(f"Estimated Output Tokens: {token_count}")
        print(f"Cache Creation Tokens: {cache_creation}")
        print(f"Cache Read Tokens: {cache_read}")
        print(f"If token count is very low or stream didn't finish properly, there is a proxy truncation issue.")
except requests.exceptions.RequestException as e:
    print(f"Connection error: {e}")

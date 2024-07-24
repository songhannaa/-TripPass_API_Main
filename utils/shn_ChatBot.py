import openai
import json
from serpapi import GoogleSearch
import os

# BASE_DIR 설정을 수정하여 secret.json 파일 경로가 정확한지 확인
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
secret_file = os.path.join(BASE_DIR, '../secret.json')

# secret.json 파일에서 API 키를 읽어옴
with open(secret_file) as f:
    secrets = json.loads(f.read())

def get_secret(setting, secrets=secrets):
    try:
        return secrets[setting]
    except KeyError:
        error_msg = "Set the {} environment variable".format(setting)
        raise KeyError(error_msg)

# SerpAPI 키 가져오기
SERP_API_KEY = get_secret("SERP_API_KEY")

def get_current_weather(location, unit="fahrenheit"):
    """Get the current weather in a given location"""
    weather_info = {
        "location": location,
        "temperature": "72",
        "unit": unit,
        "forecast": ["sunny", "windy"],
    }
    return json.dumps(weather_info)

def getSerpPlace(query):
    """Get place information using Google Maps API and save to a JSON file"""
    params = {
        "engine": "google_maps",
        "q": query,
        "hl": "en",
        "api_key": SERP_API_KEY
    }
    search = GoogleSearch(params)
    results = search.get_dict()

    if 'error' in results:
        return json.dumps({"error": results['error']})

    if results:
        # JSON 파일로 결과 저장
        output_file = os.path.join(BASE_DIR, 'serp_results.json')
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=4)
        return "저장되었습니다."
    else:
        return json.dumps({"error": "No results found"})

def run_conversation(query):
    messages = [{"role": "user", "content": query}]
    functions = [
        {
            "name": "getSerpPlace",
            "description": "Get the serp place",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                },
                "required": ["query"],
            }
        },
        {
            "name": "get_current_weather",
            "description": "Get the current weather",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string"},
                    "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
                },
                "required": ["location"],
            }
        }
    ]

    try:
        # 최신 모델을 사용하여 응답을 생성합니다.
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=messages,
            functions=functions,
            function_call="auto",
        )
    except Exception as e:
        return f"Error occurred while generating response: {e}"

    response_message = response["choices"][0]["message"]

    # Step 2: GPT에서 함수 호출을 하라고 했는지 확인합니다.
    if response_message.get("function_call"):
        # Step 3: GPT에서 호출하라고 한 함수를 실제로 호출합니다.
        available_functions = {
            "get_current_weather": get_current_weather,
            "getSerpPlace": getSerpPlace,
        }
        function_name = response_message["function_call"]["name"]
        function_to_call = available_functions[function_name]
        function_args = json.loads(response_message["function_call"]["arguments"])
        function_response = function_to_call(**function_args)

        # Step 4: 함수 호출 결과를 GPT에게 다시 전달합니다.
        messages.append(response_message)
        messages.append(
            {
                "role": "function",
                "name": function_name,
                "content": function_response,
            }
        )

        # 최대 토큰 길이를 초과하지 않도록 메시지 수를 제한합니다.
        while True:
            try:
                second_response = openai.ChatCompletion.create(
                    model="gpt-4",
                    messages=messages,
                )
                break
            except openai.error.InvalidRequestError as e:
                if "maximum context length" in str(e):
                    # 메시지를 오래된 것부터 제거하여 토큰 수 줄이기
                    messages.pop(1)
                else:
                    raise e

        final_message = second_response["choices"][0]["message"]["content"]
        return final_message if final_message.strip() != '' else "저장되었습니다."

# 사용자 쿼리를 입력 받아 시작
user_query = input("User: ")
print(run_conversation(user_query))

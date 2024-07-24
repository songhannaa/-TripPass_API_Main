import os
import json
import openai
from serpapi import GoogleSearch
from deep_translator import GoogleTranslator

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

SERP_API_KEY = get_secret("SERP_API_KEY")
OPENAI_API_KEY = get_secret("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

def call_openai_function(query: str):
    response = openai.ChatCompletion.create(
        model="gpt-4-0613",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that provides travel recommendations."},
            {"role": "user", "content": query}
        ],
        functions=[
            {
                "name": "search_places",
                "description": "Search for various types of places based on user query",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query for finding places"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "just_chat",
                "description": "Respond to general questions and provide information",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The user's general query"
                        }
                    },
                    "required": ["query"]
                }
            }
        ],
        function_call="auto"
    )
    return response

def search_places(query: str):
    # Google Search API 호출을 위한 로직
    params = {
        "engine": "google_maps",
        "q": query,
        "hl": "en",
        "api_key": SERP_API_KEY
    }
    search = GoogleSearch(params)
    results_data = search.get_dict()

    return parseSerpData(results_data)

def parseSerpData(data):
    if 'local_results' not in data:
        return []
    
    translator = GoogleTranslator(source='en', target='ko')
    parsed_results = []
    
    for idx, result in enumerate(data['local_results'], 1):
        title = result.get('title')
        rating = result.get('rating')
        address = result.get('address')
        gps_coordinates = result.get('gps_coordinates', {})
        latitude = gps_coordinates.get('latitude')
        longitude = gps_coordinates.get('longitude')
        description = result.get('description', 'No description available.')
        translated_description = translator.translate(description)

        if not address or not latitude or not longitude:
            continue

        place_data = {
            "title": title,
            "rating": rating,
            "address": address,
            "latitude": latitude,
            "longitude": longitude,
            "description": translated_description,
        }
        
        parsed_results.append(place_data)
        
        if 'price' in result:
            price = result.get('price')
            print(f"{idx}. 장소 이름: {title}\n    별점: {rating}\n    주소: {address}\n    가격: {price}\n    설명: {translated_description}\n")
        else:
            print(f"{idx}. 장소 이름: {title}\n    별점: {rating}\n    주소: {address}\n    설명: {translated_description}\n")

    return parsed_results

def just_chat(query: str):
    response = openai.ChatCompletion.create(
        model="gpt-4-0613",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": query}
        ]
    )
    return response.choices[0].message["content"]

# 사용 예제
query = "안녕"
response = call_openai_function(query)

try:
    function_call = response.choices[0].message["function_call"]
    if function_call["name"] == "search_places":
        args = json.loads(function_call["arguments"])
        search_query = args["query"]
        response = search_places(search_query)
    elif function_call["name"] == "just_chat":
        args = json.loads(function_call["arguments"])
        response = just_chat(args["query"])
except KeyError:
    response = response.choices[0].message["content"]

print(response)

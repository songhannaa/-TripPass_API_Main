import os
import json
import openai
from serpapi import GoogleSearch
from deep_translator import GoogleTranslator
from langchain.memory import ConversationBufferMemory
from langchain.schema import BaseMessage, AIMessage, HumanMessage, SystemMessage

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

# ConversationBufferMemory 초기화
if 'memory' not in globals():
    memory = ConversationBufferMemory()

def message_to_dict(msg: BaseMessage):
    if isinstance(msg, HumanMessage):
        return {"role": "user", "content": msg.content}
    elif isinstance(msg, AIMessage):
        return {"role": "assistant", "content": msg.content}
    elif isinstance(msg, SystemMessage):
        return {"role": "system", "content": msg.content}
    else:
        raise ValueError(f"Unknown message type: {type(msg)}")

def call_openai_function(query: str):
    # 대화 메모리에 사용자 입력 추가
    memory.save_context({"input": query}, {"output": ""})
    print(memory)

    # 메시지를 적절한 형식으로 변환
    messages = [
        {"role": "system", "content": "You are a helpful assistant that helps users plan their travel plans."},
    ] + [message_to_dict(msg) for msg in memory.chat_memory.messages] + [
        {"role": "user", "content": query}
    ]

    # OpenAI API 호출
    response = openai.ChatCompletion.create(
        model="gpt-4-0613",
        messages=messages,
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

    message_content = response.choices[0].message.get("content", "")
    
    try:
        function_call = response.choices[0].message["function_call"]
        if function_call["name"] == "search_places":
            args = json.loads(function_call["arguments"])
            search_query = args["query"]
            result = search_places(search_query)
            result_str = format_parsed_results(result)  # 결과를 예쁘게 포맷
            result = result_str
        elif function_call["name"] == "just_chat":
            args = json.loads(function_call["arguments"])
            result = just_chat(args["query"])
            result_str = result
        else:
            result = message_content
            result_str = result
    except KeyError:
        result = message_content
        result_str = result

    # 대화 메모리에 응답 추가
    memory.save_context({"input": query}, {"output": result_str})

    return result

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
        
    return parsed_results

def format_parsed_results(results):
    formatted_results = []
    for idx, result in enumerate(results, 1):
        formatted_results.append(
            f"{idx}. 장소 이름: {result['title']}\n"
            f"   별점: {result['rating']}\n"
            f"   주소: {result['address']}\n"
            f"   위도: {result['latitude']}\n"
            f"   경도: {result['longitude']}\n"
            f"   설명: {result['description']}\n"
        )
    return "\n".join(formatted_results)

def just_chat(query: str):
    response = openai.ChatCompletion.create(
        model="gpt-4-0613",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": query}
        ]
    )
    return response.choices[0].message["content"]

# 사용자 입력 버튼용
def search_place_details(query: str):
    params = {
        "engine": "google_maps",
        "q": query,
        "hl": "en",
        "api_key": SERP_API_KEY,
    }
    search = GoogleSearch(params)
    data = search.get_dict()
    
    translator = GoogleTranslator(source='en', target='ko')
    result = data.get('place_results', {})
    
    title = result.get('title')
    rating = result.get('rating')
    address = result.get('address')
    gps_coordinates = result.get('gps_coordinates', {})
    latitude = gps_coordinates.get('latitude')
    longitude = gps_coordinates.get('longitude')
    description = result.get('description', 'No description available.')
    translated_description = translator.translate(description)
    price = result.get('price', None)

    if not address or not latitude or not longitude:
        return "유효한 장소 정보를 찾을 수 없습니다."

    place_data = {
        "title": title,
        "rating": rating,
        "address": address,
        "latitude": latitude,
        "longitude": longitude,
        "description": translated_description,
        "price": price,
        "date": None,
        "time": None
    }
    
    formatted_result = f"장소 이름: {title}\n주소: {address}\n설명: {translated_description}\n"
    if price:
        formatted_result += f"    가격: {price}\n"
        
    return formatted_result, place_data

# 무한 루프를 사용하여 사용자 입력을 계속 받아 처리
while True:
    query = input("입력: ")
    if query.lower() in ['exit', 'quit']:
        break
    
    response, data = search_places(query)
    print(response, data)
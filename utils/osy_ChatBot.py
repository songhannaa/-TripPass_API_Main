from pymongo import MongoClient
import json
import openai
from serpapi import GoogleSearch
import deepl
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

# SerpAPI, DeepL 및 MongoDB 키 가져오기
SERP_API_KEY = get_secret("SERP_API_KEY")
DEEPL_AUTH_KEY = get_secret("DEEPL_AUTH_KEY")
MongoDB_Username = get_secret("MongoDB_Username")
MongoDB_Password = get_secret("MongoDB_Password")
MongoDB_Hostname = get_secret("MongoDB_Hostname")

mongodb_url = f'mongodb://{MongoDB_Username}:{MongoDB_Password}@{MongoDB_Hostname}:27017/'
client = MongoClient(mongodb_url)
db = client['TripPass']


# MongoDB 클라이언트 설정
client = MongoClient(mongodb_url)
db = client['TripPass']  # 데이터베이스 선택

# 유저의 발화 의도 파악하기
def chatIntent(prompt):
    intents = ["여행 일정을 만들어줘", "여행 일정에 추가해줘", "여행 일정을 변경할래", "여행 장소를 찾을래", "여행 장소를 추천해줘"]
    
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that classifies user intents."},
            {"role": "user", "content": f"Classify the intent of the following sentence: '{prompt}'. The possible intents are: {', '.join(intents)}."}
        ],
        max_tokens=150
    )

    return response.choices[0].message['content'].strip()

# 발화 의도 파악 후 질문자의 prompt에서 serpAPI 질문용 query 생성
def extractLocation(prompt):
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that extracts the location from a sentence."},
            {"role": "user", "content": f"Convert the following sentence into a query for SerpAPI: '{prompt}'. Here are some examples: 'restaurants near Eiffel Tower in Paris', 'popular tourist spots in New York', 'places to visit in Tokyo'. Please return it similar to these examples."}
        ],
        max_tokens=100
    )
    
    extracted_location = response.choices[0].message['content'].strip()
    print("query : ", extracted_location)

    return extracted_location

# 뽑아낸 쿼리를 이용해 serpAPI로 장소를 가져오기
def serpPlace(query):
    params = {
        "engine": "google_maps",
        "q": query,
        "hl": "en",
        "api_key": SERP_API_KEY
    }
    search = GoogleSearch(params)
    results = search.get_dict()

    if 'error' in results:
        return None

    return results

# serpApi return 값 깔끔하게 보여주기
def parseSerpData(data, userId, tripId):
    if 'local_results' not in data:
        return []
    
    translator = deepl.Translator(DEEPL_AUTH_KEY)
    parsed_results = []
    serp_collection = db['SerpData']
    
    for idx, result in enumerate(data['local_results'], 1):
        title = result.get('title')
        rating = result.get('rating')
        address = result.get('address')
        gps_coordinates = result.get('gps_coordinates', {})
        latitude = gps_coordinates.get('latitude')
        longitude = gps_coordinates.get('longitude')
        description = result.get('description', 'No description available.')
        translated_description = translator.translate_text(description, target_lang="KO").text
        
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
            print(f"{idx}. 장소 이름: {title}, 별점: {rating}, 주소: {address}, 가격: {price}\n    {translated_description}\n")
        else:
            print(f"{idx}. 장소 이름: {title}, 별점: {rating}, 주소: {address}\n    {translated_description}\n")

    document = {
        "userId": userId,
        "tripId": tripId,
        "serpData": parsed_results
    }
    
    # update_one을 사용하여 문서가 존재하면 업데이트, 존재하지 않으면 삽입 (upsert)
    serp_collection.update_one(
        {"userId": userId, "tripId": tripId},
        {"$set": document},
        upsert=True
    )
    
    return parsed_results

# 예시 실행
while(True):
    data = {}
    prompt = input("사용자 입력 (종료하려면 'exit' 입력): ")
    if prompt.lower() == 'exit':
        break
    
    user_id = 'example_user_id'  # 실제 구현 시에는 사용자의 ID를 동적으로 설정해야 합니다.
    trip_id = 'example_trip_id'  # 실제 구현 시에는 여행 ID를 동적으로 설정해야 합니다.
    
    intent = chatIntent(prompt)
    if '여행 장소를 찾을래' in intent  or '여행 장소를 추천해줘' in intent:
        query = extractLocation(prompt)
        print("query: ", query)
        data = serpPlace(query)
        if data:
            serpResults = parseSerpData(data, user_id, trip_id)
    elif '여행 일정에 추가해줘' in intent:
        print("intent: ", intent, "title, address, latitude, logitude, description을 저장하려고 mongodb에")
    elif '여행 일정을 만들어줘' in intent:
        print('intent: ', intent, "저장한 tmp mongodb를 가져와서 chatgpt한테 넘겨서 여행 일정 만들기")
    elif '여행 일정을 변경할래' in intent:
        print('intent: ', intent, "sql에 있는 여행 일정을 가져오고 수정인지 삭제인지 api 하기...")
    else:
        if data:
            print(data)
        print("intent: ", intent, "아직 그 부분은 개발 안함 쏴리")
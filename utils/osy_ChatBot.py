from pymongo import MongoClient
import json
import openai
from serpapi import GoogleSearch
import deepl
import os
import re
import uuid
import google.generativeai as genai

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

MYSQL_USERNAME = get_secret("MYSQL_USER_NAME")
MYSQL_PASSWORD = get_secret("MYSQL_PASSWORD")
MYSQL_DB_NAME = get_secret("MYSQL_DB_NAME")
HOSTNAME = get_secret("MYSQL_HOST")

GEMINI_API_KEY = get_secret("GEMINI_API_KEY")

mongodb_url = f'mongodb://{MongoDB_Username}:{MongoDB_Password}@{MongoDB_Hostname}:27017/'
client = MongoClient(mongodb_url)
db = client['TripPass']

# 유저의 발화 의도 파악하기
def chatIntent(prompt):
    intents = ["여행 일정을 만들어줘", "여행 일정에 추가해줘", "몇번 저장할래", "여행 일정을 수정, 삭제할래", "여행 장소를 찾을래", "여행 장소를 추천해줘"]
    
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
            {"role": "system", "content": "You are a helpful assistant that extracts the location and context from a sentence and converts it into a query for SerpAPI's Google Maps search."},
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
            "datetime": None
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

def extractNumbers(text):
    numbers = re.findall(r'\d+', text)
    # 숫자를 정수형으로 변환하여 리스트로 반환
    return [int(number) for number in numbers]

def saveSelectedPlace(userId, tripId, indexes):
    print(indexes)
    serp_collection = db['SerpData']
    save_place_collection = db['SavePlace']
    
    document = serp_collection.find_one({"userId": userId, "tripId": tripId})
    if not document:
        print("No matching document found in SerpData.")
        return
    
    serp_data_length = len(document['serpData'])
    valid_indexes = [index for index in indexes if 0 <= index < serp_data_length]
    
    if not valid_indexes:
        print("No valid indexes found.")
        return
    
    selected_places = [document['serpData'][index] for index in valid_indexes]
    
    save_place_collection.update_one(
        {"userId": userId, "tripId": tripId},
        {"$push": {"placeData": {"$each": selected_places}}},
        upsert=True
    )
    
    print(f"Saved places: {selected_places}")

# mongoDB에서 SavePlace의 placeData를 가져오기
def getSavedPlaces(userId, tripId):
    save_place_collection = db['SavePlace']
    document = save_place_collection.find_one({"userId": userId, "tripId": tripId})
    if not document:
        print("No matching document found in SavePlace.")
        return []
    

    return document.get('placeData', [])


def createSqlQuerys(userId, tripId, data, startdate, enddate):
    
    messages = [
        {"role": "system", "content": "당신은 주어진 데이터만 여행 계획과 SQL INSERT 문을 생성하는 유용한 도우미입니다."},
        {"role": "user", "content": f"다음 장소들을 이용하여 균형 잡힌 여행 계획을 만들어주세요. 각 날에는 관광 명소, 레스토랑, 카페가 균형 있게 포함되도록 해주세요. 되도록 식사 시간에 레스토랑 카페를 방문하도록 해줘"
                                    f"'tripPlans' 테이블에 대한 SQL INSERT 문을 생성해주세요. 테이블 스키마는 다음과 같습니다: "
                                    f"`planId` (UUID), `userId` ({userId}), `tripId` ({tripId}), `title` (한국어), `date`, `time` (HH:MM:SS 형식), `place`, `address`, `latitude`, `longitude`, `description`, `crewId`. "
                                    f"여행은 {startdate}에 시작하여 {enddate}에 끝나야 합니다. 각 장소에 고유한 datetime이 있어야 하며, 장소의 `datetime`이 null인 경우 INSERT 문에 포함하지 마세요. "
                                    f"같은 장소는 여행에서 한 번만 포함되도록 해주세요."
                                    f"insert문의 place가 data의 title이야 insert문이 title은 이 장소에 대해 너가 직접 타이틀을 붙여줘야해 만약 이 장소가 식당이라면 점심식사 라는 제목을 붙여주면 돼"
                                    f"`planId`는 Python의 `uuid` 라이브러리를 사용하여 생성된 UUID여야 합니다. 데이터: {json.dumps(data, default=str)}"
                                    f"이 예시를 참고해서 만들어줘 INSERT INTO tripPlans (planId, userId, tripId, title, date, time, place, address, latitude, longitude, description, crewId) VALUES('f8bcd5b5-7352-4f1c-bf49-0ba32f5aa53d', 'example_user', 'dubai_trip', 'Burj Khalifa', '2024-08-01', '09:00:00', 'Burj Khalifa', '1 Sheikh Mohammed bin Rashid Blvd, Downtown Dubai - Dubai, United Arab Emirates', 25.197197, 55.274376399999994, '160층 초고층 레스토랑 및 전망대. 전망대, 루스터와, 현대, 사회적이고 환상적인 828미터 랜드마크로부터 전망할 수 있습니다.', NULL);"
                                    f"모든 일정의 insert 문을 다 뽑아줘야해 모든 인자는 ""안에 넣어줘"}
    ]
    
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=messages,
        max_tokens=3000
    )

    return response.choices[0].message['content'].strip()

# 예시 실행
while(True):
    data = {}
    prompt = input("사용자 입력 (종료하려면 'exit' 입력): ")
    if prompt.lower() == 'exit':
        break
    
    user_id = 'example_user'  # 실제 구현 시에는 사용자의 ID를 동적으로 설정해야 합니다.
    trip_id = 'dubai_trip'  # 실제 구현 시에는 여행 ID를 동적으로 설정해야 합니다.
    startDate = '2024-08-01'
    endDate = '2024-08-04'
    
    intent = chatIntent(prompt)
    if '여행 장소를 찾을래' in intent or '여행 장소를 추천해줘' in intent:
        query = extractLocation(prompt)
        data = serpPlace(query)
        if data:
            serpResults = parseSerpData(data, user_id, trip_id)
    elif '여행 일정에 추가해줘' in intent or '몇번 저장할래' in intent:
        indexes = extractNumbers(prompt)
        saveSelectedPlace(user_id, trip_id, [index - 1 for index in indexes])  # 배열 인덱스는 0부터 시작하므로 -1
    elif '여행 일정을 만들어줘' in intent:
        data = getSavedPlaces(user_id, trip_id)
        if data:
            insertQ = createSqlQuerys(user_id, trip_id, data, startDate, endDate)
        print(insertQ)
        #print('intent: ', intent, "저장한 tmp mongodb를 가져와서 chatgpt한테 넘겨서 여행 일정 만들기")
    elif '여행 일정을 수정, 삭제할래' in intent:
        print('intent: ', intent, "sql에 있는 여행 일정을 가져오고 수정인지 삭제인지 api 하기...")
    else:
        if data:
            print(data)
        print("intent: ", intent, "아직 그 부분은 개발 안함 쏴리")

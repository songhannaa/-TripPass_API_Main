from pymongo import MongoClient
import json
import openai
from serpapi import GoogleSearch
import deepl
import os
import requests

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
API_URL = get_secret("API_URL")  # chat.py에서 FastAPI 애플리케이션이 실행되는 URL

mongodb_url = f'mongodb://{MongoDB_Username}:{MongoDB_Password}@{MongoDB_Hostname}:27017/'
client = MongoClient(mongodb_url)
db = client['TripPass']

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
    
    user_id = '9a29fb74-cf6f-4eff-b0e2-249ed3677527'  # 임시 userId
    trip_id = '487cbc12-b24a-4c1f-b6e7-bba46315be93'  # 임시 tripId
    
    intent = chatIntent(prompt)
    if '여행 장소를 찾을래' in intent or '여행 장소를 추천해줘' in intent:
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
        print("계획 수정을 시작합니다.")
        print("예시: '2024-07-24에 있는 Burj Khalifa 계획을 수정하고 싶어'")
        user_input = input("날짜와 제목을 입력해주세요: ")

        date, title = user_input.split("에 있는 ")
        title = title.replace(" 계획을 수정하고 싶어", "").strip()
        
        update_date = date.strip()
        print("수정할 시간을 입력해주세요 (예: 오후 3:00:00 또는 15:00:00): ")
        new_time = input("시간 입력: ").strip()

        update_request = {
            "userId": user_id,
            "tripId": trip_id,
            "date": update_date,
            "title": title,
            "new_time": new_time
        }

        # API 엔드포인트 호출하여 업데이트
        response = requests.post(f'{API_URL}/updateTripPlan', data=update_request, headers={"Content-Type": "application/x-www-form-urlencoded"})
        
        if response.status_code == 200:
            print("계획이 성공적으로 수정되었습니다.")
        else:
            print("계획 수정 중 오류가 발생했습니다: ", response.json().get('detail'))

    else:
        if data:
            print(data)
        print("intent: ", intent, "아직 그 부분은 개발 안함 쏴리")

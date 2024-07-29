import os
import json
import openai
from serpapi import GoogleSearch
from deep_translator import GoogleTranslator
from sqlalchemy.ext.declarative import declarative_base
from pymongo import MongoClient
import re
import uuid
from sqlalchemy import *
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, Column, String, INT,  FLOAT, LargeBinary, JSON
from sqlalchemy.dialects.mysql import LONGBLOB
import google.generativeai as genai

Base = declarative_base()

class tripPlans(Base):
    __tablename__ = 'tripPlans'
    planId = Column(String(36), primary_key=True)
    userId = Column(String(36), nullable=False)
    tripId = Column(String(36), nullable=False)
    title = Column(String(36), nullable=False)
    date = Column(String(36), nullable=False)
    time = Column(String(36), nullable=False)
    place = Column(String(255), nullable=False)
    address = Column(String(100), nullable=False)
    latitude = Column(FLOAT, nullable=False)
    longitude = Column(FLOAT, nullable=False)
    description = Column(String(100), nullable=False)
    crewId = Column(String(36), nullable=True)

class user(Base):
    __tablename__ = 'user'
    userId = Column(String(36), primary_key=True)
    id = Column(String(36), nullable=False)
    passwd = Column(String(255), nullable=False)
    nickname = Column(String(50), nullable=False)
    profileImage = Column(LONGBLOB,  nullable=True)
    socialProfileImage = Column(String(255), nullable=True)
    birthDate = Column(String(36), nullable=False)
    sex = Column(String(36), nullable=False)
    personality = Column(JSON, nullable=True)
    mainTrip = Column(String(36), nullable=True)

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

PORT = get_secret("MYSQL_PORT")
SQLUSERNAME = get_secret("MYSQL_USER_NAME")
SQLPASSWORD = get_secret("MYSQL_PASSWORD")
SQLDBNAME = get_secret("MYSQL_DB_NAME")
HOSTNAME = get_secret("MYSQL_HOST")
KAKAO_CLIENT_ID = get_secret("KAKAO_CLIENT_ID")
KAKAO_REDIRECT_URI = get_secret("KAKAO_REDIRECT_URI")
OPENAI_API_KEY = get_secret("OPENAI_API_KEY")
WEATHER_API_KEY = get_secret("WEATHER_API_KEY")
SERP_API_KEY = get_secret("SERP_API_KEY")
MongoDB_Hostname = get_secret("MongoDB_Hostname")
MongoDB_Username = get_secret("MongoDB_Username")
MongoDB_Password = get_secret("MongoDB_Password")
GEMINI_API_KEY = get_secret("GEMINI_API_KEY")

mongodb_url = f'mongodb://{MongoDB_Username}:{MongoDB_Password}@{MongoDB_Hostname}:27017/'
client = MongoClient(mongodb_url)
db = client['TripPass']

DB_URL = f'mysql+pymysql://{SQLUSERNAME}:{SQLPASSWORD}@{HOSTNAME}:{PORT}/{SQLDBNAME}'
class db_conn:
    def __init__(self):
        self.engine = create_engine(DB_URL, pool_recycle=500)

    def sessionmaker(self):
        Session = sessionmaker(bind=self.engine)
        session = Session()
        return session
    
    def connection(self):
        conn = self.engine.connection()
        return conn

sqldb = db_conn()

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
                            "description": "The search query for finding places if your query isn't english pleas translate it to english"
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
            },
            {
                "name": "save_place",
                "description": "query에서 숫자만 추출해 SerpData의 mongoDB데이터를 가져와 SavePlace mongoDB에 저장",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "사용자가 숫자와 함께 저장,추가해줘 혹은 갈래 라는 쿼리를 입력했을 시에 실행"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "save_plan",
                "description": "SavePlace의 placeData를 mysql tripPlans Table에 저장",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "사용자가 여행 일정을 만들어줘 혹은 이정도면 충분해 이제 저장할래 이런 말을 했을 때에 실행"
                        }
                    },
                    "required": ["query"]
                }
            }
        ],
        function_call="auto"
    )
    return response

def search_places(query: str, userId, tripId):
    params = {
        "engine": "google_maps",
        "q": query,
        "hl": "en",
        "api_key": SERP_API_KEY
    }
    print(query)
    search = GoogleSearch(params)
    results_data = search.get_dict()

    return parseSerpData(results_data, userId, tripId)

def parseSerpData(data, userId, tripId):
    if 'local_results' not in data:
        return []
    
    # 성향 사전 정의
    personality_dict = {
        "money1": "이왕 여행을 간 김에 가격이 비싸고 좋은 곳으로 알려줘",
        "money2": "여행 경비를 아껴야해 가격이 저렴한 곳으로 알려줘",
        "food1": "맛집 웨이팅 기다릴 수 있어 평점이 높은 곳 위주로",
        "food2": "그냥 끌리는대로 다닐래 평점 낮아도 상관 없어",
        "transport1": "경도 위도가 가까운 곳으로 알려줘",
        "transport2": "좀 멀어도 괜찮아",
        "schedule1": "즐기면서 천천히 다니고 싶어",
        "schedule2": "일정 알차게 돌아다니고 싶어",
        "photo1": "사진은 중요하지 않아",
        "photo2": "포토스팟 위주로 알려줘"
    }
    
    # SQL 데이터베이스에서 사용자 성향 데이터 가져오기
    session = sqldb.sessionmaker()
    user_data = session.query(user).filter(user.userId == userId).first().personality
    session.close()
    mypersonality = json.loads(user_data)
    
    # 성향 데이터를 문자열 쿼리로 변환
    personality_query = "사용자의 성향: "
    for key, value in mypersonality.items():
        personality_query += personality_dict[value] + " "

    print(personality_query)
    
    translator = GoogleTranslator(source='en', target='ko')
    parsed_results = []
    serp_collection = db['SerpData']
    
    for result in data['local_results']:
        title = result.get('title')
        rating = result.get('rating')
        address = result.get('address')
        gps_coordinates = result.get('gps_coordinates', {})
        latitude = gps_coordinates.get('latitude')
        longitude = gps_coordinates.get('longitude')
        description = result.get('description', 'No description available.')
        # translated_description = translator.translate(description)
        price = result.get('price', None)

        if not address or not latitude or not longitude:
            continue

        place_data = {
            "title": title,
            "rating": rating,
            "address": address,
            "latitude": latitude,
            "longitude": longitude,
            "description": description,
            "price": price,
            "date": None,
            "time": None
        }
        
        parsed_results.append(place_data)
    
    print(parsed_results)
    
    # Gemini API를 사용하여 검색 결과를 정렬
    genai.configure(api_key=GEMINI_API_KEY)
    prompt = (personality_query + "\n"
              "장소 목록:\n" +
              '\n'.join([f"{i+1}. 장소 이름: {place['title']}\n    별점: {place['rating']}\n    주소: {place['address']}\n    설명: {place['description']}\n    가격: {place.get('price', '없음')}\n" 
                         for i, place in enumerate(parsed_results)]) + "\n"
              "위 성향에 맞게 장소 목록을 재정렬해주세요. 해당 성향에 적합한 장소를 먼저 정렬해주세요 모든 장소를 사용해야하고 중복되지 않게 해주세요 이 장소 말고 다른 장소는 추가해서 안돼")
    
    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content(prompt).text
    
    # 응답에서 정렬된 장소 목록 추출
    sorted_results = response.strip().split('\n')
    
    # parsed_results를 sorted_results 순서에 맞게 정렬
    sorted_parsed_results = []
    for result in sorted_results:
        for place in parsed_results:
            if place['title'] in result:
                sorted_parsed_results.append(place)
                break
    
    parsed_results = sorted_parsed_results
    
    document = {
        "userId": userId,
        "tripId": tripId,
        "data": parsed_results
    }

    serp_collection.update_one(
        {"userId": userId, "tripId": tripId},
        {"$set": document},
        upsert=True
    )

    # 정렬된 결과를 formatted_place 형식으로 변환
    final_formatted_results = []
    for idx, place in enumerate(parsed_results, 1):
        formatted_place = f"{idx}. 장소 이름: {place['title']}\n    별점: {place['rating']}\n    주소: {place['address']}\n    설명: {place['description']}\n"
        if place['price']:
            formatted_place += f"    가격: {place['price']}\n"
        final_formatted_results.append(formatted_place)

    # 최종 문자열로 결합하여 반환
    return '\n'.join(final_formatted_results)

def just_chat(query: str):
    response = openai.ChatCompletion.create(
        model="gpt-4-0613",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": query}
        ]
    )
    return response.choices[0].message["content"]

def extractNumbers(text, userId, tripId):
    numbers = re.findall(r'\d+', text)
    indexes = [int(number) for number in numbers]

    saveSelectedPlace(userId, tripId, indexes)

    return indexes

def saveSelectedPlace(userId, tripId, indexes):
    serp_collection = db['SerpData']
    save_place_collection = db['SavePlace']
    
    document = serp_collection.find_one({"userId": userId, "tripId": tripId})
    if not document:
        print(userId, tripId)
        print("No matching document found in SerpData.")
        return
    
    serp_data_length = len(document['data'])
    valid_indexes = [index-1 for index in indexes if 0 <= index-1 < serp_data_length]
    
    if not valid_indexes:
        print("No valid indexes found.")
        return
    
    selected_places = [document['data'][index] for index in valid_indexes]
    
    save_place_collection.update_one(
        {"userId": userId, "tripId": tripId},
        {"$push": {"placeData": {"$each": selected_places}}},
        upsert=True
    )
    
    print(f"Saved places: {selected_places}")

def savePlans(userId, tripId, startDate, endDate):
    session = sqldb.sessionmaker()
    genai.configure(api_key=GEMINI_API_KEY)
    save_place_collection = db['SavePlace']
    document = save_place_collection.find_one({"userId": userId, "tripId": tripId})
    if not document:
        print("SavePlace에서 일치하는 문서를 찾을 수 없습니다.")
        return []
    place_data = document['placeData']
    place_data_str = json.dumps(place_data, ensure_ascii=False)
    model = genai.GenerativeModel('gemini-1.5-flash')
    query = f"""
    {startDate}부터 {endDate}까지 다음 장소들만 포함한 상세한 여행 일정을 만들어줘. {place_data_str} 데이터만을 모두 사용해서 각 날에 관광지, 레스토랑, 카페가 균형있게 포함되게 짜주고 되도록 경도와 위도가 가까운 장소들을 하루 일정에 적당히 넣어줘 같은 장소는 일정을 여러번 넣지 않게 해줘. 되도록 식사시간 그니까 12시, 6시는 식당이나 카페에 방문하게 해주고 
    시간은 시작 시간만 HH:MM:SS 형태로 뽑아주고 날짜는 YYYY-MM-DD이렇게 뽑아줘 description 절대 생략하지 말고 다 넣어줘. title 은 장소에서 해야할 일을 알려주면 좋겠다 예를 들어 에펠탑 관광 이런식으로 만약에 데이터가 부족해서 전체 일정을 다 채우지 못한다 해도 괜찮아 그럼 그냥 아예 리턴을 하지마
    일정에 들어가야하는 정보는 다음과 같은 포맷으로 만들어줘: title: [title], date: [YYYY-MM-DD], time: [HH:MM:SS], place: [place], address: [address], latitude: [latitude], longitude: [longitude], description: [description]. 의 json배열로 뽑아줘
    date랑 time이 null이 아니라면 그 시간으로 일정을 짜줘
    """
    response = model.generate_content(query)

    cleaned_string = response.text.strip('```')
    cleaned_string= cleaned_string.replace('json', '').strip()
    datas = json.loads(cleaned_string)
    print(datas)

    for data in datas:
        new_trip = tripPlans(
            planId= str(uuid.uuid4()),
            userId= "1c54d9e8-c2cc-4c49-a2cd-1d5143828c3e",
            tripId= "fd1188d7-1cd9-4824-aa6c-7d6328e77b75",
            title=data['title'],
            date=data['date'],
            time=data['time'],
            place=data['place'],
            address=data['address'],
            latitude=data['latitude'],
            longitude=data['longitude'],
            description=data['description']
        )
        session.add(new_trip)

    session.commit()

    save_place_collection.delete_one({"userId": userId, "tripId": tripId})
    session.close()
    

# 사용 예제
query = "뉴욕 카페 알려줄래?"
response = call_openai_function(query)

userId = "1c54d9e8-c2cc-4c49-a2cd-1d5143828c3e"
tripId = "fd1188d7-1cd9-4824-aa6c-7d6328e77b75"

startDate = "2024-08-01"
endDate = "2024-08-04"

try:
    function_call = response.choices[0].message["function_call"]
    if function_call["name"] == "search_places":
        args = json.loads(function_call["arguments"])
        search_query = args["query"]
        response = search_places(search_query, userId, tripId)
    elif function_call["name"] == "just_chat":
        args = json.loads(function_call["arguments"])
        response = just_chat(args["query"])
    elif function_call["name"] == "save_place":
        args = json.loads(function_call["arguments"])
        response = extractNumbers(args["query"],userId, tripId)
    elif function_call["name"] == "save_plan":
        args = json.loads(function_call["arguments"])
        response = savePlans(userId, tripId, startDate, endDate)
except KeyError:
    response = response.choices[0].message["content"]

print(response)
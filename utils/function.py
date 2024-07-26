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
from sqlalchemy import create_engine,Column, String, INT,  FLOAT, LargeBinary, JSON
import google.generativeai as genai
from database import sqldb, OPENAI_API_KEY, DB_URL, mongodb_url, GEMINI_API_KEY, SERP_API_KEY,db
from models.models import myTrips, tripPlans


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
                        },
                        "userId": {
                            "type": "string",
                            "description": "The user ID for the search context"
                        },
                        "tripId": {
                            "type": "string",
                            "description": "The trip ID for the search context"
                        }
                    },
                    "required": ["query", "userId", "tripId"]
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
    search = GoogleSearch(params)
    results_data = search.get_dict()

    return parseSerpData(results_data, userId, tripId)

def parseSerpData(data, userId, tripId):
    if 'local_results' not in data:
        return []
    
    translator = GoogleTranslator(source='en', target='ko')
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
        translated_description = translator.translate(description)
        price = result.get('price', None)

        if not address or not latitude or not longitude:
            continue

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
        
        parsed_results.append(place_data)
        
        if price:
            print(f"{idx}. 장소 이름: {title}\n    별점: {rating}\n    주소: {address}\n    가격: {price}\n    설명: {translated_description}\n")
        else:
            print(f"{idx}. 장소 이름: {title}\n    별점: {rating}\n    주소: {address}\n    설명: {translated_description}\n")
    
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

def extractNumbers(text, userId, tripId):
    numbers = re.findall(r'\d+', text)
    indexes = [int(number) for number in numbers]

    return saveSelectedPlace(userId, tripId, indexes)

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
    
    return selected_places

def savePlans(userId, tripId):
    session = sqldb.sessionmaker()
    mytrip = session.query(myTrips).filter(myTrips.tripId == tripId).first()
    startDate = mytrip.startDate
    endDate = mytrip.endDate
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
    {startDate}부터 {endDate}까지 다음 장소들만 포함한 상세한 여행 일정을 만들어줘. {place_data_str} 데이터만을 모두 사용해서 각 날에 관광지, 레스토랑, 카페가 균형있게 포함되게 짜주고 되도록 경도와 위도가 가까운 장소들을 하루 일정에 적당히 넣어줘, 하루에 너무 많은 장소를 넣지는 말아줘 적당히 배분해 같은 장소는 일정을 여러번 넣지 않게 해줘. 되도록 식사시간 그니까 12시, 6시는 식당이나 카페에 방문하게 해주고 
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
            userId= userId,
            tripId= tripId,
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

    query = f"""
    {cleaned_string}이걸 상세하게 설명해서 답변해줘 챗봇이 일정을 만들어준 것처럼 예를 들어 바르셀로나 여행 일정을 완성했어요! 1일차 - 이런식으로
    """
    response = model.generate_content(query).text

    return response
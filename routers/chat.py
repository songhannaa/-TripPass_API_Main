from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import json
from database import MongoDB_Hostname, MongoDB_Username, MongoDB_Password, SERP_API_KEY
import os
from fastapi import FastAPI, APIRouter, Query
import base64
from pymongo import MongoClient
from utils.SerpSearch import queryConvert, serpPlace, parseSerpData

router = APIRouter()

mongodb_url = f'mongodb://{MongoDB_Username}:{MongoDB_Password}@{MongoDB_Hostname}:27017/'
client = MongoClient(mongodb_url)
db = client['TripPass']

class QuestionRequest(BaseModel):
    userId: str
    tripId: str
    sender: str
    message: str

# ObjectId를 문자열로 변환하는 헬퍼 함수
def convert_objectid_to_str(doc):
    if '_id' in doc:
        doc['_id'] = str(doc['_id'])
    return doc

@router.get(path='/getChatMessages', description="채팅 로그 가져오기")
async def getChatMessages(userId: str = Query(...), tripId: str = Query(...)):
    collection = db['ChatData']
    try:
        chat_log = collection.find_one({"userId": userId, "tripId": tripId})
        if chat_log:
            response_data = convert_objectid_to_str(chat_log)
            conversation = response_data.get("conversation", [])
            return {"result_code": 200, "messages": conversation}
        else:
            return {"result_code": 404, "messages": []}
    except Exception as e:
        return {"result_code": 400, "messages": f"Error: {str(e)}"}

@router.post(path='/saveChatMessage', description="채팅 로그 저장")
async def saveChatMessage(request: QuestionRequest, isSerp: bool = False):
    collection = db['ChatData']
    
    # 채팅 로그 생성
    chat_log = {
        "timestamp": datetime.utcnow(),
        "sender": request.sender,
        "message": request.message,
        "isSerp": isSerp
    }
    
    try:
        # userId와 tripId가 있는지 확인하고 업데이트 또는 삽입
        result = collection.update_one(
            {"userId": request.userId, "tripId": request.tripId},
            {
                "$push": {"conversation": chat_log},
                "$setOnInsert": {
                    "userId": request.userId,
                    "tripId": request.tripId
                }
            },
            upsert=True
        )
    except Exception as e:
        return {"result code": 400, "response": f"Error: {str(e)}"}

    if result.upserted_id is not None:
        response_message = "New chat log created successfully"
    else:
        response_message = "Chat log updated successfully"

    return {"result code": 200, "response": response_message}

@router.post(path='/searchPlace', description="장소 검색 및 저장")
async def searchPlace(request: QuestionRequest):
    try:
        # 사용자 입력을 받아서 SerpAPI 쿼리로 변환
        query = queryConvert(request.message)
        
        # SerpAPI를 이용해 장소 검색
        place_data = serpPlace(query, SERP_API_KEY, request.userId, request.tripId)
        
        # 검색 결과가 있으면 MongoDB에 저장
        if place_data:
            bot_message = "\n".join([
                f"{idx + 1}. {place['title']}\n별점: {place['rating']}\n주소: {place['address']}\n설명: {place['description']}\n"
                for idx, place in enumerate(place_data)
            ])
            await saveChatMessage(QuestionRequest(userId=request.userId, tripId=request.tripId, sender='bot', message=bot_message), isSerp=True)
            return {"result_code": 200, "places": place_data}
        else:
            return {"result_code": 404, "message": "No results found."}
    except Exception as e:
        return {"result_code": 400, "message": f"Error: {str(e)}"}
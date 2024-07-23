from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import json
from database import MongoDB_Hostname, MongoDB_Username, MongoDB_Password
import os
from fastapi import FastAPI, APIRouter, Query
import base64
from pymongo import MongoClient

router = APIRouter()

mongodb_url = f'mongodb://{MongoDB_Username}:{MongoDB_Password}@{MongoDB_Hostname}:27017/'
client = MongoClient(mongodb_url)
db = client['TripPass']
ChatData_collection=db['ChatData']
SavePlace_collection=db['SavePlace']

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
    try:
        chat_log = ChatData_collection.find_one({"userId": userId, "tripId": tripId})
        if chat_log:
            response_data = convert_objectid_to_str(chat_log)
            return {"result_code": 200, "messages": response_data.get("conversation", [])}
        else:
            return {"result_code": 404, "messages": []}
    except Exception as e:
        return {"result_code": 400, "messages": f"Error: {str(e)}"}

@router.post(path='/saveChatMessage', description="채팅 로그 저장")
async def saveChatMessage(request: QuestionRequest):
    # 채팅 로그 생성
    chat_log = {
        "timestamp": datetime.utcnow(),
        "sender": request.sender,
        "message": request.message
    }
    
    try:
        # userId와 tripId가 있는지 확인하고 업데이트 또는 삽입
        result = ChatData_collection.update_one(
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


@router.get(path='/getSavePlace', description="선택한 장소 가져오기")
async def getSavedPlaces(userId: str = Query(...), tripId: str = Query(...)):
    try:
        document = SavePlace_collection.find_one({"userId": userId, "tripId": tripId})
        response_data = document.get('placeData', [])
        if document:
            return {"result code": 200, "response": response_data}
        else:
            return {"result code": 404, "response": "Document not found"}
    except Exception as e:
        return {"result code": 400, "response": f"Error: {str(e)}"}
    

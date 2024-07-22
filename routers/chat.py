from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import json
from database import MongoDB_Hostname, MongoDB_Username, MongoDB_Password
import os
from fastapi import FastAPI, APIRouter
import base64
from pymongo import MongoClient

router = APIRouter()

mongodb_url = f'mongodb://{MongoDB_Username}:{MongoDB_Password}@{MongoDB_Hostname}:27017/'
client = MongoClient(mongodb_url)
db = client['TripPass']
collection=db['ChatData']

class QuestionRequest(BaseModel):
    userId: str
    tripId: str
    sender: str
    message: str



@router.get(
    path='/getChat', description="채팅 로그"
)
async def getChat():
    # MongoDB에서 데이터 조회
    answer = list(collection.find())
    # ObjectId를 문자열로 변환하여 JSON 직렬화
    return json.loads(json.dumps({"result code": 200, "response": answer}))

@router.post(
    path='/insertChat', description="채팅 로그 저장"
)
async def insertChat(request: QuestionRequest):
    # 채팅 로그 생성
    chat_log = {
        "userId": request.userId,
        "tripId": request.tripId,
        "sender": request.sender,
        "message": request.message,
        "timestamp": datetime.utcnow()
    }
    
    try:
        collection.insert_one(chat_log)
    except Exception as e:
        return {"result code": 400, "response": f"Error: {str(e)}"}

    return {"result code": 200, "response": "Chat log updated successfully"}
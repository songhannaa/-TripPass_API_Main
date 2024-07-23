from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import json
from database import MongoDB_Hostname, MongoDB_Username, MongoDB_Password
from database import sqldb
import os
from fastapi import FastAPI, APIRouter, Query, HTTPException, Depends, Form
import base64
from pymongo import MongoClient
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.models import tripPlans
import uuid

router = APIRouter()

# Mongo 연결 설정
mongodb_url = f'mongodb://{MongoDB_Username}:{MongoDB_Password}@{MongoDB_Hostname}:27017/'
client = MongoClient(mongodb_url)
db = client['TripPass']
collection=db['ChatData']
placeCollcetion=db['SavePlace']

# MySQL 연결 설정
MYSQL_USER = os.getenv("MYSQL_USER_NAME")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
MYSQL_HOST = os.getenv("MYSQL_HOST")
MYSQL_DB = os.getenv("MYSQL_DB_NAME")

DATABASE_URL = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}/{MYSQL_DB}"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

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
        chat_log = collection.find_one({"userId": userId, "tripId": tripId})
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

@router.post(path='/updateTripPlan', description="여행 계획 수정")
async def updateTripPlan(
    userId: str = Form(...),
    tripId: str = Form(...),
    date: str = Form(...),
    title: str = Form(...),
    new_time: str = Form(...),
    session: Session = Depends(SessionLocal)
):
    try:
        # 사용자와 여행 ID에 따른 모든 여행 정보 가져오기
        plans = session.query(tripPlans).filter_by(userId=userId, tripId=tripId).all()
        
        if not plans:
            raise HTTPException(status_code=404, detail="No data found for this user and trip.")
        
        # 날짜와 제목이 일치하는 계획 찾기
        updated = False
        for plan in plans:
            if plan.date == date and plan.title == title:
                # 변경할 시간이 이미 존재하면 불가능
                if any(p.time == new_time for p in plans):
                    raise HTTPException(status_code=400, detail="The new time already exists in the schedule.")
                
                # crewId가 있을 경우 변경 불가
                if plan.crewId:
                    raise HTTPException(status_code=403, detail="Cannot modify plan with crewId.")
                
                # 시간 업데이트
                plan.time = new_time
                session.commit()
                updated = True
                break
        
        if not updated:
            raise HTTPException(status_code=404, detail="No matching plan found to update.")

        return {"result code": 200, "response": "Plan updated successfully"}
    
    except Exception as e:
        session.rollback()
        return {"result code": 400, "response": f"Error: {str(e)}"}
    
    finally:
        session.close()

app = FastAPI()
app.include_router(router)

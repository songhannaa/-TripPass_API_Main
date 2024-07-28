from fastapi import FastAPI, APIRouter, Query, HTTPException, Depends, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from models.models import *
import json
from database import sqldb , db , SERP_API_KEY
import base64
import uuid
from utils.SerpSearch import queryConvert, serpPlace, parseSerpData
from utils.function import *


router = APIRouter()

# mongodb collection
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
            conversation = response_data.get("conversation", [])
            return {"result_code": 200, "messages": conversation}
        else:
            return {"result_code": 404, "messages": []}
    except Exception as e:
        return {"result_code": 400, "messages": f"Error: {str(e)}"}

@router.post(path='/saveChatMessage', description="채팅 로그 저장")
async def saveChatMessage(request: QuestionRequest, isSerp: bool = False):
    
    # 채팅 로그 생성
    chat_log = {
        "timestamp": datetime.utcnow(),
        "sender": request.sender,
        "message": request.message,
        "isSerp": isSerp
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
    

@router.post(path='/updateTripPlan', description="여행 계획 수정")
async def updateTripPlan(
    userId: str = Form(...),
    tripId: str = Form(...),
    date: str = Form(...),
    title: str = Form(...),
    new_time: str = Form(...),
    session: Session = Depends(sqldb.sessionmaker)
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


@router.post(path='/callOpenAIFunction', description="OpenAI 함수 호출")
async def call_openai_function_endpoint(request: QuestionRequest):
    try:
        # OpenAI 함수를 호출하고 응답 받기
        response = call_openai_function(request.message)

        try:
            function_call = response.choices[0].message["function_call"]
            if function_call["name"] == "search_places":
                args = json.loads(function_call["arguments"])
                search_query = args["query"]
                result = search_places(search_query, request.userId, request.tripId)
            elif function_call["name"] == "just_chat":
                args = json.loads(function_call["arguments"])
                result = just_chat(args["query"])
            elif function_call["name"] == "save_place":
                args = json.loads(function_call["arguments"])
                result = extractNumbers(args["query"], request.userId, request.tripId)
            elif function_call["name"] == "save_plan":
                args = json.loads(function_call["arguments"])
                result = savePlans(request.userId, request.tripId)
            elif function_call["name"] == "update_trip_plan":
                args = json.loads(function_call["arguments"])
                result = update_trip_plan(args["user_id"], args["trip_title"], args["date"], args["plan_title"], args["new_time"])
            elif function_call["name"] == "check_trip_plan":
                args = json.loads(function_call["arguments"])
                result = check_trip_plan(args["user_id"], args["trip_title"], args["plan_title"], args["date"])

        except KeyError:
            result = response.choices[0].message["content"]

        return {"result_code": 200, "response": result}
    except Exception as e:
        return {"result_code": 400, "message": f"Error: {str(e)}"}
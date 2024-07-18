from fastapi import FastAPI, File, UploadFile, Form, Depends, HTTPException, Request, APIRouter
from sqlalchemy.orm import Session
from models.models import joinRequests, crew ,user, tripPlans
from database import sqldb
import base64
import uuid

router = APIRouter()

@router.get('/getJoinRequests', description="mySQL joinRequests Table 접근해서 정보 가져오기, crewId는 선택사항")
async def getJoinRequestsTable(userId: str = None,
session: Session = Depends(sqldb.sessionmaker)):
    try:
        if userId:
            crew_data = session.query(crew).filter(crew.tripmate.like(f"%{userId}%")).all()
            crew_ids = [c.crewId for c in crew_data]
            join_requests = session.query(joinRequests).filter(joinRequests.crewId.in_(crew_ids), joinRequests.status == 0).all()
        else:
            join_requests = session.query(joinRequests).filter(joinRequests.status == 0).all()

        results = []
        for request in join_requests:
            user_data = session.query(user).filter(user.userId == request.userId).first()
            request_dict = {
                "requestId": request.requestId,
                "crewId": request.crewId,
                "userId": request.userId,
                "tripId": request.tripId,
                "nickname": user_data.nickname,
                "profileImage": base64.b64encode(user_data.profileImage).decode('utf-8') if user_data.profileImage else None,
            }
            results.append(request_dict)
        return {"result code": 200, "response": results}
    finally:
        session.close()

@router.post('/insertJoinRequests', description="mySQL joinRequests Table에 추가, requestId는 auto increment로 생성")
async def insertJoinRequestsTable(
    userId : str = Form(...),
    tripId : str = Form(...),
    crewId : str = Form(...),
    session: Session = Depends(sqldb.sessionmaker)
):
    try:
        new_joinRequest = joinRequests(
            userId=userId, 
            tripId=tripId,
            crewId=crewId,
            status = 0
        )
        query = session.query(crew)
        query = query.filter(crew.crewId == crewId)
        crew_data = query.first()
        session.add(new_joinRequest)
        sincheongIn = crew_data.sincheongIn
        if sincheongIn is None:
            crew_data.sincheongIn = userId
        elif userId in sincheongIn:
            return {"result code": 404, "response": "Already joined"}
        else:
            crew_data.sincheongIn = str(sincheongIn) + "," + userId
        session.commit()
        session.refresh(new_joinRequest)
        return {"result code": 200, "response": crewId}
    finally:
        session.close()

@router.post('/updateCrewTripMate', description="mySQL crew Table의 tripMate를 업데이트. main page에서 수락 누르면 crew trip mate update 되고 joinRequests status 1로 바뀌고 crew sincheongIn에서 사라짐")
async def updateCrewTripMate(
    crewId: str = Form(...),
    userId: str = Form(...),
    status: int = Form(...),
    session: Session = Depends(sqldb.sessionmaker)
):
    try:
        # joinRequests 테이블에서 crewId와 userId가 일치하는 레코드를 찾고, status 업데이트
        join_request = session.query(joinRequests).filter(
            joinRequests.crewId == crewId,
            joinRequests.userId == userId
        ).first()

        if not join_request:
            return {"result code": 404, "response": "Join request not found"}

        join_request.status = status
        session.commit()

        # crew 테이블에서 crewId로 크루 찾기
        crew_data = session.query(crew).filter(crew.crewId == crewId).first()
        if not crew_data:
            return {"result code": 404, "response": "Crew not found"}

        # sincheongIn 필드에서 userId 제거
        sincheongIn = crew_data.sincheongIn.split(",") if crew_data.sincheongIn else []
        if userId in sincheongIn:
            sincheongIn.remove(userId)
            if not sincheongIn or sincheongIn == [""]:
                crew_data.sincheongIn = None
            else:
                crew_data.sincheongIn = ",".join(sincheongIn)
        session.commit()

        # status가 1인 경우 (수락 상태)
        if status == 1:
            # tripmate 필드에 userId 추가
            tripmates = crew_data.tripmate.split(",") if crew_data.tripmate else []
            if userId not in tripmates:
                tripmates.append(userId)
                crew_data.tripmate = ",".join(tripmates)
            session.commit()

            # joinRequests 테이블에서 tripId 가져오기
            tripId = join_request.tripId

            # tripPlans 테이블에서 tripId로 계획 찾기
            trip_plans = session.query(tripPlans).filter(tripPlans.tripId == crew_data.tripId).first()
            new_trip_plan = tripPlans(
                planId=str(uuid.uuid4()),
                userId=userId,
                tripId=tripId,
                title=trip_plans.title,
                date=trip_plans.date,
                time=trip_plans.time,
                place=trip_plans.place,
                address=trip_plans.address,
                latitude=trip_plans.latitude,
                longitude=trip_plans.longitude,
                description=trip_plans.description,
                crewId=trip_plans.crewId
            )
            session.add(new_trip_plan)
            session.commit()

        return {"result code": 200, "response": "Operation successful"}
    except Exception as e:
        session.rollback()
        return {"result code": 500, "response": str(e)}
    finally:
        session.close()
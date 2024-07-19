from fastapi import FastAPI, File, UploadFile, Form, Depends, HTTPException, Request, APIRouter
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from models.models import crew, tripPlans, myTrips
from database import sqldb
from sqlalchemy import and_
import base64
import uuid

router = APIRouter()

@router.get('/getCrew', description = "mySQL crew Table 접근해서 정보 가져오기, crewId는 선택사항")
async def getCrewTable(crewId: str = None,
 session: Session = Depends(sqldb.sessionmaker)):
    try:
        query = session.query(crew)
        if crewId is not None:
            query = query.filter(crew.crewId == crewId)
        crew_data = query.all()
        results = []
        for crews in crew_data:
            crew_dict = {
                "crewId": crews.crewId,
                "planId": crews.planId,
                "tripId": crews.tripId,
                "title": crews.title,
                "contact": crews.contact,
                "note": crews.note,
                "numOfMate": crews.numOfMate,
                "banner": base64.b64encode(crews.banner).decode('utf-8') if crews.banner else None,
                "tripmate": crews.tripmate,
                "sincheongIn": crews.sincheongIn,
            }
            results.append(crew_dict)
        return {"result code": 200, "response": results}
    finally:
        session.close()

@router.get('/getThisTripCrew', description="tripId가져와서 이번 여행에 있는 crew 다 가져오기")
async def getThisTripCrewTable(tripId: str,
session: Session = Depends(sqldb.sessionmaker)):
    try:
        # tripPlans 테이블에서 tripId가 일치하고 crewId가 null이 아닌 값 가져오기
        tripplans_query = session.query(tripPlans).filter(and_(tripPlans.tripId == tripId, tripPlans.crewId.isnot(None)))
        tripplans_data = tripplans_query.all()

        results = []
        for tripplan in tripplans_data:
            # crew 테이블에서 crewId가 일치하는 값 가져오기
            crew_query = session.query(crew).filter(crew.crewId == tripplan.crewId)
            crew_data = crew_query.first()
            
            if crew_data:
                crew_dict = {
                    "crewId": crew_data.crewId,
                    "planId": crew_data.planId,
                    "tripId": crew_data.tripId,
                    "title": crew_data.title,
                    "contact": crew_data.contact,
                    "note": crew_data.note,
                    "numOfMate": crew_data.numOfMate,
                    "banner": base64.b64encode(crew_data.banner).decode('utf-8') if crew_data.banner else None,
                    "tripmate": crew_data.tripmate,
                    "sincheongIn": crew_data.sincheongIn,
                    "date": tripplan.date,
                    "time": tripplan.time,
                    "place": tripplan.place,
                    "address": tripplan.address,
                    "latitude": tripplan.latitude,
                    "longitude": tripplan.longitude
                }
                results.append(crew_dict)

        if not results:
            return {"result code": 404, "message": "No matching crew data found"}

        return {"result code": 200, "response": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

@router.get('/getMyCrew', description = "mySQL crew Table 접근해서 정보 가져오기, userId, tripId 필수로 넣기 ")
async def getMyCrewTable(
    tripId : str,
    userId : str,
    session: Session = Depends(sqldb.sessionmaker)):
    try:
        query = session.query(crew)
        query = query.filter(and_(crew.tripId == tripId, crew.tripmate.like(f"%{userId}%")))
        print(crew.tripmate.like(f"%{userId}%"))
        crew_data = query.all()
        results = []
        for crews in crew_data:
            query = session.query(tripPlans)
            query = query.filter(tripPlans.planId == crews.planId)
            tripplans_data = query.first()
            query = session.query(myTrips)
            query = query.filter(myTrips.tripId == crews.tripId)
            mytrips_data = query.first()
            crew_dict = {
                "crewId": crews.crewId,
                "planId": crews.planId,
                "userId": tripplans_data.userId,
                "tripId": crews.tripId,
                "date": tripplans_data.date,
                "time": tripplans_data.time,
                "place": tripplans_data.place,
                "title": crews.title,
                "contact": crews.contact,
                "note": crews.note,
                "numOfMate": crews.numOfMate,
                "banner": base64.b64encode(crews.banner).decode('utf-8') if crews.banner else None,
                "tripmate": crews.tripmate,
                "sincheongIn": crews.sincheongIn,
                "address": tripplans_data.address,
                "latitude": tripplans_data.latitude,
                "longitude": tripplans_data.longitude,
                "contry": mytrips_data.contry,
                "city": mytrips_data.city
            }
            results.append(crew_dict)
        return {"result code": 200, "response": results}
    finally:
        session.close()

@router.get('/getCrewCalc', description="mySQL crew Table 접근해서 정보 가져오기, mainTrip 입력 필수")
async def getCrewTableCalc(mainTrip: str,
session: Session = Depends(sqldb.sessionmaker)):
    try:
        # mainTrip에 해당하는 여행 정보를 가져옴
        mytrips_query = session.query(myTrips).filter(myTrips.tripId == mainTrip)
        mytrips_data = mytrips_query.first()
        
        if not mytrips_data:
            raise HTTPException(status_code=404, detail="No trip found for the given tripId")

        contry = mytrips_data.contry
        city = mytrips_data.city
        start_date = mytrips_data.startDate
        end_date = mytrips_data.endDate
        
        results = []

        # 날짜 범위를 반복하여 각 날짜에 대한 tripPlans와 crew 정보를 가져옴
        current_date = start_date
        while current_date <= end_date:
            tripplans_query = session.query(tripPlans).filter(
                tripPlans.date == current_date,
                tripPlans.crewId != None
            )
            tripplans_data = tripplans_query.all()
            
            for plan in tripplans_data:
                # 필터링 조건 추가: 동일한 나라와 도시에서 mainTrip에 해당하는 계획을 제외
                if plan.tripId == mainTrip:
                    continue

                crew_query = session.query(crew).filter(crew.planId == plan.planId).first()
                
                if crew_query:
                    # 추가 필터링: 동일한 나라와 도시인지 확인
                    related_trip = session.query(myTrips).filter(myTrips.tripId == crew_query.tripId).first()
                    if related_trip.contry == contry and related_trip.city == city:
                        crew_dict = {
                            "crewId": crew_query.crewId,
                            "planId": crew_query.planId,
                            "userId": plan.userId,
                            "tripId": crew_query.tripId,
                            "date": plan.date.strftime("%Y-%m-%d"),
                            "time": plan.time,
                            "place": plan.place,
                            "title": crew_query.title,
                            "contact": crew_query.contact,
                            "note": crew_query.note,
                            "numOfMate": crew_query.numOfMate,
                            "banner": base64.b64encode(crew_query.banner).decode('utf-8') if crew_query.banner else None,
                            "tripmate": crew_query.tripmate,
                            "sincheongIn": crew_query.sincheongIn,
                            "address": plan.address,
                            "latitude": plan.latitude,
                            "longitude": plan.longitude,
                            "contry": contry,
                            "city": city
                        }
                        results.append(crew_dict)

            current_date += timedelta(days=1)
        
        if not results:
            raise HTTPException(status_code=404, detail="No matching crew data found")

        return {"result code": 200, "response": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

@router.post('/insertCrew', description="mySQL crew Table에 추가, crewId는 uuid로 생성, insert data 중 일부는 tripPlans planId를 이용해 가져오는거임")
async def insertCrewTable(
    planId: str = Form(...),
    title: str = Form(...),
    contact: str = Form(...),
    note: str = Form(...),
    numOfMate: str = Form(...),
    banner: UploadFile = File(None),
    session: Session = Depends(sqldb.sessionmaker)
):
    image_data = await banner.read() if banner else None
    try:
        # Get tripPlans data using planId
        trip_plan = session.query(tripPlans).filter(tripPlans.planId == planId).first()
        if not trip_plan:
            return {"result code": 404, "response": "Trip plan not found"}
        
        userId = trip_plan.userId
        tripId = trip_plan.tripId
        
        # Create new crew
        new_crew = crew(
            crewId=str(uuid.uuid4()), 
            planId=planId,
            tripId=tripId,
            title=title,
            contact=contact,
            note=note,
            numOfMate=numOfMate,
            banner=image_data,
            tripmate=userId,
            crewLeader=userId
        )
        
        session.add(new_crew)
        session.commit()
        session.refresh(new_crew)
        
        # Update tripPlans table with new crewId
        trip_plan.crewId = new_crew.crewId
        session.commit()

        return {"result code": 200, "response": new_crew.crewId}
    except Exception as e:
        session.rollback()
        return {"result code": 500, "response": str(e)}
    finally:
        session.close()

@router.delete('/deleteCrew', description="mySQL crew Table에서 크루 삭제, 크루를 생성한 사용자만 가능")
async def deleteCrew(request: Request,
session: Session = Depends(sqldb.sessionmaker)):
    try:
        data = await request.json()
        crewId = data.get("crewId")
        userId = data.get("userId")

        # 크루 정보를 가져옵니다
        crew_data = session.query(crew).filter(crew.crewId == crewId).first()

        # 크루가 존재하는지 확인합니다
        if not crew_data:
            return {"result code": 404, "response": "Crew not found"}

        crews = crew_data.tripmate.split(",")
        # 크루를 생성한 사용자인지 확인합니다
        if crews[0] != userId:
            return {"result code": 403, "response": "You are not authorized to delete this crew"}
        
        if len(crews) > 1 :
            return {"result code": 402, "response": "This Crew Already Has A Mate"}

        # 크루를 삭제합니다
        session.delete(crew_data)
        session.commit()

        # 관련된 tripPlans의 crewId를 제거합니다
        trip_plan = session.query(tripPlans).filter(tripPlans.crewId == crewId).first()
        if trip_plan:
            trip_plan.crewId = None
            session.commit()

        return {"result code": 200, "response": "Crew deleted successfully"}
    except Exception as e:
        session.rollback()
        return {"result code": 500, "response": str(e)}
    finally:
        session.close()
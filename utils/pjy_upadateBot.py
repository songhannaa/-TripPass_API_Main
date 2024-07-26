import os
import sys
import json
import openai
from datetime import datetime
from sqlalchemy import Column, String, INT, FLOAT, LargeBinary, JSON, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 현재 파일의 디렉토리 경로를 가져와서 부모 디렉토리를 sys.path에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# BASE_DIR 설정을 수정하여 secret.json 파일 경로가 정확한지 확인
BASE_DIR = parent_dir
secret_file = os.path.join(BASE_DIR, 'secret.json')

# secret.json 파일에서 API 키를 읽어옴
with open(secret_file) as f:
    secrets = json.loads(f.read())

# secret.json 파일에서 특정 설정을 가져오는 함수
def get_secret(setting, secrets=secrets):
    try:
        return secrets[setting]
    except KeyError:
        error_msg = f"Set the {setting} environment variable"
        raise KeyError(error_msg)

# API 키
OPENAI_API_KEY = get_secret("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

# Database 설정
PORT = get_secret("MYSQL_PORT")
SQLUSERNAME = get_secret("MYSQL_USER_NAME")
SQLPASSWORD = get_secret("MYSQL_PASSWORD")
SQLDBNAME = get_secret("MYSQL_DB_NAME")
HOSTNAME = get_secret("MYSQL_HOST")

DB_URL = f'mysql+pymysql://{SQLUSERNAME}:{SQLPASSWORD}@{HOSTNAME}:{PORT}/{SQLDBNAME}'
engine = create_engine(DB_URL, pool_recycle=500)
Session = sessionmaker(bind=engine)

# SQLAlchemy 모델 정의
Base = declarative_base()

class user(Base):
    __tablename__ = 'user'
    userId = Column(String(36), primary_key=True)
    id = Column(String(36), nullable=False)
    passwd = Column(String(255), nullable=False)
    nickname = Column(String(50), nullable=False)
    profileImage = Column(LargeBinary,  nullable=True)
    socialProfileImage = Column(String(255), nullable=True)
    birthDate = Column(String(36), nullable=False)
    sex = Column(String(36), nullable=False)
    personality = Column(JSON, nullable=True)
    mainTrip = Column(String(36), nullable=True)

class myTrips(Base):
    __tablename__ = 'myTrips'
    tripId = Column(String(36), primary_key=True)
    userId = Column(String(36), nullable=False)
    title = Column(String(60), nullable=False)
    contry = Column(String(36), nullable=False)
    city = Column(String(36), nullable=False)
    startDate = Column(String(36), nullable=False)
    endDate = Column(String(36), nullable=False)
    banner = Column(LargeBinary, nullable=True)
    memo = Column(String(255), nullable=True)

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

# 날짜 형식 변환 함수
def convert_date_format(date_str):
    try:
        # 입력된 날짜 문자열을 datetime 객체로 변환
        date_obj = datetime.strptime(date_str, "%y년 %m월 %d일")
        # 원하는 형식으로 변환하여 반환
        return date_obj.strftime("%Y-%m-%d")
    except ValueError:
        return date_str

# 일반 대화를 위한 OpenAI 모델 호출
def just_chat(query: str):
    response = openai.ChatCompletion.create(
        model="gpt-4-0613",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that provides travel recommendations and helps manage travel plans."},
            {"role": "user", "content": query}
        ]
    )
    return response.choices[0].message["content"]

# 사용자의 의도를 파악하는 함수
def detect_intent(query: str):
    response = openai.ChatCompletion.create(
        model="gpt-4-0613",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that identifies the user's intent. The intents can be: 'chat', 'update_plan'."},
            {"role": "user", "content": f"User query: '{query}'. Determine the user's intent from the given query."}
        ]
    )
    return response.choices[0].message["content"]

# 수정할 계획을 찾고 사용자에게 확인 받는 함수
def check_trip_plan(user_id: str, trip_title: str, plan_title: str, date: str):
    """Get the trip plan details and check if the given user_id, trip_title, date, plan_title match. And confirm with the user"""
    session = Session()

    try:
        # 날짜 형식 변환
        formatted_date = convert_date_format(date)
        
        # 해당 여행의 계획을 찾음
        trip = session.query(myTrips).filter_by(userId=user_id, title=trip_title).first()
        if not trip:
            return "Trip not found."

        plan = session.query(tripPlans).filter_by(userId=user_id, tripId=trip.tripId, date=formatted_date, title=plan_title).first()

        if plan:
            confirmation_message = (
                f"해당 계획을 수정하는 것이 맞나요?\n"
                f"여행명: {trip.title}\n"
                f"일정명: {plan.title}\n"
                f"날짜: {plan.date}\n"
                f"시간: {plan.time}\n"
                f"장소: {plan.place}\n"
            )
            return confirmation_message
        else:
            return "일치하는 일정을 찾지 못하였습니다. 기존 일정을 확인 후, 다시 말씀해주세요."
    except Exception as e:
        return f"An error occurred: {str(e)}"
    finally:
        session.close()

# 여행 계획을 수정하는 함수
def update_trip_plan(user_id: str, trip_title: str, date: str, plan_title: str, new_time: str):
    """Update the trip plan with the given user_id, trip_title, date, plan_title, and new_time."""
    session = Session()

    try:
        # 날짜 형식 변환
        formatted_date = convert_date_format(date)

        # 해당 여행의 계획을 찾음
        trip = session.query(myTrips).filter_by(userId=user_id, title=trip_title).first()
        if not trip:
            return "Trip not found."

        plan = session.query(tripPlans).filter_by(userId=user_id, tripId=trip.tripId, date=formatted_date, title=plan_title).first()
        if plan:
            # 계획 시간 업데이트
            plan.time = new_time
            session.commit()
            return "성공적으로 일정 시간이 수정되었습니다."
        else:
            return "일정을 수정하는 과정에서 문제가 발생했습니다. 다시 시도해주세요."
    except Exception as e:
        session.rollback()
        return f"An error occurred: {str(e)}"
    finally:
        session.close()

# OpenAI의 function calling을 사용하여 적절한 함수 호출
def call_openai_function(user_query: str, context_messages: list):
    messages = context_messages + [{"role": "user", "content": user_query}]
    
    response = openai.ChatCompletion.create(
        model="gpt-4-0613",
        messages=messages,
        functions=[
            {
                "name": "check_trip_plan",
                "description": "Get the trip plan details and confirm with the user",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_id": {
                            "type": "string",
                            "description": "User ID"
                        },
                        "trip_title": {
                            "type": "string",
                            "description": "Title of the trip"
                        },
                        "date": {
                            "type": "string",
                            "description": "Date of the trip"
                        },
                        "plan_title": {
                            "type": "string",
                            "description": "Title of the trip plan"
                        }
                    },
                    "required": ["user_id", "trip_title", "date", "plan_title"]
                }
            },
            {
                "name": "update_trip_plan",
                "description": "Update a trip plan with the given details",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_id": {
                            "type": "string",
                            "description": "User ID"
                        },
                        "trip_title": {
                            "type": "string",
                            "description": "Title of the trip"
                        },
                        "date": {
                            "type": "string",
                            "description": "Date of the trip"
                        },
                        "plan_title": {
                            "type": "string",
                            "description": "Title of the trip plan"
                        },
                        "new_time": {
                            "type": "string",
                            "description": "New time for the trip plan"
                        }
                    },
                    "required": ["user_id", "trip_title", "date", "plan_title", "new_time"]
                }
            }
        ],
        function_call="auto"
    )
    return response

# 사용자 입력 받아서 처리
def main():
    # 고정된 user_id
    user_id = "9a29fb74-cf6f-4eff-b0e2-249ed3677527"

    context_messages = [
        {"role": "system", "content": "You are a helpful assistant that provides travel recommendations and helps manage travel plans."}
    ]

    while True:
        user_query = input("사용자: ")

        # 사용자의 의도를 파악
        intent = detect_intent(user_query)

        if "update_plan" in intent:
            # 여행 계획 수정 의도일 때만 추가 정보 수집
            print("수정하려는 여행의 제목을 알려주세요:")
            trip_title = input("여행 제목: ")

            print("수정하려는 계획의 제목을 알려주세요:")
            plan_title = input("계획 제목: ")
            
            print("계획의 날짜를 알려주세요 (예: 24년 9월 12일):")
            date = input("날짜: ")

            print("계획의 시간을 알려주세요 (예: 19:00):")
            time = input("시간: ")

            response = check_trip_plan(user_id, trip_title, plan_title, date)
            print(response)
            confirmation = input("해당 계획을 수정하는 것이 맞나요? (yes/no): ")
            if confirmation.lower().strip() == "yes":
                new_time = input("새로운 시간을 입력하세요 (HH:MM): ")
                response = update_trip_plan(user_id, trip_title, date, plan_title, new_time)
                print(response)
            else:
                print("계획 수정을 취소했습니다.")
        else:
            # 일반 대화
            response = just_chat(user_query)
            print(response)

if __name__ == "__main__":
    main()

import os
import json
import openai
from sqlalchemy import create_engine, Column, String, Float, LargeBinary, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

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
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    description = Column(String(100), nullable=False)
    crewId = Column(String(36), nullable=True)

# 날짜 형식 변환 함수
def convert_date_format(date_str):
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        return date_obj.strftime("%Y-%m-%d")
    except ValueError:
        return date_str

# OpenAI 모델 호출 함수
def just_chat(query: str):
    response = openai.ChatCompletion.create(
        model="gpt-4-0613",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": query}
        ]
    )
    return response.choices[0].message["content"]

# 계획을 수정하는 함수
def update_trip_plan(user_id: str, trip_id: str, date: str, plan_title: str, new_time: str):
    session = Session()
    try:
        formatted_date = convert_date_format(date)
        plan = session.query(tripPlans).filter_by(userId=user_id, tripId=trip_id, date=formatted_date, title=plan_title).first()
        if plan:
            plan.time = new_time
            session.commit()
            return "성공적으로 일정 시간이 수정되었습니다."
        else:
            return "해당 일정이 존재하지 않습니다."
    except Exception as e:
        session.rollback()
        return f"오류가 발생했습니다: {str(e)}"
    finally:
        session.close()

# OpenAI 함수 호출
def call_openai_function(user_query: str):
    response = openai.ChatCompletion.create(
        model="gpt-4-0613",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that provides travel recommendations."},
            {"role": "user", "content": user_query}
        ],
        functions=[
            {
                "name": "update_trip_plan",
                "description": "Update a trip plan with the given details",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string", "description": "User ID"},
                        "trip_id": {"type": "string", "description": "Trip ID"},
                        "date": {"type": "string", "description": "Date of the trip"},
                        "plan_title": {"type": "string", "description": "Title of the trip plan"},
                        "new_time": {"type": "string", "description": "New time for the trip plan"}
                    },
                    "required": ["user_id", "trip_id", "date", "plan_title", "new_time"]
                }
            }
        ],
        function_call="auto"
    )
    return response

# 사용자 요청 처리 함수
def process_request(user_query: str, user_id: str, trip_id: str):
    context_messages = [
        {"role": "system", "content": "You are a helpful assistant that provides travel recommendations and helps manage travel plans."}
    ]

    intent_response = just_chat(f"Determine the intent of the following query: {user_query}")

    if "update" in intent_response.lower():
        date = input("수정하려는 계획의 날짜를 알려주세요 (예: 2024-09-13): ")
        plan_title = input("수정하려는 계획의 제목을 알려주세요: ")
        new_time = input("새로운 시간을 입력하세요 (HH:MM): ")

        response = call_openai_function(
            f"Update the trip plan for userId: {user_id}, tripId: {trip_id}, date: {date}, planTitle: {plan_title}, newTime: {new_time}"
        )

        try:
            function_call = response.choices[0].message["function_call"]
            if function_call["name"] == "update_trip_plan":
                args = json.loads(function_call["arguments"])
                date = args["date"]
                plan_title = args["plan_title"]
                new_time = args["new_time"]
                update_response = update_trip_plan(user_id, trip_id, date, plan_title, new_time)
                return update_response
        except KeyError:
            return response.choices[0].message["content"]
    else:
        return just_chat(user_query)

# 사용 예제
if __name__ == "__main__":
    user_query = input("사용자: ")
    user_id = "9a29fb74-cf6f-4eff-b0e2-249ed3677527"
    trip_id = "487cbc12-b24a-4c1f-b6e7-bba46315be93"

    response = process_request(user_query, user_id, trip_id)
    print(response)

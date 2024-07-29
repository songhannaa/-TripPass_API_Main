import os
import json
import openai
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, Column, String, FLOAT, LargeBinary

# BASE_DIR 설정을 수정하여 secret.json 파일 경로가 정확한지 확인
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(BASE_DIR)  # 부모 디렉토리를 가져옴
secret_file = os.path.join(parent_dir, 'secret.json')  # 부모 디렉토리에 있는 secret.json 파일 경로

# secret.json 파일에서 API 키를 읽어옴
with open(secret_file) as f:
    secrets = json.loads(f.read())

def get_secret(setting, secrets=secrets):
    try:
        return secrets[setting]
    except KeyError:
        error_msg = "Set the {} environment variable".format(setting)
        raise KeyError(error_msg)

PORT = get_secret("MYSQL_PORT")
SQLUSERNAME = get_secret("MYSQL_USER_NAME")
SQLPASSWORD = get_secret("MYSQL_PASSWORD")
SQLDBNAME = get_secret("MYSQL_DB_NAME")
HOSTNAME = get_secret("MYSQL_HOST")
OPENAI_API_KEY = get_secret("OPENAI_API_KEY")

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
    latitude = Column(FLOAT, nullable=False)
    longitude = Column(FLOAT, nullable=False)
    description = Column(String(100), nullable=False)
    crewId = Column(String(36), nullable=True)

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

openai.api_key = OPENAI_API_KEY

def call_openai_function(query: str):
    response = openai.ChatCompletion.create(
        model="gpt-4-0613",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that helps manage travel plans."},
            {"role": "user", "content": query}
        ],
        functions=[
            {
                "name": "update_trip_plan",
                "description": "Update a trip plan with the given details",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "userId": {
                            "type": "string",
                            "description": "User ID"
                        },
                        "tripId": {
                            "type": "string",
                            "description": "Trip ID"
                        },
                        "date": {
                            "type": "string",
                            "description": "Date of the tripPlans"
                        },
                        "title": {
                            "type": "string",
                            "description": "Title of the tripPlans"
                        },
                        "newTime": {
                            "type": "string",
                            "description": "New time for the trip plan"
                        }
                    },
                    "required": ["userId", "tripId", "date", "title", "newTime"]
                }
            }
        ],
        function_call="auto"
    )
    return response

def update_trip_plan(userId: str, tripId: str, date: str, title: str, newTime: str):
    """Update the trip plan with the given userId, tripId, date, title, and newTime."""
    session = Session()

    try:
        plan = session.query(tripPlans).filter_by(userId=userId, tripId=tripId, date=date, title=title).first()
        if plan:
            # 계획 시간 업데이트
            plan.time = newTime
            session.commit()
            return "성공적으로 일정 시간이 수정되었습니다."
        else:
            return "일정을 찾을 수 없습니다."
    except Exception as e:
        session.rollback()
        return f"An error occurred: {str(e)}"
    finally:
        session.close()

# def check_trip_plan(user_id: str, trip_title: str, plan_title: str, date: str):
#     """Get the trip plan details and check if the given user_id, trip_title, date, plan_title match. And confirm with the user"""
#     session = Session()

#     try:
#         # 날짜 형식 변환
#         formatted_date = convert_date_format(date)
        
#         # 해당 여행의 계획을 찾음
#         trip = session.query(myTrips).filter_by(userId=user_id, title=trip_title).first()
#         if not trip:
#             return "Trip not found."

#         plan = session.query(tripPlans).filter_by(userId=user_id, tripId=trip.tripId, date=formatted_date, title=plan_title).first()

#         if plan:
#             confirmation_message = (
#                 f"해당 계획을 수정하는 것이 맞나요?\n"
#                 f"여행명: {trip.title}\n"
#                 f"일정명: {plan.title}\n"
#                 f"날짜: {plan.date}\n"
#                 f"시간: {plan.time}\n"
#                 f"장소: {plan.place}\n"
#             )
#             return confirmation_message
#         else:
#             return "일치하는 일정을 찾지 못하였습니다. 기존 일정을 확인 후, 다시 말씀해주세요."
#     except Exception as e:
#         return f"An error occurred: {str(e)}"
#     finally:
#         session.close()

# # 여행 계획을 수정하는 함수
# def update_trip_plan(user_id: str, trip_title: str, date: str, plan_title: str, new_time: str):
#     """Update the trip plan with the given user_id, trip_title, date, plan_title, and new_time."""
#     session = Session()

#     try:
#         # 날짜 형식 변환
#         formatted_date = convert_date_format(date)

#         # 해당 여행의 계획을 찾음
#         trip = session.query(myTrips).filter_by(userId=user_id, title=trip_title).first()
#         if not trip:
#             return "Trip not found."

#         plan = session.query(tripPlans).filter_by(userId=user_id, tripId=trip.tripId, date=formatted_date, title=plan_title).first()
#         if plan:
#             # 계획 시간 업데이트
#             plan.time = new_time
#             session.commit()
#             return "성공적으로 일정 시간이 수정되었습니다."
#         else:
#             return "일정을 수정하는 과정에서 문제가 발생했습니다. 다시 시도해주세요."
#     except Exception as e:
#         session.rollback()
#         return f"An error occurred: {str(e)}"
#     finally:
#         session.close()

# 사용 예제
query = """나의 여행 계획을 수정하고 싶어. 수정하려는 계획의 날짜는 2024년 9월 13일이고, 일정명은 해변 산책 이야. 시간을 15:00로 변경해줄래?"""

response = call_openai_function(query)

userId = "9a29fb74-cf6f-4eff-b0e2-249ed3677527"
tripId = "487cbc12-b24a-4c1f-b6e7-bba46315be93"

try:
    function_call = response.choices[0].message["function_call"]
    if function_call["name"] == "update_trip_plan":
        args = json.loads(function_call["arguments"])
        date = args["date"]
        title = args["title"]
        newTime = args["newTime"]
        response = update_trip_plan(userId, tripId, date, title, newTime)
except KeyError:
    response = response.choices[0].message["content"]

print(response)


import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import user, myTrip, tripPlan, crew, joinRequest

app = FastAPI()

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get('/')
async def health_check():
    return "OK"

app.include_router(user.router, tags=["user"])
app.include_router(myTrip.router, tags=["mytrip"])
app.include_router(tripPlan.router, tags=["tripPlan"])
app.include_router(crew.router, tags=["crew"])
app.include_router(joinRequest.router, tags=["joinRequest"])
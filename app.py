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

app.include_router(user.router, prefix="/user", tags=["user"])
app.include_router(myTrip.router, prefix="/mytrip", tags=["mytrip"])
app.include_router(tripPlan.router, prefix="/tripPlan", tags=["tripPlan"])
app.include_router(crew.router, prefix="/crew", tags=["crew"])
app.include_router(joinRequest.router, prefix="/joinRequest", tags=["joinRequest"])

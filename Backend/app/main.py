from fastapi import FastAPI
from Backend.app.routes.search import router

app = FastAPI()

app.include_router(router)
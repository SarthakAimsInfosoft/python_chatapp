import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")


client = AsyncIOMotorClient(MONGODB_URI)
db = client.chatapp  # This is your database
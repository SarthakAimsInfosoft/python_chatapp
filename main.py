from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from database import db
from auth import hash_password, verify_password, create_access_token
from schemas import UserCreate
import re

app = FastAPI()

connected_clients = {}

# Allowed origins
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "https://chat-frontend-rob9.onrender.com"
]

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def is_allowed_ws_origin(origin: str) -> bool:
    if not origin:
        return False
    if origin in ALLOWED_ORIGINS:
        return True
    # Allow any Render subdomain if needed
    if re.match(r"https://.*\.onrender\.com$", origin):
        return True
    return False


@app.get("/")
async def root():
    return {"message": "FastAPI backend is running!"}

@app.post("/register")
async def register(user: UserCreate):
    existing_user = await db.users.find_one({"username": user.username})
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")

    hashed_password = hash_password(user.password)
    await db.users.insert_one({"username": user.username, "password": hashed_password})
    return {"message": "User registered successfully!"}

@app.post("/login")
async def login(user: UserCreate):
    db_user = await db.users.find_one({"username": user.username})
    if not db_user:
        raise HTTPException(status_code=400, detail="Invalid username or password")

    if not verify_password(user.password, db_user["password"]):
        raise HTTPException(status_code=400, detail="Invalid username or password")

    token = create_access_token({"sub": user.username})
    return {"access_token": token, "token_type": "bearer"}

@app.get("/online/{username}")
async def check_online(username: str):
    return {"username": username, "online": username in connected_clients}

# -----------------------------
# WebSocket endpoint
# -----------------------------
@app.websocket("/ws/{username}")
async def websocket_chat(websocket: WebSocket, username: str):
    origin = websocket.headers.get("origin")

    # Validate origin
    if not is_allowed_ws_origin(origin):
        await websocket.close(code=1008)  # Policy violation
        return

    await websocket.accept()
    connected_clients[username] = websocket

    try:
        while True:
            data = await websocket.receive_json()
            event_type = data.get("type")

            # -----------------------------
            # Handle message event
            # -----------------------------
            if event_type == "message":
                msg_id = data["id"]
                text = data["text"]
                receiver = data["receiver"]

                if receiver in connected_clients:
                    # Send message to receiver
                    await connected_clients[receiver].send_json({
                        "type": "message",
                        "id": msg_id,
                        "text": text,
                        "sender": username,
                        "receiver": receiver,
                        "status": "sent",
                    })
                    # Send delivered status to sender
                    await websocket.send_json({
                        "type": "status",
                        "id": msg_id,
                        "status": "delivered",
                    })
                else:
                    # Receiver offline → mark as sent
                    await websocket.send_json({
                        "type": "status",
                        "id": msg_id,
                        "status": "sent",
                    })

            # -----------------------------
            # Handle seen event
            # -----------------------------
            if event_type == "seen":
                sender = data["sender"]
                msg_id = data["id"]

                if sender in connected_clients:
                    await connected_clients[sender].send_json({
                        "type": "seen",
                        "id": msg_id
                    })

    except WebSocketDisconnect:
        pass
    finally:
        connected_clients.pop(username, None)

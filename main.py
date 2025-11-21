from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from database import db
from auth import hash_password, verify_password, create_access_token
from schemas import UserCreate
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

connected_clients = {}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://python-chatapp-xiny.onrender.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

@app.websocket("/ws/{username}")
async def websocket_chat(websocket: WebSocket, username: str):
    await websocket.accept()
    connected_clients[username] = websocket

    try:
        while True:
            data = await websocket.receive_json()
            event_type = data.get("type")

            if event_type == "message":
                msg_id = data["id"]
                text = data["text"]
                receiver = data["receiver"]

                if receiver in connected_clients:
                    await connected_clients[receiver].send_json({
                        "type": "message",
                        "id": msg_id,
                        "text": text,
                        "sender": username,
                        "receiver": receiver,
                        "status": "sent",
                    })

                    await websocket.send_json({
                        "type": "status",
                        "id": msg_id,
                        "status": "delivered",
                    })
                else:
                    await websocket.send_json({
                        "type": "status",
                        "id": msg_id,
                        "status": "sent",
                    })

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

@app.get("/online/{username}")
async def check_online(username: str):
    return { "username": username, "online": username in connected_clients }


@app.get("/")
async def root():
    return {"message": "FastAPI backend is running!"}

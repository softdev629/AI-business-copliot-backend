from fastapi import APIRouter, HTTPException
from schemas.auth import UserRegisterRequest
from core.database import db
from utils import get_password_hash

router = APIRouter(prefix="/api", tags=["auth"])

users_collection = db["users"]


@router.post("/register", description="Register User")
async def register_user(user: UserRegisterRequest):
    # Check if the user already exists
    existing_user = users_collection.find_one({"email": user.email})
    if existing_user:
        raise HTTPException(
            status_code=400, detail="Username already registered")

    # Hash the password and insert the new user into the database
    password_hash = get_password_hash(user.password)
    user_dict = user.dict()
    user_dict["password"] = password_hash
    users_collection.insert_one(user_dict)

    return {"message": "User registered successfully"}

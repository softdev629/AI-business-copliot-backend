from fastapi import APIRouter, HTTPException, Depends, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from schemas.auth import UserRegisterRequest
from typing import Annotated
from pydantic import EmailStr
from datetime import datetime
from random import randbytes
import hashlib

from core.database import db
from utils import get_password_hash, verify_password, create_access_token, user_entity
from core.email import Email

router = APIRouter(prefix="/api/auth", tags=["auth"])

users_collection = db["users"]


@router.post("/register", description="register user")
async def register_user(user: UserRegisterRequest, request: Request):
    # Check if the user already exists
    existing_user = users_collection.find_one({"email": user.email})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Account already exist")

    # Hash the password and insert the new user into the database
    password_hash = get_password_hash(user.password)

    user_dict = user.dict()
    user_dict["password"] = password_hash
    user_dict["role"] = "user"
    user_dict["is_verified"] = False
    user_dict["google_sign"] = False
    user_dict["created_at"] = datetime.utcnow()
    user_dict["updated_at"] = user_dict["created_at"]

    result = users_collection.insert_one(user_dict)
    # new_user = users_collection.find_one({"_id": result.inserted_id})

    # try:
    token = randbytes(10)
    hashed_code = hashlib.sha256()
    hashed_code.update(token)
    verification_code = hashed_code.hexdigest()
    users_collection.find_one_and_update({"_id": result.inserted_id}, {"$set": {
        "verification_code": verification_code, "updated_at": datetime.utcnow()}})
    print(token.hex())
    # url = f"{request.url.scheme}://{request.client.host}:{request.url.port}/api/auth/verifyemail/{token.hex()}"
    # await Email(user_entity(new_user), url, [EmailStr(user.email)]).sendVerificationCode()
    # except Exception as error:
    #     users_collection.find_one_and_update({"_id": result.inserted_id}, {
    #                                          "$set": {"verification_code": None, "updated_at": datetime.utcnow()}})
    #     raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    #                         detail="There was error sending email")
    return {"status": "success", "message": "Verification token successfully sent"}


@router.get('/verifyemail/{token}')
async def verify_me(token: str):
    hashed_code = hashlib.sha256()
    hashed_code.update(bytes.fromhex(token))
    verification_code = hashed_code.hexdigest()
    result = users_collection.find_one_and_update({"verification_code": verification_code}, {"$set": {
                                                  "verification_code": None, "is_verified": True, "updated_at": datetime.utcnow()}}, new=True)
    if not result:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Invalid verification code or account already verified")
    return {
        "status": "success",
        "message": "Account verified successfully"
    }


@router.post("/login", description="login user")
async def login_user(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    user = users_collection.find_one({"email": form_data.username})
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Incorrect username", headers={"WWW-Authenticate": "Bearer"})
    if not verify_password(form_data.password, user["password"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Incorrect password", headers={"WWW-Authenticate": "Bearer"})

    access_token = create_access_token(data={"sub": user["email"]})
    return {"access_token": access_token}

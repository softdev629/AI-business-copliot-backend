from fastapi import APIRouter, Query
from bson import ObjectId
from core.database import db

router = APIRouter(prefix="/api/admin/users", tags=["auth"])

users = db["users"]


@router.get("/", description="get all users")
async def get_users(page=1, size=10):
    all_users = list(users.find({}))
    total = users.count_documents({})
    user_array = []
    for user in all_users:
        user["id"] = str(user["_id"])
        user.pop("_id")
        user_array.append(user)
    return {"users": user_array, "total": total}


@router.delete("/", description="delete user")
async def delete_user(id: str):
    users.delete_one({"_id": ObjectId(id)})
    return {"state": "success"}

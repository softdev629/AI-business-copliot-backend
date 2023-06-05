from fastapi import APIRouter
from core.database import db

router = APIRouter(prefix="/api/admin/users", tags=["auth"])

users = db["users"]


@router.get("/", description="get all users")
async def get_users():
    all_users = list(users.find({}))
    user_array = []
    for user in all_users:
        user.pop("_id")
        user_array.append(user)
    return {"users": user_array}

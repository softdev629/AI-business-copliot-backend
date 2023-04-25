from pydantic import BaseModel


class UserRegisterRequest(BaseModel):
    email: str
    full_name: str
    phone: str
    password: str

import uuid

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=200)


class RegisterRequest(BaseModel):
    display_name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=6, max_length=200)


class GoogleAuthRequest(BaseModel):
    credential: str = Field(min_length=1)
    email: str | None = Field(default=None, max_length=320)
    name: str | None = Field(default=None, max_length=120)


class AuthConfigOut(BaseModel):
    google_client_id: str = ""


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str

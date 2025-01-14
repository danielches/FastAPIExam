from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from fastapi import Form


class SearchForm(BaseModel):
    query: Optional[str] = ""


class RegisterForm:
    def __init__(
        self,
        username: str = Form(...),
        email: str = Form(...),
        first_name: str = Form(...),
        last_name: str = Form(""),
        password: str = Form(...),
        confirm_password: str = Form(...)
    ):
        self.username = username
        self.email = email
        self.first_name = first_name
        self.last_name = last_name
        self.password = password
        self.confirm_password = confirm_password


class LoginForm:
    def __init__(
        self,
        username: str = Form(...),
        password: str = Form(...)
    ):
        self.username = username
        self.password = password


class ProfileForm(BaseModel):
    username: str = Field(..., title="Username", max_length=50)
    first_name: str = Field(..., title="First Name", max_length=50)
    last_name: str = Field(..., title="Last Name", max_length=50)
    email: EmailStr = Field(..., title="Email Address")


class CartItemForm:
    def __init__(self, quantity: int = Form(...)):
        self.quantity = quantity


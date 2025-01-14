from sqlalchemy import Column, Integer, String, ForeignKey, Text, DateTime, Float, Table
from sqlalchemy.orm import relationship
from app.database import Base
from passlib.context import CryptContext
from fastapi import Request

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class Genre(Base):
    __tablename__ = "genres"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    code = Column(String, unique=True, nullable=False)
    books = relationship("Book", back_populates="genre")

    def __repr__(self):
        return self.name


class Book(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    author = Column(String, nullable=False)
    published_date = Column(DateTime, nullable=False)
    description = Column(String, nullable=False)
    photo = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    buy_cnt = Column(Integer, default=0)
    genre_id = Column(Integer, ForeignKey("genres.id"), nullable=False)

    genre = relationship("Genre", back_populates="books")

    def __repr__(self):
        return self.name

roles_users = Table(
    'roles_users',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id')),
    Column('role_id', Integer, ForeignKey('roles.id'))
)


class Role(Base):
    __tablename__ = 'roles'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(80), unique=True, nullable=False)
    description = Column(String(255), nullable=True)

    # Связь с пользователями
    users = relationship("User", secondary=roles_users, back_populates="roles")

    def __repr__(self):
        return f"<Role(name={self.name})>"
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String)
    password = Column(String, nullable=False)
    roles = relationship("Role", secondary=roles_users, back_populates="users")

    def verify_password(self, password: str) -> bool:
        return pwd_context.verify(password, self.password)

    def set_password(self, password: str):
        self.password = pwd_context.hash(password)

    @property
    def is_authenticated(self):
        return True if self.id else False

    @property
    def is_admin(self):
        return any(role.name == "admin" for role in self.roles)


class Cart(Base):
    __tablename__ = "carts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship("User")
    items = relationship("CartItem", back_populates="cart")

    def total_price(self):
        return sum(item.total_price() for item in self.items)

class CartItem(Base):
    __tablename__ = "cart_items"

    id = Column(Integer, primary_key=True, index=True)
    cart_id = Column(Integer, ForeignKey("carts.id"))
    book_id = Column(Integer, ForeignKey("books.id"))
    quantity = Column(Integer, default=1)

    cart = relationship("Cart", back_populates="items")
    book = relationship("Book")

    def total_price(self):
        return self.quantity * self.book.price

import os
from datetime import datetime

from fastapi import FastAPI, Depends, Request, HTTPException, APIRouter, Form
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.responses import RedirectResponse
from app.database import SessionLocal, engine, Base
from app.models import Genre, Book, User, Cart, CartItem, Role
from app.schemas import RegisterForm, LoginForm, ProfileForm, SearchForm, CartItemForm
from app.auth import get_db, authenticate_user, get_current_user, pwd_context
from fastapi_csrf_protect import CsrfProtect
from starlette.middleware.sessions import SessionMiddleware



class CsrfSettings(BaseModel):
    secret_key: str = "your_secret_key_here"


@CsrfProtect.load_config
def get_csrf_config():
    return CsrfSettings()


app = FastAPI()

app.add_middleware(SessionMiddleware, secret_key="your_secret_key")

static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory="templates")

Base.metadata.create_all(bind=engine)



@app.get("/ping")
async def ping():
    return {"message": "pong"}


@app.get("/", response_class=HTMLResponse)
async def homepage(request: Request, db: Session = Depends(get_db),
                   searchform: SearchForm = Depends(),user: User = Depends(get_current_user)):
    genres = db.query(Genre).all()
    books = db.query(Book).order_by(Book.buy_cnt.desc()).limit(3).all()
    return templates.TemplateResponse("homepage.html", {
        "request": request,
        "genres": genres,
        "books": books,
        "user": user,
        "searchform": searchform
    })


@app.get('/genre/{genre_code}')
async def genrepage(request: Request, genre_code: str, db: Session = Depends(get_db),
                    searchform: SearchForm = Depends(), user: User = Depends(get_current_user)):
    genres = db.execute(select(Genre)).scalars().all()
    current_genre = db.query(Genre).filter(Genre.code == genre_code).first()
    books = db.query(Book).join(Genre).filter(Genre.code == genre_code).all()

    return templates.TemplateResponse(
        "genrepage.html",
        {"request": request, "name": "genre", "genres": genres, "books": books,
         "searchform": searchform, "title": current_genre, "user": user}
    )


@app.get("/books/{page}", response_class=HTMLResponse)
async def all_books(request: Request, page: int = 1, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    page_size = 12
    offset = (page - 1) * page_size

    genres = db.query(Genre).all()
    books = db.query(Book).offset(offset).limit(page_size).all()
    total_books = db.query(Book).count()
    total_pages = (total_books + page_size - 1) // page_size

    has_prev = page > 1
    has_next = page < total_pages

    return templates.TemplateResponse("books.html", {
        "request": request,
        "title": "All Books",
        "books": books,
        "genres": genres,
        "page": page,
        "total_pages": total_pages,
        "has_prev": has_prev,
        "has_next": has_next,
        "searchform": SearchForm(),
        "user": user
    })


@app.get("/popular_books/{page}", response_class=HTMLResponse)
async def popular_books(request: Request, page: int = 1, db: Session = Depends(get_db),
                        user: User = Depends(get_current_user)):
    page_size = 12
    offset = (page - 1) * page_size

    genres = db.query(Genre).all()
    books = db.query(Book).order_by(Book.buy_cnt.desc()).offset(offset).limit(page_size).all()
    total_books = db.query(Book).count()
    total_pages = (total_books + page_size - 1) // page_size

    has_prev = page > 1
    has_next = page < total_pages

    return templates.TemplateResponse("popularbooks.html", {
        "request": request,
        "title": "Popular Books",
        "books": books,
        "genres": genres,
        "page": page,
        "total_pages": total_pages,
        "has_prev": has_prev,
        "has_next": has_next,
        "searchform": SearchForm(),
        "user": user
    })


@app.get("/search", response_class=HTMLResponse)
async def search_books(request: Request, query: str = "", db: Session = Depends(get_db),
                       searchform: SearchForm = Depends(), user: User = Depends(get_current_user)):
    genres = db.query(Genre).all()

    # Расширяем поиск: фильтруем книги по названию, автору и жанру
    books = db.query(Book).join(Genre).filter(
        (Book.title.ilike(f"%{query}%")) |
        (Book.author.ilike(f"%{query}%")) |
        (Genre.name.ilike(f"%{query}%"))
    ).all()

    return templates.TemplateResponse("search.html", {
        "request": request,
        "genres": genres,
        "books": books,
        "query": query,
        "user": user,
        "searchform": searchform
    })


@app.get("/book/{book_id}", response_class=HTMLResponse)
async def book_detail(request: Request, book_id: int, db: Session = Depends(get_db),
                      searchform: SearchForm = Depends(), user: User = Depends(get_current_user)):
    genres = db.query(Genre).all()
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return templates.TemplateResponse("bookpage.html", {
        "request": request,
        "genres": genres,
        "book": book,
        "searchform": searchform,
        "user": user
    })


@app.post("/book/{book_id}", response_class=HTMLResponse)
async def add_to_cart(
        request: Request,
        book_id: int,
        form_data: CartItemForm = Depends(),
        db: Session = Depends(get_db),
        user: User = Depends(get_current_user),
        searchform: SearchForm = Depends(),
):
    cart = db.query(Cart).filter(Cart.user_id == user.id).first()
    cart_item = db.query(CartItem).filter(
        CartItem.cart_id == cart.id,
        CartItem.book_id == book_id
    ).first()

    if cart_item:
        cart_item.quantity += form_data.quantity
    else:
        cart_item = CartItem(cart_id=cart.id, book_id=book_id, quantity=form_data.quantity)
        db.add(cart_item)

    db.commit()

    # Добавляем уведомление в шаблон
    book = db.query(Book).filter(Book.id == book_id).first()
    success_message = f"'{book.title}' has been added to your cart."

    genres = db.query(Genre).all()
    return templates.TemplateResponse("bookpage.html", {
        "request": request,
        "book": book,
        "user": user,
        "genres": genres,
        "success_message": success_message,
        "searchform": searchform
    })


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request,
                        searchform: SearchForm = Depends(),
                        user: User = Depends(get_current_user)):
    return templates.TemplateResponse("register.html", {"request": request, "searchform": searchform,
                                                        "user": user})


@app.post("/register", response_class=HTMLResponse)
async def register_user(
    request: Request,
    form_data: RegisterForm = Depends(),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    genres = db.query(Genre).all()

    if form_data.password != form_data.confirm_password:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "genres": genres,
            "error": "Passwords do not match!",
            "user": user
        })

    hashed_password = pwd_context.hash(form_data.password)

    new_user = User(
        first_name=form_data.first_name,
        last_name=form_data.last_name or "",
        username=form_data.username,
        email=form_data.email,
        password=hashed_password,
    )
    db.add(new_user)
    db.commit()

    return RedirectResponse(url="/login", status_code=302)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, csrf_protect: CsrfProtect = Depends(),
                     searchform: SearchForm = Depends(), user: User = Depends(get_current_user)):
    csrf_token = csrf_protect.generate_csrf_tokens()
    return templates.TemplateResponse("login.html", {
        "request": request,
        "csrf_token": csrf_token,
        "user": user,
        "searchform": searchform

    })


@app.post("/login", response_class=HTMLResponse)
async def login_user(
    request: Request,
    form_data: LoginForm = Depends(),
    db: Session = Depends(get_db),
    searchform: SearchForm = Depends(),
):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "user": None,
                "error": "Invalid username or password.",
                "searchform": searchform,
            },
            status_code=401,
        )

    request.session["user_id"] = user.id

    return templates.TemplateResponse(
        "homepage.html",
        {
            "request": request,
            "user": user,
            "searchform": searchform,
        },
    )



@app.get("/profile", response_class=HTMLResponse)
async def profile(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    searchform: SearchForm = Depends(),
):
    genres = db.query(Genre).all()
    form = ProfileForm(
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        username=user.username,
    )
    return templates.TemplateResponse(
        "profile.html",
        {
            "request": request,
            "form": form,
            "searchform": searchform,
            "user": user,
            "genres": genres,
        },
    )


@app.post("/profile", response_class=HTMLResponse)
async def profile_update(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
):
    user.first_name = first_name
    user.last_name = last_name
    user.email = email
    db.commit()
    return RedirectResponse(url="/profile", status_code=302)


@app.get("/cart", response_class=HTMLResponse)
async def cart_detail(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    searchform: SearchForm = Depends(),
):
    genres = db.query(Genre).all()

    cart = db.query(Cart).filter_by(user_id=user.id).first()
    if not cart:
        cart = Cart(user_id=user.id)
        db.add(cart)
        db.commit()
        db.refresh(cart)

    return templates.TemplateResponse(
        "cart.html",
        {
            "request": request,
            "cart": cart,
            "items": cart.items,
            "user": user,
            "searchform": searchform,
            "genres": genres,
        },
    )


@app.post("/cart/remove/{item_id}")
async def remove_from_cart(
        request: Request,
        item_id: int,
        db: Session = Depends(get_db),
        user: User = Depends(get_current_user)
):
    cart_item = db.query(CartItem).filter(CartItem.id == item_id).first()
    if not cart_item:
        raise HTTPException(status_code=404, detail="Item not found")
    db.delete(cart_item)
    db.commit()
    return RedirectResponse(url="/cart", status_code=302)


@app.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=302)


@app.get("/change_password", response_class=HTMLResponse)
async def change_password_page(
    request: Request,
    user: User = Depends(get_current_user),
    searchform: SearchForm = Depends(),
):
    return templates.TemplateResponse("change_password.html", {
        "request": request,
        "user": user,
        "searchform": searchform
    })


@app.post("/change_password", response_class=HTMLResponse)
async def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    searchform: SearchForm = Depends(),
):
    if not pwd_context.verify(current_password, user.password):
        return templates.TemplateResponse("change_password.html", {
            "request": request,
            "user": user,
            "error": "Current password is incorrect",
            "searchform": searchform
        })

    if new_password != confirm_password:
        return templates.TemplateResponse("change_password.html", {
            "request": request,
            "user": user,
            "error": "New passwords do not match",
            "searchform": searchform
        })

    user.password = pwd_context.hash(new_password)
    db.commit()

    return templates.TemplateResponse("change_password.html", {
        "request": request,
        "user": user,
        "success": "Password successfully updated",
        "searchform": searchform
    })





@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    searchform: SearchForm = Depends(),
):
    if not (user is not None and user.is_admin):
        raise HTTPException(status_code=403, detail="Access denied")

    genres = db.query(Genre).all()
    users = db.query(User).all()
    books = db.query(Book).all()

    return templates.TemplateResponse("admin_dashboard.html", {
        "request": request,
        "user": user,
        "genres": genres,
        "users": users,
        "books": books,
        "searchform": searchform,
    })


@app.get("/admin/genres", response_class=HTMLResponse)
async def admin_genres(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    searchform: SearchForm = Depends(),
):
    if not (user is not None and user.is_admin):
        raise HTTPException(status_code=403, detail="Access denied")

    genres = db.query(Genre).all()
    return templates.TemplateResponse("admin_genres.html", {
        "request": request,
        "user": user,
        "genres": genres,
        "searchform": searchform,
    })


@app.get("/admin/genres/add", response_class=HTMLResponse)
async def admin_add_genre_page(
    request: Request,
    user: User = Depends(get_current_user),
    searchform: SearchForm = Depends(),
):
    if not (user is not None and user.is_admin):
        raise HTTPException(status_code=403, detail="Access denied")

    return templates.TemplateResponse("admin_add_genre.html", {
        "request": request,
        "user": user,
        "searchform": searchform,
    })


@app.post("/admin/genres/add", response_class=HTMLResponse)
async def admin_add_genre(
    request: Request,
    name: str = Form(...),
    code: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not (user is not None and user.is_admin):
        raise HTTPException(status_code=403, detail="Access denied")

    new_genre = Genre(name=name, code=code)
    db.add(new_genre)
    db.commit()
    return RedirectResponse(url="/admin/genres", status_code=302)


@app.get("/admin/genres/edit/{genre_id}", response_class=HTMLResponse)
async def admin_edit_genre_page(
    request: Request,
    genre_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    searchform: SearchForm = Depends(),
):
    if not (user is not None and user.is_admin):
        raise HTTPException(status_code=403, detail="Access denied")

    genre = db.query(Genre).filter(Genre.id == genre_id).first()
    if not genre:
        raise HTTPException(status_code=404, detail="Genre not found")

    return templates.TemplateResponse("admin_edit_genre.html", {
        "request": request,
        "genre": genre,
        "user": user,
        "searchform": searchform,
    })


@app.post("/admin/genres/edit/{genre_id}", response_class=HTMLResponse)
async def admin_edit_genre(
    request: Request,
    genre_id: int,
    name: str = Form(...),
    code: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not (user is not None and user.is_admin):
        raise HTTPException(status_code=403, detail="Access denied")

    genre = db.query(Genre).filter(Genre.id == genre_id).first()
    if not genre:
        raise HTTPException(status_code=404, detail="Genre not found")

    genre.name = name
    genre.code = code
    db.commit()
    return RedirectResponse(url="/admin/genres", status_code=302)


@app.post("/admin/genres/delete/{genre_id}")
async def admin_delete_genre(
    request: Request,
    genre_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not (user is not None and user.is_admin):
        raise HTTPException(status_code=403, detail="Access denied")

    genre = db.query(Genre).filter(Genre.id == genre_id).first()
    if not genre:
        raise HTTPException(status_code=404, detail="Genre not found")

    db.delete(genre)
    db.commit()
    return RedirectResponse(url="/admin/genres", status_code=302)






@app.get("/admin/books", response_class=HTMLResponse)
async def admin_books(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not (user is not None and user.is_admin):
        raise HTTPException(status_code=403, detail="Access denied")

    books = db.query(Book).all()
    return templates.TemplateResponse("admin_books.html", {"request": request, "books": books})

@app.get("/admin/books/add", response_class=HTMLResponse)
async def add_book_form(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user),):
    if not (user is not None and user.is_admin):
        raise HTTPException(status_code=403, detail="Access denied")
    genres = db.query(Genre).all()
    return templates.TemplateResponse("add_book.html", {"request": request, "genres": genres})

@app.post("/admin/books/add")
async def add_book(
    title: str = Form(...),
    author: str = Form(...),
    genre_id: int = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not (user is not None and user.is_admin):
        raise HTTPException(status_code=403, detail="Access denied")

    new_book = Book(title=title, author=author, genre_id=genre_id)
    db.add(new_book)
    db.commit()
    return RedirectResponse(url="/admin/books", status_code=303)

@app.get("/admin/books/edit/{book_id}", response_class=HTMLResponse)
async def edit_book_form(book_id: int, request: Request, db: Session = Depends(get_db),
                         user: User = Depends(get_current_user)):
    if not (user is not None and user.is_admin):
        raise HTTPException(status_code=403, detail="Access denied")

    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return templates.TemplateResponse("edit_book.html", {"request": request, "book": book})


@app.post("/admin/books/edit/{book_id}")
async def edit_book(
        book_id: int,
        title: str = Form(...),
        author: str = Form(...),
        genre_id: int = Form(...),
        published_date: str = Form(...),
        description: str = Form(...),
        photo: str = Form(...),
        price: float = Form(...),
        buy_cnt: int = Form(...),
        db: Session = Depends(get_db),
        user: User = Depends(get_current_user),
):
    if not (user is not None and user.is_admin):
        raise HTTPException(status_code=403, detail="Access denied")

    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    # Преобразование строки в объект datetime
    try:
        published_date_obj = datetime.strptime(published_date, "%Y-%m-%dT%H:%M")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")

    # Обновление данных книги
    book.title = title
    book.author = author
    book.genre_id = genre_id
    book.published_date = published_date_obj
    book.description = description
    book.photo = photo
    book.price = price
    book.buy_cnt = buy_cnt

    db.commit()
    return RedirectResponse(url="/admin/books", status_code=303)


@app.get("/admin/books/delete/{book_id}")
async def delete_book(book_id: int, db: Session = Depends(get_db),
                      user: User = Depends(get_current_user),
                      ):
    if not (user is not None and user.is_admin):
        raise HTTPException(status_code=403, detail="Access denied")
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    db.delete(book)
    db.commit()
    return RedirectResponse(url="/admin/books", status_code=303)



@app.get("/admin/users", response_class=HTMLResponse)
async def admin_users(request: Request, db: Session = Depends(get_db),
    user: User = Depends(get_current_user)):
    if not (user is not None and user.is_admin):
        raise HTTPException(status_code=403, detail="Access denied")
    users = db.query(User).all()
    return templates.TemplateResponse("admin_users.html", {"request": request, "users": users})


@app.get("/admin/users/add", response_class=HTMLResponse)
async def add_user_form(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not (user is not None and user.is_admin):
        raise HTTPException(status_code=403, detail="Access denied")
    roles = db.query(Role).all()
    return templates.TemplateResponse("add_user.html", {"request": request, "user": user, "roles": roles})


@app.post("/admin/users/add")
async def add_user(
    username: str = Form(...),
    email: str = Form(...),
    first_name = Form(...),
    last_name = Form(''),
    password: str = Form(...),
    role: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not (user is not None and user.is_admin):
        raise HTTPException(status_code=403, detail="Access denied")

    new_user = User(username=username, email=email, password=password, first_name=first_name, last_name=last_name)
    role = db.query(Role).filter(Role.name == role).first()
    if role:
        new_user.roles.append(role)
    db.add(new_user)
    db.commit()
    return RedirectResponse(url="/admin/users", status_code=303)


@app.get("/admin/users/edit/{user_id}", response_class=HTMLResponse)
async def edit_user_form(user_id: int, request: Request, db: Session = Depends(get_db),
                         user: User = Depends(get_current_user),
                         ):
    if not (user is not None and user.is_admin):
        raise HTTPException(status_code=403, detail="Access denied")
    user = db.query(User).filter(User.id == user_id).first()
    roles = db.query(Role).all()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return templates.TemplateResponse("edit_user.html", {"request": request, "user": user, "roles": roles})


@app.post("/admin/users/edit/{user_id}")
async def edit_user(
    user_id: int,
    username: str = Form(...),
    email: str = Form(...),
    role: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not (user is not None and user.is_admin):
        raise HTTPException(status_code=403, detail="Access denied")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.username = username
    user.email = email
    user.roles = [db.query(Role).filter(Role.name == role).first()]
    db.commit()
    return RedirectResponse(url="/admin/users", status_code=303)


@app.get("/admin/users/delete/{user_id}")
async def delete_user(user_id: int, db: Session = Depends(get_db),
                      user: User = Depends(get_current_user),
                      ):
    if not (user is not None and user.is_admin):
        raise HTTPException(status_code=403, detail="Access denied")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return RedirectResponse(url="/admin/users", status_code=303)




@app.get("/admin/roles")
def list_roles(request: Request, db: Session = Depends(get_db),
               user: User = Depends(get_current_user),
               ):
    if not (user is not None and user.is_admin):
        raise HTTPException(status_code=403, detail="Access denied")
    roles = db.query(Role).all()
    return templates.TemplateResponse("admin_roles.html", {"request": request, "roles": roles})


@app.get("/admin/roles/add")
def add_role_form(request: Request, user: User = Depends(get_current_user)):
    if not (user is not None and user.is_admin):
        raise HTTPException(status_code=403, detail="Access denied")
    return templates.TemplateResponse("add_role.html", {"request": request})


@app.post("/admin/roles/add")
def add_role(name: str = Form(...), db: Session = Depends(get_db),
             user: User = Depends(get_current_user)):
    if not (user is not None and user.is_admin):
        raise HTTPException(status_code=403, detail="Access denied")
    role = Role(name=name)
    db.add(role)
    db.commit()
    return RedirectResponse(url="/admin/roles", status_code=303)


@app.get("/admin/roles/edit/{role_id}")
def edit_role_form(role_id: int, request: Request, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user),
                   ):
    if not (user is not None and user.is_admin):
        raise HTTPException(status_code=403, detail="Access denied")
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    return templates.TemplateResponse("edit_role.html", {"request": request, "role": role})


@app.post("/admin/roles/edit/{role_id}")
def edit_role(role_id: int, name: str = Form(...), db: Session = Depends(get_db),
              user: User = Depends(get_current_user),
              ):
    if not (user is not None and user.is_admin):
        raise HTTPException(status_code=403, detail="Access denied")
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    role.name = name
    db.commit()
    return RedirectResponse(url="/admin/roles", status_code=303)


@app.get("/admin/roles/delete/{role_id}")
def delete_role(role_id: int, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    if not (user is not None and user.is_admin):
        raise HTTPException(status_code=403, detail="Access denied")
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    db.delete(role)
    db.commit()
    return RedirectResponse(url="/admin/roles", status_code=303)
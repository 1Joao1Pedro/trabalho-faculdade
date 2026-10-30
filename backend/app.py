"""API do Cadastro Seguro. A interface web consome esta API em /api."""

from __future__ import annotations

import os
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator
from pwdlib import PasswordHash
from sqlalchemy import DateTime, ForeignKey, String, Text, create_engine, func, or_, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker
from starlette.middleware.sessions import SessionMiddleware


DEFAULT_DATABASE = Path(__file__).resolve().parent.parent / "cadastro_seguro.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DATABASE}")
SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_urlsafe(48)
engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(engine, expire_on_commit=False)
password_hash = PasswordHash.recommended()


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="user")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(60), index=True)
    description: Mapped[str] = mapped_column(Text)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    user: Mapped[User | None] = relationship()


class RegisterInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    password_confirmation: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def passwords_match(self):
        if self.password != self.password_confirmation:
            raise ValueError("A confirmação da senha não confere.")
        return self


class LoginInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: str
    role: str
    created_at: datetime


class AuditView(BaseModel):
    id: int
    user: str | None
    action: str
    description: str
    ip_address: str | None
    created_at: datetime


app = FastAPI(title="Cadastro Seguro API", version="1.0.0")
frontend_origins = os.getenv("FRONTEND_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",")
app.add_middleware(CORSMiddleware, allow_origins=[origin.strip() for origin in frontend_origins], allow_credentials=True, allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"], allow_headers=["Content-Type", "X-CSRF-Token"])
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, session_cookie="cadastro_session", same_site="lax", https_only=os.getenv("COOKIE_SECURE", "false").lower() == "true")
Base.metadata.create_all(engine)


def db_session():
    with SessionLocal() as db:
        yield db


DB = Annotated[Session, Depends(db_session)]
attempts: dict[str, deque[float]] = defaultdict(deque)
registration_attempts: dict[str, deque[float]] = defaultdict(deque)
last_rate_limit_cleanup = 0.0


def cleanup_rate_limits(now: float):
    global last_rate_limit_cleanup
    if now - last_rate_limit_cleanup < 60:
        return
    for bucket in (attempts, registration_attempts):
        for key, timestamps in list(bucket.items()):
            while timestamps and now - timestamps[0] > 60:
                timestamps.popleft()
            if not timestamps:
                del bucket[key]
    last_rate_limit_cleanup = now


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def audit(db: Session, request: Request, action: str, description: str, user_id: int | None = None):
    db.add(AuditLog(user_id=user_id, action=action, description=description, ip_address=client_ip(request)))


def current_user(request: Request, db: DB) -> User:
    user_id = request.session.get("user_id")
    user = db.get(User, user_id) if user_id else None
    if user is None:
        raise HTTPException(status_code=401, detail="Faça login para continuar.")
    return user


def administrator(request: Request, db: DB) -> User:
    user = current_user(request, db)
    if user.role != "admin":
        audit(db, request, "access.denied", "Tentativa de acesso à área administrativa.", user.id)
        db.commit()
        raise HTTPException(status_code=403, detail="Acesso permitido somente para administradores.")
    return user


def superuser(request: Request, db: DB) -> User:
    user = current_user(request, db)
    if user.role != "superuser":
        audit(db, request, "access.denied", "Tentativa de acesso à consulta de superusuário.", user.id)
        db.commit()
        raise HTTPException(status_code=403, detail="Acesso permitido somente para superusuários.")
    return user


def csrf(request: Request):
    header = request.headers.get("x-csrf-token")
    session_token = request.session.get("csrf_token")
    if not session_token or not header or not secrets.compare_digest(session_token, header):
        raise HTTPException(status_code=403, detail="Token de segurança inválido. Atualize a página.")


@app.get("/api/csrf")
def csrf_token(request: Request, response: Response):
    token = request.session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["csrf_token"] = token
    return {"csrf_token": token}


@app.get("/api/me", response_model=UserView)
def me(user: Annotated[User, Depends(current_user)]):
    return user


@app.post("/api/register", response_model=UserView, status_code=201, dependencies=[Depends(csrf)])
def register(data: RegisterInput, request: Request, db: DB):
    key = client_ip(request) or "unknown"
    now = time.monotonic()
    cleanup_rate_limits(now)
    recent = registration_attempts[key]
    while recent and now - recent[0] > 60:
        recent.popleft()
    if len(recent) >= 10:
        raise HTTPException(status_code=429, detail="Muitos cadastros deste endereço. Aguarde um minuto.")
    recent.append(now)

    email = str(data.email).lower()
    if db.scalar(select(User).where(func.lower(User.email) == email)):
        raise HTTPException(status_code=409, detail="Este e-mail já está cadastrado.")
    user = User(name=data.name.strip(), email=email, password_hash=password_hash.hash(data.password), role="user")
    db.add(user)
    db.flush()
    audit(db, request, "user.created", "Conta cadastrada.", user.id)
    db.commit()
    request.session["user_id"] = user.id
    return user


@app.post("/api/login", dependencies=[Depends(csrf)])
def login(data: LoginInput, request: Request, db: DB):
    key = f"{client_ip(request)}:{str(data.email).lower()}"
    now = time.monotonic()
    cleanup_rate_limits(now)
    while attempts[key] and now - attempts[key][0] > 60:
        attempts[key].popleft()
    if len(attempts[key]) >= 5:
        raise HTTPException(status_code=429, detail="Muitas tentativas. Aguarde um minuto.")
    user = db.scalar(select(User).where(func.lower(User.email) == str(data.email).lower()))
    if not user or not password_hash.verify(data.password, user.password_hash):
        attempts[key].append(now)
        audit(db, request, "login.failed", "Tentativa de login inválida.", user.id if user else None)
        db.commit()
        raise HTTPException(status_code=401, detail="E-mail ou senha incorretos.")
    attempts.pop(key, None)
    csrf_value = request.session.get("csrf_token")
    request.session.clear()
    if csrf_value:
        request.session["csrf_token"] = csrf_value
    request.session["user_id"] = user.id
    audit(db, request, "login.success", "Entrada no sistema.", user.id)
    db.commit()
    return {"user": UserView.model_validate(user), "redirect": "/admin" if user.role in {"admin", "superuser"} else "/perfil"}


@app.post("/api/logout", dependencies=[Depends(csrf)])
def logout(request: Request, db: DB, user: Annotated[User, Depends(current_user)]):
    audit(db, request, "logout", "Saída do sistema.", user.id)
    db.commit()
    request.session.pop("user_id", None)
    return {"ok": True}


@app.put("/api/me", response_model=UserView, dependencies=[Depends(csrf)])
def update_me(data: UserUpdate, request: Request, db: DB, user: Annotated[User, Depends(current_user)]):
    email = str(data.email).lower()
    if db.scalar(select(User).where(func.lower(User.email) == email, User.id != user.id)):
        raise HTTPException(status_code=409, detail="Este e-mail já está cadastrado.")
    user.name, user.email = data.name.strip(), email
    if data.password:
        user.password_hash = password_hash.hash(data.password)
    audit(db, request, "profile.updated", "Dados próprios atualizados.", user.id)
    db.commit()
    return user


@app.get("/api/admin/users", response_model=list[UserView])
def list_users(request: Request, db: DB, admin: Annotated[User, Depends(administrator)], q: str = "", limit: int = 10, offset: int = 0):
    if len(q) > 100 or not 1 <= limit <= 100 or offset < 0:
        raise HTTPException(status_code=422, detail="Parâmetros de busca inválidos.")
    stmt = select(User).where(User.role == "user")
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(or_(User.name.ilike(pattern), User.email.ilike(pattern)))
    return db.scalars(stmt.order_by(User.id.desc()).offset(offset).limit(limit)).all()


@app.get("/api/superuser/users", response_model=list[UserView])
def list_all_registrations(request: Request, db: DB, root: Annotated[User, Depends(superuser)], q: str = ""):
    if len(q) > 100:
        raise HTTPException(status_code=422, detail="Parâmetros de busca inválidos.")
    stmt = select(User).where(User.id != root.id)
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(or_(User.name.ilike(pattern), User.email.ilike(pattern)))
    results = db.scalars(stmt.order_by(User.id.desc())).all()
    # Registrar a consulta de dados pessoais na trilha de auditoria.
    audit(db, request, "superuser.viewed", "Superusuário consultou cadastros.", root.id)
    db.commit()
    return results


@app.put("/api/admin/users/{user_id}", response_model=UserView, dependencies=[Depends(csrf)])
def admin_update_user(user_id: int, data: UserUpdate, request: Request, db: DB, admin: Annotated[User, Depends(administrator)]):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    if user.role != "user":
        raise HTTPException(status_code=403, detail="Administradores só podem editar contas comuns.")
    email = str(data.email).lower()
    if db.scalar(select(User).where(func.lower(User.email) == email, User.id != user.id)):
        raise HTTPException(status_code=409, detail="Este e-mail já está cadastrado.")
    user.name, user.email = data.name.strip(), email
    if data.password:
        user.password_hash = password_hash.hash(data.password)
    audit(db, request, "user.updated", f"Cadastro do usuário #{user.id} atualizado pelo administrador.", admin.id)
    db.commit()
    return user


@app.delete("/api/admin/users/{user_id}", status_code=204, dependencies=[Depends(csrf)])
def delete_user(user_id: int, request: Request, db: DB, admin: Annotated[User, Depends(administrator)]):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    if user.role != "user":
        raise HTTPException(status_code=403, detail="Contas administrativas não podem ser excluídas por esta operação.")
    audit(db, request, "user.deleted", f"Usuário #{user.id} excluído.", admin.id)
    db.delete(user)
    db.commit()


@app.get("/api/admin/audit", response_model=list[AuditView])
def audit_history(db: DB, admin: Annotated[User, Depends(administrator)], limit: int = 50, offset: int = 0):
    rows = db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).offset(offset).limit(min(max(limit, 1), 100))).all()
    return [AuditView(id=row.id, user=row.user.name if row.user else None, action=row.action, description=row.description, ip_address=row.ip_address, created_at=row.created_at) for row in rows]


@app.get("/api/admin/summary")
def summary(db: DB, admin: Annotated[User, Depends(administrator)]):
    return {"users": db.scalar(select(func.count()).select_from(User)), "administrators": db.scalar(select(func.count()).select_from(User).where(User.role == "admin"))}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def home():
    return {"name": "Cadastro Seguro API", "documentation": "/docs"}

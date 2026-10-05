from datetime import datetime, timedelta

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import S
from .db import get_db
from .models import User

bearer = HTTPBearer(auto_error=False)


def hash_pw(p: str) -> str:
    return bcrypt.hashpw(p.encode()[:72], bcrypt.gensalt()).decode()


def check_pw(p: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(p.encode()[:72], h.encode())
    except ValueError:
        return False


def make_token(uid: int) -> str:
    return jwt.encode({"sub": str(uid), "exp": datetime.utcnow() + timedelta(hours=S.jwt_hours)}, S.jwt_secret, "HS256")


def current_user(cred: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if not cred:
        raise HTTPException(401, "ابتدا وارد شوید.")
    try:
        uid = int(jwt.decode(cred.credentials, S.jwt_secret, ["HS256"])["sub"])
    except Exception:
        raise HTTPException(401, "نشست شما منقضی شده؛ دوباره وارد شوید.")
    user = db.get(User, uid)
    if not user:
        raise HTTPException(401, "کاربر پیدا نشد.")
    return user

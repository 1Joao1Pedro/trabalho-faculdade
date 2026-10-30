import argparse
import getpass

from pydantic import EmailStr, TypeAdapter, ValidationError

from app import SessionLocal, User, password_hash

parser = argparse.ArgumentParser()
parser.add_argument("--superuser", action="store_true", help="cria uma conta com acesso de superusuário")
role = "superuser" if parser.parse_args().superuser else "admin"
label = "superusuário" if role == "superuser" else "administrador"

name = input(f"Nome do {label}: ").strip()
try:
    email = TypeAdapter(EmailStr).validate_python(input("E-mail: ").strip()).lower()
except ValidationError:
    raise SystemExit("Informe um e-mail válido.")
password = getpass.getpass("Senha (mínimo 8 caracteres): ")
if not name or len(name) > 100 or len(email) > 255 or len(password) < 8 or len(password) > 128:
    raise SystemExit("Nome e senha fora dos limites permitidos.")
with SessionLocal() as db:
    if db.query(User).filter(User.email == email).first():
        raise SystemExit("Este e-mail já está cadastrado.")
    db.add(User(name=name, email=email, password_hash=password_hash.hash(password), role=role))
    db.commit()
print(f"Conta de {label} criada.")

import os
from pathlib import Path


def _normalize_database_uri(uri: str) -> str:
    """Normaliza a URI de banco para SQLAlchemy.

    - Se não houver URI no ambiente, usa instance/manutencao.db (se existir)
      ou cai para sqlite:///manutencao.db.
    - Ajusta postgres:// -> postgresql:// (compatibilidade com SQLAlchemy).
    """
    if not uri:
        base = Path(__file__).resolve().parent
        candidate = base / "instance" / "manutencao.db"
        if candidate.exists():
            return f"sqlite:///{candidate.as_posix()}"
        return "sqlite:///manutencao.db"

    if uri.startswith("postgres://"):
        uri = uri.replace("postgres://", "postgresql://", 1)

    return uri


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "troque-esta-chave-para-producao")

    # prioridade: SQLALCHEMY_DATABASE_URI > DATABASE_URL
    _raw_db_uri = os.getenv("SQLALCHEMY_DATABASE_URI") or os.getenv("DATABASE_URL")
    SQLALCHEMY_DATABASE_URI = _normalize_database_uri(_raw_db_uri or "")

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEFAULT_ALERT_HOURS = int(os.getenv("DEFAULT_ALERT_HOURS", "20"))
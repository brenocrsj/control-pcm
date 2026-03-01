import os

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///manutencao.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Limiar padrão (se o plano não tiver alerta definido)
    DEFAULT_ALERT_HOURS = 20
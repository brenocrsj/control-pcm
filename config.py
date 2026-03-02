import os

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "troque-esta-chave-para-producao")
    SQLALCHEMY_DATABASE_URI = os.getenv("SQLALCHEMY_DATABASE_URI", "sqlite:///manutencao.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    DEFAULT_ALERT_HOURS = int(os.getenv("DEFAULT_ALERT_HOURS", "20"))
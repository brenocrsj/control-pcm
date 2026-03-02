from __future__ import annotations
from datetime import datetime, date
import enum

from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

from .extensions import db


class PlanType(enum.Enum):
    PREVENTIVA = "PREVENTIVA"
    LUBRIFICACAO = "LUBRIFICACAO"


class OsStatus(enum.Enum):
    ABERTA = "ABERTA"
    EM_ANDAMENTO = "EM_ANDAMENTO"
    AGUARDANDO_PECA = "AGUARDANDO_PECA"
    CONCLUIDA = "CONCLUIDA"
    CANCELADA = "CANCELADA"


OPEN_OS_STATUSES = (
    OsStatus.ABERTA.value,
    OsStatus.EM_ANDAMENTO.value,
    OsStatus.AGUARDANDO_PECA.value,
)


# -------------------------
# Auth
# -------------------------
class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(180), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)

    role = db.Column(db.String(20), nullable=False, default="user")  # user/admin
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)

    def is_admin(self) -> bool:
        return self.role == "admin"


# -------------------------
# Core models
# -------------------------
class Equipment(db.Model):
    __tablename__ = "equipamentos"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    codigo = db.Column(db.String(60), nullable=False, unique=True)  # TAG
    tipo = db.Column(db.String(60), nullable=True)

    horimetro_atual = db.Column(db.Integer, nullable=False, default=0)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def open_backlog_count(self) -> int:
        from .models import WorkOrder  # evita circular
        return (
            WorkOrder.query.filter_by(equipamento_id=self.id)
            .filter(WorkOrder.status.in_(OPEN_OS_STATUSES))
            .count()
        )


class MaintenancePlan(db.Model):
    __tablename__ = "planos_manutencao"

    id = db.Column(db.Integer, primary_key=True)
    equipamento_id = db.Column(db.Integer, db.ForeignKey("equipamentos.id"), nullable=False)

    tipo = db.Column(db.String(30), nullable=False)
    descricao = db.Column(db.String(200), nullable=False)

    intervalo_horas = db.Column(db.Integer, nullable=False)
    alerta_horas = db.Column(db.Integer, nullable=True)

    ultima_execucao_horimetro = db.Column(db.Integer, nullable=False, default=0)
    ultima_execucao_data = db.Column(db.Date, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    equipamento = db.relationship("Equipment", backref=db.backref("planos", lazy=True))

    def remaining_hours(self, horimetro_atual: int) -> int:
        return (self.ultima_execucao_horimetro + self.intervalo_horas) - horimetro_atual

    def status(self, horimetro_atual: int, default_alert: int = 20) -> str:
        faltam = self.remaining_hours(horimetro_atual)
        alert = self.alerta_horas if self.alerta_horas is not None else default_alert
        if faltam <= 0:
            return "VENCIDA"
        if faltam <= alert:
            return "PROXIMA"
        return "EM_DIA"


class MaintenanceExecution(db.Model):
    __tablename__ = "execucoes_manutencao"

    id = db.Column(db.Integer, primary_key=True)
    plano_id = db.Column(db.Integer, db.ForeignKey("planos_manutencao.id"), nullable=False)
    equipamento_id = db.Column(db.Integer, db.ForeignKey("equipamentos.id"), nullable=False)

    data_execucao = db.Column(db.Date, nullable=False, default=date.today)
    horimetro_execucao = db.Column(db.Integer, nullable=False)
    observacoes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    plano = db.relationship("MaintenancePlan", backref=db.backref("execucoes", lazy=True))
    equipamento = db.relationship("Equipment", backref=db.backref("execucoes", lazy=True))


class WorkOrder(db.Model):
    __tablename__ = "ordens_servico"

    id = db.Column(db.Integer, primary_key=True)
    equipamento_id = db.Column(db.Integer, db.ForeignKey("equipamentos.id"), nullable=False)

    titulo = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text, nullable=True)

    prioridade = db.Column(db.String(20), nullable=False, default="MEDIA")
    status = db.Column(db.String(30), nullable=False, default=OsStatus.ABERTA.value)

    opened_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    closed_at = db.Column(db.DateTime, nullable=True)

    equipamento = db.relationship("Equipment", backref=db.backref("os", lazy=True))


class HorimeterLog(db.Model):
    __tablename__ = "horimetro_log"

    id = db.Column(db.Integer, primary_key=True)
    equipamento_id = db.Column(db.Integer, db.ForeignKey("equipamentos.id"), nullable=False)

    data_registro = db.Column(db.Date, nullable=False, default=date.today)
    horimetro = db.Column(db.Integer, nullable=False)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    equipamento = db.relationship("Equipment", backref=db.backref("horimetros", lazy=True))
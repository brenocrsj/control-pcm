from datetime import datetime, date
from enum import Enum

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class PlanType(str, Enum):
    PREVENTIVA = "PREVENTIVA"
    LUBRIFICACAO = "LUBRIFICACAO"


class OsStatus(str, Enum):
    ABERTA = "ABERTA"
    EM_ANDAMENTO = "EM_ANDAMENTO"
    AGUARDANDO_PECA = "AGUARDANDO_PECA"
    CONCLUIDA = "CONCLUIDA"
    CANCELADA = "CANCELADA"


OPEN_OS_STATUSES = {OsStatus.ABERTA.value, OsStatus.EM_ANDAMENTO.value, OsStatus.AGUARDANDO_PECA.value}


class Equipment(db.Model):
    __tablename__ = "equipamentos"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    codigo = db.Column(db.String(50), unique=True, nullable=False)
    tipo = db.Column(db.String(80), nullable=True)
    horimetro_atual = db.Column(db.Integer, nullable=False, default=0)
    ativo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    planos = db.relationship("MaintenancePlan", backref="equipamento", cascade="all, delete-orphan")
    os = db.relationship("WorkOrder", backref="equipamento", cascade="all, delete-orphan")

    def open_backlog_count(self) -> int:
        return sum(1 for o in self.os if o.status in OPEN_OS_STATUSES)


class MaintenancePlan(db.Model):
    __tablename__ = "planos_manutencao"

    id = db.Column(db.Integer, primary_key=True)
    equipamento_id = db.Column(db.Integer, db.ForeignKey("equipamentos.id"), nullable=False)

    tipo = db.Column(db.String(20), nullable=False)  # PREVENTIVA / LUBRIFICACAO
    descricao = db.Column(db.String(200), nullable=False)

    intervalo_horas = db.Column(db.Integer, nullable=False)
    alerta_horas = db.Column(db.Integer, nullable=True)  # se null, usa default

    ultima_execucao_horimetro = db.Column(db.Integer, nullable=False, default=0)
    ultima_execucao_data = db.Column(db.Date, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    execucoes = db.relationship("MaintenanceExecution", backref="plano", cascade="all, delete-orphan")

    def next_due_at(self) -> int:
        return int(self.ultima_execucao_horimetro) + int(self.intervalo_horas)

    def remaining_hours(self, current_horimeter: int) -> int:
        return self.next_due_at() - int(current_horimeter)

    def status(self, current_horimeter: int, default_alert: int = 20) -> str:
        faltam = self.remaining_hours(current_horimeter)
        alerta = self.alerta_horas if self.alerta_horas is not None else default_alert
        if faltam <= 0:
            return "VENCIDA"
        if faltam <= alerta:
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

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class WorkOrder(db.Model):
    __tablename__ = "ordens_servico"

    id = db.Column(db.Integer, primary_key=True)
    equipamento_id = db.Column(db.Integer, db.ForeignKey("equipamentos.id"), nullable=False)

    titulo = db.Column(db.String(150), nullable=False)
    descricao = db.Column(db.Text, nullable=True)

    prioridade = db.Column(db.String(20), nullable=False, default="MEDIA")  # BAIXA/MEDIA/ALTA/URGENTE
    status = db.Column(db.String(30), nullable=False, default=OsStatus.ABERTA.value)

    opened_at = db.Column(db.DateTime, default=datetime.utcnow)
    closed_at = db.Column(db.DateTime, nullable=True)

    def is_open(self) -> bool:
        return self.status in OPEN_OS_STATUSES
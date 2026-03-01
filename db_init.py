import os
from pathlib import Path

from app import create_app
from models import db, Equipment, MaintenancePlan, WorkOrder, PlanType, OsStatus


def _resolve_sqlite_path(database_uri: str) -> Path | None:
    """
    Converte sqlite:///arquivo.db em Path absoluto.
    Retorna None se não for sqlite local.
    """
    if database_uri.startswith("sqlite:///"):
        fname = database_uri.replace("sqlite:///", "", 1)
        return Path(fname).resolve()
    return None


def _show_db_info(app):
    uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    print("📦 SQLALCHEMY_DATABASE_URI =", uri)
    db_path = _resolve_sqlite_path(uri)
    if db_path:
        print("📦 SQLite arquivo =", db_path)
    else:
        print("📦 Banco não é sqlite local (provavelmente Postgres/MySQL).")


def _reset_db_if_requested(app):
    """
    Se executar com RESET_DB=1, apaga o sqlite local e recria do zero.
    """
    if os.getenv("RESET_DB", "0") != "1":
        return

    uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    db_path = _resolve_sqlite_path(uri)

    if not db_path:
        print("⚠️ RESET_DB=1 ignorado: só apaga automaticamente quando for sqlite:///arquivo.db")
        return

    if db_path.exists():
        db_path.unlink()
        print(f"🧹 RESET_DB=1 → removido: {db_path}")
    else:
        print(f"🧹 RESET_DB=1 → arquivo não existe: {db_path}")


def seed_if_empty():
    """
    Cria dados exemplo (igual ao painel) apenas se ainda não existir equipamento.
    """
    if Equipment.query.first():
        print("✅ Banco já tem dados. Não repliquei.")
        return

    cam = Equipment(nome="Caminhão 01", codigo="TRK-123", tipo="Caminhão", horimetro_atual=1650)
    pa = Equipment(nome="Pá Carregadeira", codigo="PC-456", tipo="Pá", horimetro_atual=2350)
    esc = Equipment(nome="Escavadeira", codigo="ESC-789", tipo="Escavadeira", horimetro_atual=3120)
    tr = Equipment(nome="Trator Agricola", codigo="TR-321", tipo="Trator", horimetro_atual=795)

    db.session.add_all([cam, pa, esc, tr])
    db.session.commit()

    # Preventivas (alerta 20h)
    db.session.add_all([
        MaintenancePlan(
            equipamento_id=cam.id,
            tipo=PlanType.PREVENTIVA.value,
            descricao="Preventiva Geral",
            intervalo_horas=250,
            alerta_horas=20,
            ultima_execucao_horimetro=1400,
        ),
        MaintenancePlan(
            equipamento_id=pa.id,
            tipo=PlanType.PREVENTIVA.value,
            descricao="Preventiva Geral",
            intervalo_horas=250,
            alerta_horas=20,
            ultima_execucao_horimetro=2330,
        ),
        MaintenancePlan(
            equipamento_id=esc.id,
            tipo=PlanType.PREVENTIVA.value,
            descricao="Preventiva Geral",
            intervalo_horas=250,
            alerta_horas=20,
            ultima_execucao_horimetro=3000,
        ),
        MaintenancePlan(
            equipamento_id=tr.id,
            tipo=PlanType.PREVENTIVA.value,
            descricao="Preventiva Geral",
            intervalo_horas=250,
            alerta_horas=20,
            ultima_execucao_horimetro=780,
        ),
    ])
    db.session.commit()

    # Lubrificação (alerta 10h)
    db.session.add_all([
        MaintenancePlan(
            equipamento_id=cam.id,
            tipo=PlanType.LUBRIFICACAO.value,
            descricao="Lubrificação",
            intervalo_horas=100,
            alerta_horas=10,
            ultima_execucao_horimetro=1570,
        ),
        MaintenancePlan(
            equipamento_id=pa.id,
            tipo=PlanType.LUBRIFICACAO.value,
            descricao="Lubrificação",
            intervalo_horas=50,
            alerta_horas=10,
            ultima_execucao_horimetro=2335,
        ),
        MaintenancePlan(
            equipamento_id=esc.id,
            tipo=PlanType.LUBRIFICACAO.value,
            descricao="Lubrificação",
            intervalo_horas=80,
            alerta_horas=10,
            ultima_execucao_horimetro=3080,
        ),
        MaintenancePlan(
            equipamento_id=tr.id,
            tipo=PlanType.LUBRIFICACAO.value,
            descricao="Lubrificação",
            intervalo_horas=40,
            alerta_horas=10,
            ultima_execucao_horimetro=790,
        ),
    ])
    db.session.commit()

    # Backlog (OS abertas)
    db.session.add_all([
        WorkOrder(equipamento_id=cam.id, titulo="Vazamento óleo", prioridade="ALTA", status=OsStatus.ABERTA.value),
        WorkOrder(equipamento_id=cam.id, titulo="Trocar filtro ar", prioridade="MEDIA", status=OsStatus.EM_ANDAMENTO.value),
        WorkOrder(equipamento_id=cam.id, titulo="Revisar freios", prioridade="URGENTE", status=OsStatus.AGUARDANDO_PECA.value),
        WorkOrder(equipamento_id=cam.id, titulo="Ajuste correia", prioridade="BAIXA", status=OsStatus.ABERTA.value),
        WorkOrder(equipamento_id=pa.id, titulo="Ruído na transmissão", prioridade="ALTA", status=OsStatus.ABERTA.value),
        WorkOrder(equipamento_id=pa.id, titulo="Checar pneus", prioridade="MEDIA", status=OsStatus.ABERTA.value),
        WorkOrder(equipamento_id=tr.id, titulo="Trocar lâmpada", prioridade="BAIXA", status=OsStatus.ABERTA.value),
    ])
    db.session.commit()

    print("✅ Banco criado e populado com dados de exemplo!")


def main():
    app = create_app()

    _show_db_info(app)
    _reset_db_if_requested(app)

    with app.app_context():
        db.create_all()
        print("✅ Tabelas criadas com sucesso!")
        seed_if_empty()


if __name__ == "__main__":
    main()
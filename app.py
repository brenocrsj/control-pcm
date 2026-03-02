from app import create_app
app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)

import os
from datetime import date, datetime

from flask import Flask, flash, redirect, render_template, request, url_for

from config import Config
from models import (
    db,
    Equipment,
    MaintenancePlan,
    MaintenanceExecution,
    WorkOrder,
    PlanType,
    OsStatus,
    HorimeterLog,  # <- precisa existir no models.py
)


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    # -------------------------
    # Helpers
    # -------------------------
    def parse_int(v, default=0):
        try:
            return int(v)
        except Exception:
            return default

    def parse_date(v):
        if not v:
            return None
        try:
            return datetime.strptime(v, "%Y-%m-%d").date()
        except Exception:
            return None

    # -------------------------
    # Dashboard (filtro por alertas)
    # -------------------------
    @app.route("/")
    def dashboard():
        equipamentos = (
            Equipment.query.filter_by(ativo=True)
            .order_by(Equipment.nome.asc())
            .all()
        )

        default_alert = app.config.get("DEFAULT_ALERT_HOURS", 20)

        # filtro:
        # - alertas (padrão): só preventiva vencida/próxima
        # - alertas_e_backlog: preventiva vencida/próxima OU backlog > 0
        # - all: todos
        filtro = request.args.get("filtro", "alertas")

        cards = []
        total_vencidas = 0
        total_proximas = 0
        total_em_dia = 0

        for e in equipamentos:
            planos_prev = [p for p in e.planos if p.tipo == PlanType.PREVENTIVA.value]
            planos_lub = [p for p in e.planos if p.tipo == PlanType.LUBRIFICACAO.value]

            def summarize(plans):
                if not plans:
                    return {"status": "SEM_PLANO", "faltam": None, "texto": "Sem plano"}

                remaining_list = [(p, p.remaining_hours(e.horimetro_atual)) for p in plans]
                p_min, faltam_min = sorted(remaining_list, key=lambda x: x[1])[0]
                status = p_min.status(e.horimetro_atual, default_alert=default_alert)

                if status == "VENCIDA":
                    return {"status": "VENCIDA", "faltam": faltam_min, "texto": "Vencida!"}
                if status == "PROXIMA":
                    return {"status": "PROXIMA", "faltam": faltam_min, "texto": f"{faltam_min} horas"}
                return {"status": "EM_DIA", "faltam": faltam_min, "texto": f"{faltam_min} horas"}

            prev = summarize(planos_prev)
            lub = summarize(planos_lub)
            backlog = e.open_backlog_count()

            is_prev_alert = prev["status"] in ("VENCIDA", "PROXIMA")
            is_backlog_alert = backlog > 0

            if filtro == "alertas":
                if not is_prev_alert:
                    continue
            elif filtro == "alertas_e_backlog":
                if not (is_prev_alert or is_backlog_alert):
                    continue
            elif filtro == "all":
                pass
            else:
                if not is_prev_alert:
                    continue

            if prev["status"] == "VENCIDA":
                total_vencidas += 1
            elif prev["status"] == "PROXIMA":
                total_proximas += 1
            else:
                total_em_dia += 1

            cards.append({"equip": e, "prev": prev, "lub": lub, "backlog": backlog})

        return render_template(
            "dashboard.html",
            cards=cards,
            total_vencidas=total_vencidas,
            total_proximas=total_proximas,
            total_em_dia=total_em_dia,
            filtro=filtro,
        )

    # -------------------------
    # ✅ ROTA QUE ESTAVA FALTANDO (corrige o BuildError no dashboard)
    # -------------------------
    @app.route("/equipamentos/<int:equip_id>/horimetro", methods=["POST"])
    def equipamento_atualizar_horimetro(equip_id):
        item = Equipment.query.get_or_404(equip_id)

        novo_h = parse_int(request.form.get("horimetro_atual"), item.horimetro_atual)

        if novo_h < item.horimetro_atual:
            flash(f"Horímetro não pode diminuir. Atual: {item.horimetro_atual}h.", "danger")
            return redirect(url_for("dashboard", filtro=request.args.get("filtro", "alertas")))

        item.horimetro_atual = novo_h

        # registra log com data de hoje
        log = HorimeterLog(equipamento_id=item.id, data_registro=date.today(), horimetro=novo_h)
        db.session.add(log)

        db.session.commit()
        flash(f"Horímetro atualizado para {novo_h}h em {item.nome}.", "success")
        return redirect(url_for("dashboard", filtro=request.args.get("filtro", "alertas")))

    # -------------------------
    # ✅ TELA EXCLUSIVA DE HORÍMETRO (lista e atualiza em massa)
    # -------------------------
    @app.route("/horimetros", methods=["GET", "POST"])
    def horimetros():
        equipamentos = (
            Equipment.query.filter_by(ativo=True)
            .order_by(Equipment.nome.asc())
            .all()
        )

        if request.method == "POST":
            data_str = (request.form.get("data_registro") or "").strip()
            data_registro = parse_date(data_str) or date.today()

            total_salvos = 0

            for e in equipamentos:
                field = f"novo_h_{e.id}"
                raw = (request.form.get(field) or "").strip()
                if not raw:
                    continue

                novo_h = parse_int(raw, None)
                if novo_h is None:
                    continue

                if novo_h < e.horimetro_atual:
                    flash(f"{e.codigo}: horímetro não pode diminuir (atual {e.horimetro_atual}h).", "danger")
                    continue

                e.horimetro_atual = novo_h
                db.session.add(HorimeterLog(equipamento_id=e.id, data_registro=data_registro, horimetro=novo_h))
                total_salvos += 1

            if total_salvos > 0:
                db.session.commit()
                flash(f"✅ {total_salvos} horímetro(s) atualizado(s) com sucesso!", "success")
            else:
                flash("Nenhum horímetro foi atualizado (preencha os campos que deseja alterar).", "warning")

            return redirect(url_for("horimetros"))

        hoje = date.today()
        rows = []

        for e in equipamentos:
            last = (
                HorimeterLog.query.filter_by(equipamento_id=e.id)
                .order_by(HorimeterLog.data_registro.desc(), HorimeterLog.id.desc())
                .first()
            )
            last_date = last.data_registro if last else None
            dias = (hoje - last_date).days if last_date else 9999

            rows.append({"equip": e, "last_date": last_date, "dias": dias})

        return render_template("horimetros.html", rows=rows, hoje=hoje)

    # -------------------------
    # Equipamentos (CRUD)
    # -------------------------
    @app.route("/equipamentos")
    def equipamentos():
        items = Equipment.query.order_by(Equipment.ativo.desc(), Equipment.nome.asc()).all()
        return render_template("equipamentos.html", items=items)

    @app.route("/equipamentos/novo", methods=["GET", "POST"])
    def equipamento_novo():
        if request.method == "POST":
            nome = (request.form.get("nome") or "").strip()
            codigo = (request.form.get("codigo") or "").strip()
            tipo = (request.form.get("tipo") or "").strip()
            horimetro = parse_int(request.form.get("horimetro_atual"), 0)

            if not nome or not codigo:
                flash("Nome e Código são obrigatórios.", "danger")
                return render_template("equipamento_form.html", item=None)

            if Equipment.query.filter_by(codigo=codigo).first():
                flash("Já existe um equipamento com esse código.", "danger")
                return render_template("equipamento_form.html", item=None)

            e = Equipment(nome=nome, codigo=codigo, tipo=tipo, horimetro_atual=horimetro, ativo=True)
            db.session.add(e)
            db.session.commit()
            flash("Equipamento criado!", "success")
            return redirect(url_for("equipamentos"))

        return render_template("equipamento_form.html", item=None)

    @app.route("/equipamentos/<int:equip_id>/editar", methods=["GET", "POST"])
    def equipamento_editar(equip_id):
        item = Equipment.query.get_or_404(equip_id)

        if request.method == "POST":
            item.nome = (request.form.get("nome") or "").strip()
            item.codigo = (request.form.get("codigo") or "").strip()
            item.tipo = (request.form.get("tipo") or "").strip()
            item.horimetro_atual = parse_int(request.form.get("horimetro_atual"), item.horimetro_atual)
            item.ativo = (request.form.get("ativo") == "on")

            db.session.commit()
            flash("Equipamento atualizado!", "success")
            return redirect(url_for("equipamentos"))

        return render_template("equipamento_form.html", item=item)

    # -------------------------
    # Planos (CRUD)
    # -------------------------
    @app.route("/planos")
    def planos():
        items = MaintenancePlan.query.order_by(MaintenancePlan.tipo.asc(), MaintenancePlan.id.desc()).all()
        return render_template("planos.html", items=items)

    @app.route("/planos/novo", methods=["GET", "POST"])
    def plano_novo():
        equipamentos = Equipment.query.filter_by(ativo=True).order_by(Equipment.nome.asc()).all()

        if request.method == "POST":
            equipamento_id = parse_int(request.form.get("equipamento_id"))
            tipo = (request.form.get("tipo") or "").strip()
            descricao = (request.form.get("descricao") or "").strip()
            intervalo_horas = parse_int(request.form.get("intervalo_horas"), 0)

            alerta_raw = (request.form.get("alerta_horas") or "").strip()
            alerta_horas = parse_int(alerta_raw, None) if alerta_raw else None

            ultima_h = parse_int(request.form.get("ultima_execucao_horimetro"), 0)
            ultima_d = parse_date(request.form.get("ultima_execucao_data"))

            if not equipamento_id or tipo not in (PlanType.PREVENTIVA.value, PlanType.LUBRIFICACAO.value):
                flash("Selecione equipamento e tipo.", "danger")
                return render_template("plano_form.html", item=None, equipamentos=equipamentos)

            if not descricao or intervalo_horas <= 0:
                flash("Descrição e intervalo (horas) são obrigatórios.", "danger")
                return render_template("plano_form.html", item=None, equipamentos=equipamentos)

            p = MaintenancePlan(
                equipamento_id=equipamento_id,
                tipo=tipo,
                descricao=descricao,
                intervalo_horas=intervalo_horas,
                alerta_horas=alerta_horas,
                ultima_execucao_horimetro=ultima_h,
                ultima_execucao_data=ultima_d,
            )
            db.session.add(p)
            db.session.commit()
            flash("Plano criado!", "success")
            return redirect(url_for("planos"))

        return render_template("plano_form.html", item=None, equipamentos=equipamentos)

    @app.route("/planos/<int:plano_id>/editar", methods=["GET", "POST"])
    def plano_editar(plano_id):
        item = MaintenancePlan.query.get_or_404(plano_id)
        equipamentos = Equipment.query.filter_by(ativo=True).order_by(Equipment.nome.asc()).all()

        if request.method == "POST":
            item.equipamento_id = parse_int(request.form.get("equipamento_id"), item.equipamento_id)

            tipo = (request.form.get("tipo") or "").strip()
            if tipo in (PlanType.PREVENTIVA.value, PlanType.LUBRIFICACAO.value):
                item.tipo = tipo

            item.descricao = (request.form.get("descricao") or "").strip()
            item.intervalo_horas = parse_int(request.form.get("intervalo_horas"), item.intervalo_horas)

            alerta_raw = (request.form.get("alerta_horas") or "").strip()
            item.alerta_horas = parse_int(alerta_raw, None) if alerta_raw else None

            item.ultima_execucao_horimetro = parse_int(
                request.form.get("ultima_execucao_horimetro"),
                item.ultima_execucao_horimetro,
            )
            item.ultima_execucao_data = parse_date(request.form.get("ultima_execucao_data")) or item.ultima_execucao_data

            db.session.commit()
            flash("Plano atualizado!", "success")
            return redirect(url_for("planos"))

        return render_template("plano_form.html", item=item, equipamentos=equipamentos)

    @app.route("/planos/<int:plano_id>/executar", methods=["POST"])
    def plano_executar(plano_id):
        p = MaintenancePlan.query.get_or_404(plano_id)
        e = Equipment.query.get_or_404(p.equipamento_id)

        horimetro_exec = parse_int(request.form.get("horimetro_execucao"), e.horimetro_atual)
        data_exec = parse_date(request.form.get("data_execucao")) or date.today()
        obs = (request.form.get("observacoes") or "").strip()

        ex = MaintenanceExecution(
            plano_id=p.id,
            equipamento_id=e.id,
            data_execucao=data_exec,
            horimetro_execucao=horimetro_exec,
            observacoes=obs or None,
        )
        db.session.add(ex)

        p.ultima_execucao_horimetro = horimetro_exec
        p.ultima_execucao_data = data_exec

        if horimetro_exec > e.horimetro_atual:
            e.horimetro_atual = horimetro_exec

            # log também quando sincroniza
            db.session.add(HorimeterLog(equipamento_id=e.id, data_registro=data_exec, horimetro=horimetro_exec))

        db.session.commit()
        flash("Execução registrada!", "success")
        return redirect(url_for("planos"))

    # -------------------------
    # OS / Backlog
    # -------------------------
    @app.route("/os")
    def os_list():
        status = request.args.get("status")
        q = WorkOrder.query
        if status:
            q = q.filter_by(status=status)
        items = q.order_by(WorkOrder.opened_at.desc()).all()
        return render_template("os_list.html", items=items, status=status, all_statuses=[s.value for s in OsStatus])

    @app.route("/os/nova", methods=["GET", "POST"])
    def os_nova():
        equipamentos = Equipment.query.filter_by(ativo=True).order_by(Equipment.nome.asc()).all()
        all_statuses = [s.value for s in OsStatus]

        if request.method == "POST":
            equipamento_id = parse_int(request.form.get("equipamento_id"))
            titulo = (request.form.get("titulo") or "").strip()
            descricao = (request.form.get("descricao") or "").strip()
            prioridade = (request.form.get("prioridade") or "MEDIA").strip()
            status = (request.form.get("status") or OsStatus.ABERTA.value).strip()

            if not equipamento_id or not titulo:
                flash("Equipamento e título são obrigatórios.", "danger")
                return render_template("os_form.html", item=None, equipamentos=equipamentos, all_statuses=all_statuses)

            o = WorkOrder(
                equipamento_id=equipamento_id,
                titulo=titulo,
                descricao=descricao or None,
                prioridade=prioridade,
                status=status if status in all_statuses else OsStatus.ABERTA.value,
            )
            db.session.add(o)
            db.session.commit()
            flash("OS criada!", "success")
            return redirect(url_for("os_list"))

        return render_template("os_form.html", item=None, equipamentos=equipamentos, all_statuses=all_statuses)

    @app.route("/os/<int:os_id>/editar", methods=["GET", "POST"])
    def os_editar(os_id):
        item = WorkOrder.query.get_or_404(os_id)
        equipamentos = Equipment.query.filter_by(ativo=True).order_by(Equipment.nome.asc()).all()
        all_statuses = [s.value for s in OsStatus]

        if request.method == "POST":
            item.equipamento_id = parse_int(request.form.get("equipamento_id"), item.equipamento_id)
            item.titulo = (request.form.get("titulo") or "").strip()
            item.descricao = (request.form.get("descricao") or "").strip() or None
            item.prioridade = (request.form.get("prioridade") or "MEDIA").strip()

            new_status = (request.form.get("status") or item.status).strip()
            if new_status in all_statuses and new_status != item.status:
                item.status = new_status
                if new_status in (OsStatus.CONCLUIDA.value, OsStatus.CANCELADA.value):
                    item.closed_at = datetime.utcnow()
                else:
                    item.closed_at = None

            db.session.commit()
            flash("OS atualizada!", "success")
            return redirect(url_for("os_list"))

        return render_template("os_form.html", item=item, equipamentos=equipamentos, all_statuses=all_statuses)

    # -------------------------
    # Histórico
    # -------------------------
    @app.route("/historico")
    def historico():
        execs = MaintenanceExecution.query.order_by(MaintenanceExecution.created_at.desc()).limit(200).all()
        oss = (
            WorkOrder.query.filter(WorkOrder.status.in_([OsStatus.CONCLUIDA.value, OsStatus.CANCELADA.value]))
            .order_by(WorkOrder.closed_at.desc())
            .limit(200)
            .all()
        )
        return render_template("historico.html", execs=execs, oss=oss)

    return app


app = create_app()

if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=5000, debug=debug)
from datetime import date, datetime

from flask import render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from . import bp
from ..extensions import db
from ..models import (
    Equipment, MaintenancePlan, PlanType, WorkOrder, OsStatus,
    HorimeterLog
)


def admin_required():
    if not current_user.is_admin():
        abort(403)


@bp.route("/")
@login_required
def dashboard():
    equipamentos = Equipment.query.filter_by(ativo=True).order_by(Equipment.nome.asc()).all()
    default_alert = 20

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


@bp.route("/profile")
@login_required
def profile():
    # perfil bloqueado: só o próprio usuário (aqui sempre é o próprio)
    return render_template("profile.html", u=current_user)


@bp.route("/equipamentos/<int:equip_id>/horimetro", methods=["POST"])
@login_required
def equipamento_atualizar_horimetro(equip_id):
    item = Equipment.query.get_or_404(equip_id)
    try:
        novo_h = int(request.form.get("horimetro_atual", item.horimetro_atual))
    except Exception:
        novo_h = item.horimetro_atual

    if novo_h < item.horimetro_atual:
        flash(f"Horímetro não pode diminuir. Atual: {item.horimetro_atual}h.", "danger")
        return redirect(url_for("main.dashboard", filtro=request.args.get("filtro", "alertas")))

    item.horimetro_atual = novo_h
    db.session.add(HorimeterLog(equipamento_id=item.id, data_registro=date.today(), horimetro=novo_h))
    db.session.commit()

    flash("Horímetro atualizado!", "success")
    return redirect(url_for("main.dashboard", filtro=request.args.get("filtro", "alertas")))


@bp.route("/horimetros", methods=["GET", "POST"])
@login_required
def horimetros():
    equipamentos = Equipment.query.filter_by(ativo=True).order_by(Equipment.nome.asc()).all()

    def parse_date(v):
        if not v:
            return None
        try:
            return datetime.strptime(v, "%Y-%m-%d").date()
        except Exception:
            return None

    if request.method == "POST":
        data_registro = parse_date(request.form.get("data_registro")) or date.today()
        total_salvos = 0

        for e in equipamentos:
            raw = (request.form.get(f"novo_h_{e.id}") or "").strip()
            if not raw:
                continue
            try:
                novo_h = int(raw)
            except Exception:
                continue

            if novo_h < e.horimetro_atual:
                flash(f"{e.codigo}: não pode diminuir (atual {e.horimetro_atual}h).", "danger")
                continue

            e.horimetro_atual = novo_h
            db.session.add(HorimeterLog(equipamento_id=e.id, data_registro=data_registro, horimetro=novo_h))
            total_salvos += 1

        if total_salvos:
            db.session.commit()
            flash(f"✅ {total_salvos} horímetro(s) atualizado(s)!", "success")
        else:
            flash("Nenhum horímetro alterado.", "warning")

        return redirect(url_for("main.horimetros"))

    hoje = date.today()
    rows = []
    for e in equipamentos:
        last = (HorimeterLog.query.filter_by(equipamento_id=e.id)
                .order_by(HorimeterLog.data_registro.desc(), HorimeterLog.id.desc())
                .first())
        last_date = last.data_registro if last else None
        dias = (hoje - last_date).days if last_date else 9999
        rows.append({"equip": e, "last_date": last_date, "dias": dias})

    return render_template("horimetros.html", rows=rows, hoje=hoje)

# -------------------------
# Equipamentos (CRUD básico)
# -------------------------

@bp.route("/equipamentos")
@login_required
def equipamentos():
    items = Equipment.query.order_by(Equipment.nome.asc()).all()
    return render_template("equipamentos_list.html", items=items)


@bp.route("/equipamentos/novo", methods=["GET", "POST"])
@login_required
def equipamento_novo():
    admin_required()

    if request.method == "POST":
        nome = (request.form.get("nome") or "").strip()
        codigo = (request.form.get("codigo") or "").strip()
        tipo = (request.form.get("tipo") or "").strip() or None

        try:
            horimetro_atual = int(request.form.get("horimetro_atual") or 0)
        except Exception:
            horimetro_atual = 0

        ativo = True if request.form.get("ativo") == "on" else False

        if not nome or not codigo:
            flash("Nome e Código são obrigatórios.", "danger")
            return render_template("equipamento_form.html", item=None)

        # evita duplicidade de TAG
        if Equipment.query.filter_by(codigo=codigo).first():
            flash("Já existe um equipamento com esse código (TAG).", "danger")
            return render_template("equipamento_form.html", item=None)

        item = Equipment(
            nome=nome,
            codigo=codigo,
            tipo=tipo,
            horimetro_atual=horimetro_atual,
            ativo=ativo,
        )
        db.session.add(item)
        db.session.commit()

        flash("Equipamento criado!", "success")
        return redirect(url_for("main.equipamentos"))

    return render_template("equipamento_form.html", item=None)


@bp.route("/equipamentos/<int:equip_id>/editar", methods=["GET", "POST"])
@login_required
def equipamento_editar(equip_id):
    admin_required()

    item = Equipment.query.get_or_404(equip_id)

    if request.method == "POST":
        nome = (request.form.get("nome") or "").strip()
        codigo = (request.form.get("codigo") or "").strip()
        tipo = (request.form.get("tipo") or "").strip() or None

        try:
            novo_h = int(request.form.get("horimetro_atual") or item.horimetro_atual)
        except Exception:
            novo_h = item.horimetro_atual

        ativo = True if request.form.get("ativo") == "on" else False

        if not nome or not codigo:
            flash("Nome e Código são obrigatórios.", "danger")
            return render_template("equipamento_form.html", item=item)

        # não deixa mudar TAG para uma já existente em outro registro
        exists = Equipment.query.filter(Equipment.codigo == codigo, Equipment.id != item.id).first()
        if exists:
            flash("Já existe outro equipamento com esse código (TAG).", "danger")
            return render_template("equipamento_form.html", item=item)

        # regra: não pode diminuir horímetro
        if novo_h < item.horimetro_atual:
            flash(f"Horímetro não pode diminuir. Atual: {item.horimetro_atual}h.", "danger")
            return render_template("equipamento_form.html", item=item)

        # atualiza
        item.nome = nome
        item.codigo = codigo
        item.tipo = tipo
        item.ativo = ativo

        if novo_h != item.horimetro_atual:
            item.horimetro_atual = novo_h
            db.session.add(HorimeterLog(equipamento_id=item.id, data_registro=date.today(), horimetro=novo_h))

        db.session.commit()
        flash("Equipamento atualizado!", "success")
        return redirect(url_for("main.equipamentos"))

    return render_template("equipamento_form.html", item=item)


@bp.route("/equipamentos/<int:equip_id>/toggle", methods=["POST"])
@login_required
def equipamento_toggle(equip_id):
    admin_required()

    item = Equipment.query.get_or_404(equip_id)
    item.ativo = not item.ativo
    db.session.commit()
    flash("Status do equipamento atualizado.", "success")
    return redirect(url_for("main.equipamentos"))


# -------------------------
# OS / Backlog
# -------------------------

@bp.route("/os")
@login_required
def os_list():
    status = (request.args.get("status") or "").strip() or None

    q = WorkOrder.query.order_by(WorkOrder.opened_at.desc())
    if status:
        q = q.filter_by(status=status)

    items = q.all()
    all_statuses = [s.value for s in OsStatus]
    return render_template("os_list.html", items=items, status=status, all_statuses=all_statuses)


@bp.route("/os/nova", methods=["GET", "POST"])
@login_required
def os_nova():
    if request.method == "POST":
        try:
            equipamento_id = int(request.form.get("equipamento_id") or 0)
        except Exception:
            equipamento_id = 0

        titulo = (request.form.get("titulo") or "").strip()
        descricao = (request.form.get("descricao") or "").strip() or None
        prioridade = (request.form.get("prioridade") or "MEDIA").strip() or "MEDIA"
        status = (request.form.get("status") or OsStatus.ABERTA.value).strip() or OsStatus.ABERTA.value

        if not equipamento_id or not Equipment.query.get(equipamento_id):
            flash("Selecione um equipamento válido.", "danger")
        elif not titulo:
            flash("Título é obrigatório.", "danger")
        else:
            item = WorkOrder(
                equipamento_id=equipamento_id,
                titulo=titulo,
                descricao=descricao,
                prioridade=prioridade,
                status=status,
            )
            db.session.add(item)
            db.session.commit()
            flash("OS criada!", "success")
            return redirect(url_for("main.os_list"))

    equipamentos = Equipment.query.filter_by(ativo=True).order_by(Equipment.nome.asc()).all()
    all_statuses = [s.value for s in OsStatus]
    return render_template("os_form.html", item=None, equipamentos=equipamentos, all_statuses=all_statuses)


@bp.route("/os/<int:os_id>/editar", methods=["GET", "POST"])
@login_required
def os_editar(os_id):
    item = WorkOrder.query.get_or_404(os_id)

    if request.method == "POST":
        try:
            equipamento_id = int(request.form.get("equipamento_id") or item.equipamento_id)
        except Exception:
            equipamento_id = item.equipamento_id

        titulo = (request.form.get("titulo") or "").strip()
        descricao = (request.form.get("descricao") or "").strip() or None
        prioridade = (request.form.get("prioridade") or item.prioridade).strip() or item.prioridade
        status = (request.form.get("status") or item.status).strip() or item.status

        if not Equipment.query.get(equipamento_id):
            flash("Selecione um equipamento válido.", "danger")
        elif not titulo:
            flash("Título é obrigatório.", "danger")
        else:
            item.equipamento_id = equipamento_id
            item.titulo = titulo
            item.descricao = descricao
            item.prioridade = prioridade

            # fecha data ao concluir/cancelar, reabre se voltar para status aberto
            closing_statuses = {OsStatus.CONCLUIDA.value, OsStatus.CANCELADA.value}
            was_closed = item.status in closing_statuses
            will_close = status in closing_statuses

            item.status = status
            if will_close and not item.closed_at:
                item.closed_at = datetime.utcnow()
            if not will_close and was_closed:
                item.closed_at = None

            db.session.commit()
            flash("OS atualizada!", "success")
            return redirect(url_for("main.os_list"))

    equipamentos = Equipment.query.filter_by(ativo=True).order_by(Equipment.nome.asc()).all()
    all_statuses = [s.value for s in OsStatus]
    return render_template("os_form.html", item=item, equipamentos=equipamentos, all_statuses=all_statuses)
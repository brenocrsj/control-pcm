from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user

from . import bp
from .forms import LoginForm, RegisterForm
from ..extensions import db
from ..models import User


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()
        if not user or not user.check_password(form.password.data):
            flash("E-mail ou senha inválidos.", "danger")
            return render_template("auth_login.html", form=form)

        if not user.is_active:
            flash("Usuário desativado.", "danger")
            return render_template("auth_login.html", form=form)

        login_user(user)
        nxt = request.args.get("next")
        return redirect(nxt or url_for("main.dashboard"))

    return render_template("auth_login.html", form=form)


@bp.route("/registrar", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    form = RegisterForm()
    if form.validate_on_submit():
        email = form.email.data.lower().strip()
        if User.query.filter_by(email=email).first():
            flash("Esse e-mail já está cadastrado.", "danger")
            return render_template("auth_register.html", form=form)

        user = User(name=form.name.data.strip(), email=email, role="user")
        user.set_password(form.password.data)

        db.session.add(user)
        db.session.commit()

        flash("Conta criada! Faça login.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth_register.html", form=form)


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Você saiu do sistema.", "info")
    return redirect(url_for("auth.login"))
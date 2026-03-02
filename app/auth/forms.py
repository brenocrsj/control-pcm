from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo

class LoginForm(FlaskForm):
    email = StringField("E-mail", validators=[DataRequired(), Email()])
    password = PasswordField("Senha", validators=[DataRequired(), Length(min=4)])
    submit = SubmitField("Entrar")

class RegisterForm(FlaskForm):
    name = StringField("Nome", validators=[DataRequired(), Length(min=2, max=120)])
    email = StringField("E-mail", validators=[DataRequired(), Email()])
    password = PasswordField("Senha", validators=[DataRequired(), Length(min=4)])
    confirm = PasswordField("Confirmar senha", validators=[DataRequired(), EqualTo("password")])
    submit = SubmitField("Criar conta")
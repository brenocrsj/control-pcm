from app import create_app
from app.extensions import db
from app.models import User

app = create_app()

with app.app_context():
    email = "admin@pcm.com"
    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(name="Administrador", email=email, role="admin")
        user.set_password("admin123")
        db.session.add(user)
        db.session.commit()
        print("✅ Admin criado!")
    else:
        user.role = "admin"
        user.set_password("admin123")
        db.session.commit()
        print("✅ Admin atualizado!")

    print("Login:", email)
    print("Senha:", "admin123")
"""WSGI entrypoint.

Importante: este projeto tem um pacote chamado `app/`.
Por isso o entrypoint NÃO pode se chamar `app.py` (conflita com o pacote).

Rodar local:
    flask --app wsgi run --host 0.0.0.0 --port 5000

Produção (Procfile):
    gunicorn wsgi:app
"""

from app import create_app

app = create_app()
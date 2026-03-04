import sqlite3
from werkzeug.security import generate_password_hash


def criar_banco_de_dados():
    """
    Cria e configura o banco de dados 'refeitorio.db' com as tabelas
    'colaboradores' e 'registros' com campos de segurança e níveis de acesso.
    """
    conn = None
    try:
        conn = sqlite3.connect("refeitorio.db")
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS colaboradores (
                matricula TEXT PRIMARY KEY,
                nome TEXT NOT NULL,
                funcao TEXT,
                area TEXT,
                senha_hash TEXT,
                nivel_acesso TEXT NOT NULL DEFAULT 'colaborador'
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS registros (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                matricula TEXT NOT NULL,
                data_hora TEXT NOT NULL,
                FOREIGN KEY (matricula) REFERENCES colaboradores(matricula)
            )
        """)

        senha_admin_hash = generate_password_hash("123456")
        cursor.execute("""
            INSERT OR IGNORE INTO colaboradores (matricula, nome, nivel_acesso, senha_hash)
            VALUES (?, ?, ?, ?)
        """, ("admin", "Administrador", "admin", senha_admin_hash))

        conn.commit()
        print("Banco de dados 'refeitorio.db' e tabelas configuradas com sucesso!")

    except sqlite3.Error as e:
        print(f"Erro ao criar o banco de dados: {e}")
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    criar_banco_de_dados()
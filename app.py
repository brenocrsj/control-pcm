from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, Response
import sqlite3
from datetime import datetime
from flask_bcrypt import Bcrypt
import pandas as pd
from fpdf import FPDF
from io import BytesIO

app = Flask(__name__)
app.secret_key = 'sua_chave_secreta_aqui'
bcrypt = Bcrypt(app)

def get_db_connection():
    """Conecta ao banco de dados SQLite e retorna a conexão."""
    conn = sqlite3.connect('refeitorio.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def home():
    """Página inicial focada no registro de acesso de colaboradores."""
    return render_template('acesso.html')

@app.route('/acesso_refeitorio', methods=['POST'])
def acesso_refeitorio():
    """Processa o registro de acesso de um colaborador (sem login)."""
    matricula = request.form['matricula']
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT nome FROM colaboradores WHERE matricula = ?", (matricula,))
        colaborador = cursor.fetchone()
        
        if colaborador:
            data_hora_atual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("INSERT INTO registros (matricula, data_hora) VALUES (?, ?)",
                           (matricula, data_hora_atual))
            conn.commit()
            return jsonify({'status': 'success', 'nome': colaborador['nome']})
        else:
            return jsonify({'status': 'error', 'message': 'Matrícula não encontrada.'})
            
    except sqlite3.Error as e:
        return jsonify({'status': 'error', 'message': f"Ocorreu um erro: {e}"})
    finally:
        conn.close()

@app.route('/login_admin', methods=['POST'])
def login_admin():
    """Verifica a senha e inicia a sessão do administrador."""
    senha = request.form['senha']
    
    if senha == '123456':
        session['admin_logged_in'] = True
        return redirect(url_for('admin_cadastro'))
    else:
        flash('Senha incorreta. Tente novamente.', 'danger')
        return redirect(url_for('home'))

@app.route('/logout')
def logout():
    """Finaliza a sessão do administrador."""
    session.pop('admin_logged_in', None)
    return redirect(url_for('home'))

def verificar_login_admin():
    """Função de ajuda para proteger rotas do administrador."""
    if 'admin_logged_in' not in session:
        flash('Acesso negado. Por favor, faça login.', 'warning')
        return redirect(url_for('home'))
    return None

@app.route('/admin')
def admin_cadastro():
    protecao = verificar_login_admin()
    if protecao:
        return protecao
    return render_template('admin_cadastro.html')

@app.route('/cadastrar', methods=['POST'])
def cadastrar_colaborador():
    protecao = verificar_login_admin()
    if protecao:
        return protecao
        
    matricula = request.form['matricula']
    nome = request.form['nome']
    funcao = request.form['funcao']
    area = request.form['area']

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO colaboradores (matricula, nome, funcao, area) VALUES (?, ?, ?, ?)",
                       (matricula, nome, funcao, area))
        conn.commit()
    except sqlite3.IntegrityError:
        flash(f'Erro: A matrícula "{matricula}" já está cadastrada.', 'danger')
    finally:
        conn.close()
    
    return redirect(url_for('admin_cadastro'))

@app.route('/relatorio')
def relatorio_completo():
    protecao = verificar_login_admin()
    if protecao:
        return protecao
        
    conn = get_db_connection()
    
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    
    query = '''
        SELECT 
            registros.data_hora, 
            registros.matricula, 
            colaboradores.nome, 
            colaboradores.funcao, 
            colaboradores.area 
        FROM registros 
        JOIN colaboradores ON registros.matricula = colaboradores.matricula 
    '''
    
    params = []
    
    # Adiciona a cláusula WHERE apenas se pelo menos uma data for fornecida
    if data_inicio or data_fim:
        query += " WHERE "
        if data_inicio and not data_fim:
            query += " registros.data_hora >= ?"
            params.append(data_inicio)
        elif not data_inicio and data_fim:
            query += " registros.data_hora <= ?"
            params.append(data_fim)
        elif data_inicio and data_fim:
            query += " registros.data_hora BETWEEN ? AND ?"
            params.append(data_inicio)
            params.append(data_fim)
    
    query += " ORDER BY registros.data_hora DESC"
    
    registros = conn.execute(query, params).fetchall()
    conn.close()
    
    return render_template('relatorio.html', registros=registros)

@app.route('/exportar/excel')
def exportar_excel():
    """Exporta os dados do relatório para um arquivo Excel."""
    protecao = verificar_login_admin()
    if protecao:
        return protecao
        
    conn = get_db_connection()
    registros = conn.execute('''
        SELECT 
            registros.data_hora, 
            registros.matricula, 
            colaboradores.nome, 
            colaboradores.funcao, 
            colaboradores.area 
        FROM registros 
        JOIN colaboradores ON registros.matricula = colaboradores.matricula 
        ORDER BY registros.data_hora DESC
    ''').fetchall()
    conn.close()

    df = pd.DataFrame(registros, columns=['Data e Hora', 'Matrícula', 'Nome', 'Função', 'Área'])
    
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    df.to_excel(writer, index=False, sheet_name='Relatório')
    writer.close()
    output.seek(0)

    return Response(output.getvalue(), 
                    mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    headers={'Content-Disposition': 'attachment;filename=relatorio_refeitorio.xlsx'})

@app.route('/exportar/pdf')
def exportar_pdf():
    """Exporta os dados do relatório para um arquivo PDF."""
    protecao = verificar_login_admin()
    if protecao:
        return protecao
        
    conn = get_db_connection()
    registros = conn.execute('''
        SELECT 
            registros.data_hora, 
            registros.matricula, 
            colaboradores.nome, 
            colaboradores.funcao, 
            colaboradores.area 
        FROM registros 
        JOIN colaboradores ON registros.matricula = colaboradores.matricula 
        ORDER BY registros.data_hora DESC
    ''').fetchall()
    conn.close()

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size = 12)

    pdf.cell(200, 10, txt="Relatório de Acessos ao Refeitório", ln=True, align='C')
    pdf.ln(10)

    pdf.set_font("Arial", size = 10, style='B')
    headers = ['Data e Hora', 'Matrícula', 'Nome', 'Função', 'Área']
    col_widths = [40, 25, 40, 30, 30]
    for i, header in enumerate(headers):
        pdf.cell(col_widths[i], 10, header, border=1)
    pdf.ln()

    pdf.set_font("Arial", size = 10)
    for row in registros:
        pdf.cell(col_widths[0], 10, str(row['data_hora']), border=1)
        pdf.cell(col_widths[1], 10, str(row['matricula']), border=1)
        pdf.cell(col_widths[2], 10, str(row['nome']), border=1)
        pdf.cell(col_widths[3], 10, str(row['funcao']), border=1)
        pdf.cell(col_widths[4], 10, str(row['area']), border=1)
        pdf.ln()

    return Response(pdf.output(dest='S').encode('latin-1'), mimetype='application/pdf',
                    headers={'Content-Disposition': 'attachment;filename=relatorio_refeitorio.pdf'})
                    
if __name__ == '__main__':
    app.run(debug=True)
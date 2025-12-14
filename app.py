from flask import Flask, render_template, request, redirect, url_for, session, flash
import psycopg2
import os
from datetime import date # Importante para calcular idade

app = Flask(__name__)
app.secret_key = "segredo_super_secreto"

# --- Conexão Banco de Dados ---
def get_db_connection():
    try:
        if os.environ.get("DB_HOST"):
            return psycopg2.connect(
                host=os.environ["DB_HOST"],
                database=os.environ["DB_NAME"],
                user=os.environ["DB_USER"],
                password=os.environ["DB_PASS"],
                port=os.environ["DB_PORT"]
            )
        else:
            return None 
    except Exception as e:
        print(f"Erro DB: {e}")
        return None

# --- Ferramenta de Migração (Resetar Tabela) ---
# Use isso apenas uma vez para atualizar o banco antigo para o novo formato
@app.route('/reset-db')
def reset_db():
    if not session.get('logged_in'): return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    # Apaga a tabela antiga e cria a nova com campo NASCIMENTO (DATE)
    cursor.execute("DROP TABLE IF EXISTS pacientes CASCADE;")
    cursor.execute('''
        CREATE TABLE pacientes (
            id SERIAL PRIMARY KEY, 
            nome TEXT NOT NULL, 
            nascimento DATE, 
            telefone TEXT
        );
    ''')
    conn.commit()
    conn.close()
    return "Banco de dados atualizado para suportar Data de Nascimento! Volte para o Dashboard."

# --- Rotas ---

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        senha = request.form['senha']
        senha_correta = os.environ.get("SYS_PASSWORD", "admin123")
        
        if senha == senha_correta:
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        else:
            flash('Senha incorreta!')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'): return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM pacientes;")
    total_pacientes = cursor.fetchone()[0]
    
    # Se tiver a tabela agendamentos, conta. Se der erro (ainda não criada), assume 0.
    try:
        cursor.execute("SELECT COUNT(*) FROM agendamentos;")
        total_agendamentos = cursor.fetchone()[0]
    except:
        conn.rollback()
        total_agendamentos = 0
    
    conn.close()
    
    return render_template('dashboard.html', 
                           total_pacientes=total_pacientes, 
                           total_agendamentos=total_agendamentos)

@app.route('/pacientes', methods=['GET', 'POST'])
def pacientes():
    if not session.get('logged_in'): return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        nome = request.form['nome']
        nascimento = request.form['nascimento'] # Recebe 'YYYY-MM-DD' do HTML
        telefone = request.form['telefone']
        
        cursor.execute("INSERT INTO pacientes (nome, nascimento, telefone) VALUES (%s, %s, %s)", 
                       (nome, nascimento, telefone))
        conn.commit()
    
    # Busca os dados brutos
    cursor.execute("SELECT id, nome, nascimento, telefone FROM pacientes ORDER BY id DESC")
    dados_brutos = cursor.fetchall()
    
    # Processa a idade no Python antes de enviar para o site
    lista_pacientes = []
    hoje = date.today()
    
    for p in dados_brutos:
        id_p, nome, nasc, tel = p
        
        # Cálculo da Idade
        idade_calculada = "---"
        if nasc:
            # Fórmula: Ano Atual - Ano Nasc - (1 se ainda não fez aniversário este ano)
            idade_int = hoje.year - nasc.year - ((hoje.month, hoje.day) < (nasc.month, nasc.day))
            idade_calculada = f"{idade_int} anos"
            
        lista_pacientes.append((id_p, nome, idade_calculada, tel))
        
    conn.close()
    
    return render_template('pacientes.html', pacientes=lista_pacientes)

if __name__ == '__main__':
    app.run(debug=True)
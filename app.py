from flask import Flask, render_template, request, redirect, url_for, session, flash
import psycopg2
import os

app = Flask(__name__)
app.secret_key = "segredo_super_secreto" # Necessário para sessão e login

# --- Conexão Banco de Dados ---
def get_db_connection():
    try:
        # Tenta pegar do Render (Variáveis de Ambiente)
        if os.environ.get("DB_HOST"):
            return psycopg2.connect(
                host=os.environ["DB_HOST"],
                database=os.environ["DB_NAME"],
                user=os.environ["DB_USER"],
                password=os.environ["DB_PASS"],
                port=os.environ["DB_PORT"]
            )
        # Se não, tenta local (Hardcoded para teste rápido se precisar, ou use .env)
        else:
            return None 
    except Exception as e:
        print(f"Erro DB: {e}")
        return None

# --- Rotas (As Páginas do Site) ---

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        senha = request.form['senha']
        # Pega a senha do Render
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
    
    # Métricas
    cursor.execute("SELECT COUNT(*) FROM pacientes;")
    total_pacientes = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM agendamentos;")
    total_agendamentos = cursor.fetchone()[0]
    
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
        idade = request.form['idade']
        telefone = request.form['telefone']
        cursor.execute("INSERT INTO pacientes (nome, idade, telefone) VALUES (%s, %s, %s)", 
                       (nome, idade, telefone))
        conn.commit()
    
    cursor.execute("SELECT * FROM pacientes ORDER BY id DESC")
    lista_pacientes = cursor.fetchall()
    conn.close()
    
    return render_template('pacientes.html', pacientes=lista_pacientes)

if __name__ == '__main__':
    app.run(debug=True)
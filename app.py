from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import psycopg2
import os
from datetime import datetime, timedelta

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
        return None 
    except Exception as e:
        print(f"Erro DB: {e}")
        return None

# --- MIGRAÇÃO DE STATUS (NOVO) ---
@app.route('/update-db-status')
def update_db_status():
    if not session.get('logged_in'): return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Adiciona coluna status se não existir
        cursor.execute("ALTER TABLE agendamentos ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'Agendado';")
        conn.commit()
        msg = "Banco de dados atualizado com campo STATUS!"
    except Exception as e:
        conn.rollback()
        msg = f"Erro na atualização: {e}"
    finally:
        conn.close()
    return msg

# --- Rotas Padrão ---
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['senha'] == os.environ.get("SYS_PASSWORD", "admin123"):
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
    cursor.execute("SELECT COUNT(*) FROM agendamentos;")
    total_agendamentos = cursor.fetchone()[0]
    conn.close()
    return render_template('dashboard.html', total_pacientes=total_pacientes, total_agendamentos=total_agendamentos)

@app.route('/pacientes', methods=['GET', 'POST'])
def pacientes():
    if not session.get('logged_in'): return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        nome = request.form['nome']
        nascimento = request.form['nascimento']
        telefone = request.form['telefone']
        
        # Lógica para aceitar Data Vazia (Cadastro Rápido)
        if not nascimento:
            nascimento = None # Envia NULL para o banco
            
        cursor.execute("INSERT INTO pacientes (nome, nascimento, telefone) VALUES (%s, %s, %s)", 
                       (nome, nascimento, telefone))
        conn.commit()
    
    # Busca os dados
    cursor.execute("SELECT id, nome, nascimento, telefone FROM pacientes ORDER BY id DESC")
    dados_brutos = cursor.fetchall()
    
    # Processa a idade para exibição
    lista_pacientes = []
    hoje = date.today()
    
    for p in dados_brutos:
        id_p, nome_p, nasc_p, tel_p = p
        
        idade_calculada = "---"
        if nasc_p:
            try:
                idade_int = hoje.year - nasc_p.year - ((hoje.month, hoje.day) < (nasc_p.month, nasc_p.day))
                idade_calculada = f"{idade_int} anos"
            except:
                pass
            
        lista_pacientes.append((id_p, nome_p, idade_calculada, tel_p))
        
    conn.close()
    
    return render_template('pacientes.html', pacientes=lista_pacientes)

# --- ROTAS DA AGENDA (API) ---

@app.route('/agenda')
def agenda():
    if not session.get('logged_in'): return redirect(url_for('login'))
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, nome FROM pacientes")
    pacientes = cur.fetchall()
    conn.close()
    return render_template('agenda.html', pacientes=pacientes)

@app.route('/api/eventos')
def api_eventos():
    conn = get_db_connection()
    cur = conn.cursor()
    # Agora buscamos também o STATUS
    query = """
        SELECT a.id, p.nome, a.start_time, a.end_time, a.obs, a.status 
        FROM agendamentos a
        JOIN pacientes p ON a.paciente_id = p.id
    """
    cur.execute(query)
    rows = cur.fetchall()
    conn.close()
    
    eventos = []
    # Dicionário de Cores por Status
    cores = {
        'Agendado': '#007bff',   # Azul
        'Confirmado': '#17a2b8', # Turquesa
        'Realizado': '#198754',  # Verde
        'Faltou': '#dc3545',     # Vermelho
        'Cancelado': '#6c757d'   # Cinza
    }

    for row in rows:
        status = row[5] if row[5] else 'Agendado'
        cor_evento = cores.get(status, '#007bff')
        
        eventos.append({
            'id': row[0],
            'title': f"{row[1]} ({status})", # Mostra status no título
            'start': row[2].isoformat(),
            'end': row[3].isoformat(),
            'description': row[4],
            'extendedProps': {'status': status}, # Para o JS ler
            'color': cor_evento
        })
    return jsonify(eventos)

@app.route('/api/criar_evento', methods=['POST'])
def criar_evento():
    data = request.json
    paciente_id = data['paciente_id']
    data_inicio = datetime.fromisoformat(data['start'])
    obs = data.get('obs', '')
    dias_recorrentes = data.get('dias_recorrentes', [])
    semanas = int(data.get('semanas', 1))
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        if not dias_recorrentes:
            fim = data_inicio + timedelta(hours=1)
            # Cria com status padrão 'Agendado'
            cur.execute("INSERT INTO agendamentos (paciente_id, start_time, end_time, obs, status) VALUES (%s, %s, %s, %s, 'Agendado')",
                        (paciente_id, data_inicio, fim, obs))
        else:
            current_day = data_inicio
            start_of_week = current_day - timedelta(days=current_day.weekday())
            # Ajuste para começar da segunda-feira correta (se hoje for domingo e week start for segunda)
            if current_day.weekday() == 6: # Se for domingo
                 start_of_week = current_day - timedelta(days=6)

            for i in range(semanas):
                week_start = start_of_week + timedelta(weeks=i)
                for dia_semana in dias_recorrentes:
                    dia_semana = int(dia_semana)
                    event_date = week_start + timedelta(days=dia_semana)
                    event_start = event_date.replace(hour=data_inicio.hour, minute=data_inicio.minute)
                    
                    if event_start >= datetime.now().replace(hour=0, minute=0):
                        event_end = event_start + timedelta(hours=1)
                        cur.execute("INSERT INTO agendamentos (paciente_id, start_time, end_time, obs, status) VALUES (%s, %s, %s, %s, 'Agendado')",
                                    (paciente_id, event_start, event_end, obs))
        
        conn.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/mover_evento', methods=['POST'])
def mover_evento():
    data = request.json
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE agendamentos SET start_time = %s, end_time = %s WHERE id = %s",
                (data['start'], data['end'], data['id']))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

# --- NOVA ROTA: ATUALIZAR DETALHES (STATUS/OBS) ---
@app.route('/api/atualizar_evento', methods=['POST'])
def atualizar_evento():
    data = request.json
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE agendamentos SET status = %s, obs = %s WHERE id = %s",
                (data['status'], data['obs'], data['id']))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

@app.route('/api/deletar_evento', methods=['POST'])
def deletar_evento():
    data = request.json
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM agendamentos WHERE id = %s", (data['id'],))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

if __name__ == '__main__':
    app.run(debug=True)
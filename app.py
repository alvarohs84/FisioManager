from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import psycopg2
import os
from datetime import datetime, timedelta, date # <--- O erro estava aqui (faltava importar 'date')

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

# --- MIGRAÇÃO DE STATUS ---
@app.route('/update-db-status')
def update_db_status():
    if not session.get('logged_in'): return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
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
    
    # Tenta contar agendamentos, se tabela existir
    try:
        cursor.execute("SELECT COUNT(*) FROM agendamentos;")
        total_agendamentos = cursor.fetchone()[0]
    except:
        conn.rollback()
        total_agendamentos = 0
        
    conn.close()
    return render_template('dashboard.html', total_pacientes=total_pacientes, total_agendamentos=total_agendamentos)

# --- ROTA DE PACIENTES (COM CADASTRO RÁPIDO) ---
@app.route('/pacientes', methods=['GET', 'POST'])
def pacientes():
    if not session.get('logged_in'): return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        nome = request.form['nome']
        nascimento = request.form.get('nascimento') # .get evita erro se vier vazio
        telefone = request.form.get('telefone')
        
        # Lógica para aceitar Data Vazia (Null)
        if not nascimento:
            nascimento = None
            
        cursor.execute("INSERT INTO pacientes (nome, nascimento, telefone) VALUES (%s, %s, %s)", 
                       (nome, nascimento, telefone))
        conn.commit()
    
    # Busca e exibe
    cursor.execute("SELECT id, nome, nascimento, telefone FROM pacientes ORDER BY id DESC")
    dados_brutos = cursor.fetchall()
    
    lista_pacientes = []
    hoje = date.today() # Agora vai funcionar porque importamos 'date' lá em cima
    
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
    cur.execute("SELECT id, nome FROM pacientes ORDER BY nome ASC")
    pacientes = cur.fetchall()
    conn.close()
    return render_template('agenda.html', pacientes=pacientes)

@app.route('/api/eventos')
def api_eventos():
    conn = get_db_connection()
    cur = conn.cursor()
    query = """
        SELECT a.id, p.nome, a.start_time, a.end_time, a.obs, a.status 
        FROM agendamentos a
        JOIN pacientes p ON a.paciente_id = p.id
    """
    cur.execute(query)
    rows = cur.fetchall()
    conn.close()
    
    eventos = []
    cores = {
        'Agendado': '#007bff', 'Confirmado': '#17a2b8', 
        'Realizado': '#198754', 'Faltou': '#dc3545', 'Cancelado': '#6c757d'
    }

    for row in rows:
        status = row[5] if row[5] else 'Agendado'
        eventos.append({
            'id': row[0],
            'title': f"{row[1]}", # Nome Limpo
            'start': row[2].isoformat(),
            'end': row[3].isoformat(),
            'description': row[4],
            'extendedProps': {'status': status},
            'color': cores.get(status, '#007bff')
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
            cur.execute("INSERT INTO agendamentos (paciente_id, start_time, end_time, obs, status) VALUES (%s, %s, %s, %s, 'Agendado')",
                        (paciente_id, data_inicio, fim, obs))
        else:
            current_day = data_inicio
            start_of_week = current_day - timedelta(days=current_day.weekday())
            if current_day.weekday() == 6: start_of_week = current_day - timedelta(days=6)

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

@app.route('/api/deletar_paciente', methods=['POST'])
def deletar_paciente():
    if not session.get('logged_in'): return jsonify({'status': 'error'}), 403
    
    data = request.json
    paciente_id = data['id']
    
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # 1. Primeiro deleta os agendamentos desse paciente (Limpeza)
        cur.execute("DELETE FROM agendamentos WHERE paciente_id = %s", (paciente_id,))
        
        # 2. Depois deleta o paciente
        cur.execute("DELETE FROM pacientes WHERE id = %s", (paciente_id,))
        
        conn.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        conn.close()


if __name__ == '__main__':
    app.run(debug=True)
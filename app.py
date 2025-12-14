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

# --- ATUALIZAÇÃO DO BANCO (MIGRAÇÃO) ---
@app.route('/update-db-agenda')
def update_db_agenda():
    if not session.get('logged_in'): return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Recriar tabela agendamentos para suportar inicio/fim e timestamps reais
    cursor.execute("DROP TABLE IF EXISTS agendamentos;")
    cursor.execute('''
        CREATE TABLE agendamentos (
            id SERIAL PRIMARY KEY, 
            paciente_id INTEGER REFERENCES pacientes(id), 
            start_time TIMESTAMP NOT NULL,
            end_time TIMESTAMP NOT NULL,
            obs TEXT
        );
    ''')
    conn.commit()
    conn.close()
    return "Banco de dados de Agenda atualizado! Volte para o sistema."

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
        cursor.execute("INSERT INTO pacientes (nome, nascimento, telefone) VALUES (%s, %s, %s)", 
                       (request.form['nome'], request.form['nascimento'], request.form['telefone']))
        conn.commit()
    cursor.execute("SELECT id, nome, nascimento, telefone FROM pacientes ORDER BY id DESC")
    dados = cursor.fetchall()
    conn.close()
    return render_template('pacientes.html', pacientes=dados)

# --- ROTAS DA AGENDA INTELIGENTE (API) ---

@app.route('/agenda')
def agenda():
    if not session.get('logged_in'): return redirect(url_for('login'))
    # Carregar pacientes para o formulário modal
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, nome FROM pacientes")
    pacientes = cur.fetchall()
    conn.close()
    return render_template('agenda.html', pacientes=pacientes)

# 1. API para fornecer dados ao Calendário (JSON)
@app.route('/api/eventos')
def api_eventos():
    conn = get_db_connection()
    cur = conn.cursor()
    # Busca eventos e o nome do paciente
    query = """
        SELECT a.id, p.nome, a.start_time, a.end_time, a.obs 
        FROM agendamentos a
        JOIN pacientes p ON a.paciente_id = p.id
    """
    cur.execute(query)
    rows = cur.fetchall()
    conn.close()
    
    eventos = []
    for row in rows:
        eventos.append({
            'id': row[0],
            'title': row[1], # O nome do paciente será o título
            'start': row[2].isoformat(),
            'end': row[3].isoformat(),
            'description': row[4],
            'color': '#007bff' # Azul padrão
        })
    return jsonify(eventos)

# 2. API para Salvar/Criar (Com Recorrência)
@app.route('/api/criar_evento', methods=['POST'])
def criar_evento():
    data = request.json
    paciente_id = data['paciente_id']
    data_inicio = datetime.fromisoformat(data['start']) # Ex: 2025-10-20T10:00
    obs = data.get('obs', '')
    dias_recorrentes = data.get('dias_recorrentes', []) # Lista de dias [0, 2, 4] (Seg, Qua, Sex)
    semanas = int(data.get('semanas', 1)) # Quantas semanas repetir
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        if not dias_recorrentes:
            # Agendamento Único (Padrão 1 hora de duração)
            fim = data_inicio + timedelta(hours=1)
            cur.execute("INSERT INTO agendamentos (paciente_id, start_time, end_time, obs) VALUES (%s, %s, %s, %s)",
                        (paciente_id, data_inicio, fim, obs))
        else:
            # Lógica de Recorrência
            # Loop pelas próximas X semanas
            current_day = data_inicio
            # Ajusta para o inicio da semana atual para calcular os dias
            start_of_week = current_day - timedelta(days=current_day.weekday())
            
            for i in range(semanas):
                week_start = start_of_week + timedelta(weeks=i)
                for dia_semana in dias_recorrentes: # 0=Seg, 1=Ter...
                    dia_semana = int(dia_semana)
                    # Cria a data do evento
                    event_date = week_start + timedelta(days=dia_semana)
                    
                    # Mantém a hora original
                    event_start = event_date.replace(hour=data_inicio.hour, minute=data_inicio.minute)
                    
                    # Só agenda se for futuro ou hoje
                    if event_start >= datetime.now().replace(hour=0, minute=0):
                        event_end = event_start + timedelta(hours=1)
                        cur.execute("INSERT INTO agendamentos (paciente_id, start_time, end_time, obs) VALUES (%s, %s, %s, %s)",
                                    (paciente_id, event_start, event_end, obs))
        
        conn.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        conn.close()

# 3. API para Arrastar e Soltar (Atualizar Data/Hora)
@app.route('/api/mover_evento', methods=['POST'])
def mover_evento():
    data = request.json
    evento_id = data['id']
    novo_inicio = data['start']
    novo_fim = data['end']
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE agendamentos SET start_time = %s, end_time = %s WHERE id = %s",
                (novo_inicio, novo_fim, evento_id))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

# 4. API para Deletar
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
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import psycopg2
import os
from datetime import datetime, timedelta, date

app = Flask(__name__)
app.secret_key = "segredo_super_secreto"

# --- CONEXÃO COM BANCO DE DADOS ---
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

# ==========================================
# ÁREA DE MIGRAÇÕES (CRIAÇÃO DE TABELAS)
# ==========================================

@app.route('/update-db-status')
def update_db_status():
    if not session.get('logged_in'): return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE agendamentos ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'Agendado';")
        conn.commit()
        msg = "Banco atualizado: Campo STATUS criado."
    except Exception as e:
        conn.rollback()
        msg = f"Erro: {e}"
    finally:
        conn.close()
    return msg

@app.route('/update-db-prontuario')
def update_db_prontuario():
    if not session.get('logged_in'): return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evolucoes (
                id SERIAL PRIMARY KEY, 
                paciente_id INTEGER REFERENCES pacientes(id) ON DELETE CASCADE,
                data TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                texto TEXT
            );
        ''')
        conn.commit()
        msg = "Banco atualizado: Tabela EVOLUÇÕES criada."
    except Exception as e:
        conn.rollback()
        msg = f"Erro: {e}"
    finally:
        conn.close()
    return msg

@app.route('/update-db-avaliacao-completa')
def update_db_avaliacao_completa():
    if not session.get('logged_in'): return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS avaliacoes_completa (
                id SERIAL PRIMARY KEY, 
                paciente_id INTEGER REFERENCES pacientes(id) ON DELETE CASCADE,
                data_avaliacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ocupacao TEXT, lateralidade TEXT, diagnostico_medico TEXT, queixa_principal TEXT,
                hma TEXT, hpp TEXT, habitos TEXT, sinais_vitais TEXT, avaliacao_dor TEXT,
                inspecao TEXT, palpacao TEXT, adm TEXT, forca_muscular TEXT, neuro TEXT,
                testes_especiais TEXT, diagnostico_cif TEXT, objetivos TEXT, conduta TEXT
            );
        ''')
        conn.commit()
        msg = "Banco atualizado: Tabela AVALIAÇÃO COMPLETA criada."
    except Exception as e:
        conn.rollback()
        msg = f"Erro: {e}"
    finally:
        conn.close()
    return msg

@app.route('/update-db-fotos')
def update_db_fotos():
    if not session.get('logged_in'): return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS avaliacao_postural (
                id SERIAL PRIMARY KEY, 
                paciente_id INTEGER REFERENCES pacientes(id) ON DELETE CASCADE,
                data_foto TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                foto_frontal TEXT, foto_posterior TEXT, foto_lat_dir TEXT, foto_lat_esq TEXT,
                analise_ia TEXT
            );
        ''')
        conn.commit()
        msg = "Sucesso! Tabela de Fotos Posturais criada."
    except Exception as e:
        conn.rollback()
        msg = f"Erro: {e}"
    finally:
        conn.close()
    return msg

# ==========================================
# ROTAS DE NAVEGAÇÃO (PÁGINAS)
# ==========================================

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        senha_correta = os.environ.get("SYS_PASSWORD", "admin123")
        if request.form['senha'] == senha_correta:
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
    try:
        cursor.execute("SELECT COUNT(*) FROM agendamentos;")
        total_agendamentos = cursor.fetchone()[0]
    except:
        conn.rollback()
        total_agendamentos = 0
    conn.close()
    return render_template('dashboard.html', total_pacientes=total_pacientes, total_agendamentos=total_agendamentos)

@app.route('/pacientes', methods=['GET', 'POST'])
def pacientes():
    if not session.get('logged_in'): return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        nome = request.form['nome']
        nascimento = request.form.get('nascimento')
        telefone = request.form.get('telefone')
        if not nascimento: nascimento = None
            
        cursor.execute("INSERT INTO pacientes (nome, nascimento, telefone) VALUES (%s, %s, %s)", 
                       (nome, nascimento, telefone))
        conn.commit()
        conn.close()
        # REDIRECIONAMENTO PARA EVITAR DUPLICAÇÃO
        return redirect(url_for('pacientes'))
    
    cursor.execute("SELECT id, nome, nascimento, telefone FROM pacientes ORDER BY id DESC")
    dados_brutos = cursor.fetchall()
    
    lista_pacientes = []
    hoje = date.today()
    for p in dados_brutos:
        id_p, nome_p, nasc_p, tel_p = p
        idade_calculada = "---"
        if nasc_p:
            try:
                idade_int = hoje.year - nasc_p.year - ((hoje.month, hoje.day) < (nasc_p.month, nasc_p.day))
                idade_calculada = f"{idade_int} anos"
            except: pass
        lista_pacientes.append((id_p, nome_p, idade_calculada, tel_p))
        
    conn.close()
    return render_template('pacientes.html', pacientes=lista_pacientes)

@app.route('/agenda')
def agenda():
    if not session.get('logged_in'): return redirect(url_for('login'))
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, nome FROM pacientes ORDER BY nome ASC")
    pacientes = cur.fetchall()
    conn.close()
    return render_template('agenda.html', pacientes=pacientes)

@app.route('/prontuarios')
def prontuarios():
    if not session.get('logged_in'): return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome, nascimento FROM pacientes ORDER BY nome ASC")
    pacientes = cursor.fetchall()
    conn.close()
    return render_template('prontuarios.html', pacientes=pacientes)

@app.route('/fazer_backup_dados')
def fazer_backup_dados():
    if not session.get('logged_in'): return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    backup = {}
    def converter_datas(row):
        new_row = []
        for item in row:
            if isinstance(item, (datetime, date)): new_row.append(str(item))
            else: new_row.append(item)
        return new_row

    try:
        cursor.execute("SELECT * FROM pacientes")
        backup['pacientes'] = [converter_datas(row) for row in cursor.fetchall()]
        try:
            cursor.execute("SELECT * FROM agendamentos")
            backup['agendamentos'] = [converter_datas(row) for row in cursor.fetchall()]
        except: backup['agendamentos'] = "vazio"
        try:
            cursor.execute("SELECT * FROM evolucoes")
            backup['evolucoes'] = [converter_datas(row) for row in cursor.fetchall()]
        except: backup['evolucoes'] = "vazio"
        return jsonify(backup)
    except Exception as e:
        return jsonify({'erro': str(e)})
    finally:
        conn.close()

# ==========================================
# APIs (AJAX / JSON)
# ==========================================

# --- PACIENTES (EXCLUSÃO TOTAL) ---
@app.route('/api/deletar_paciente', methods=['POST'])
def deletar_paciente():
    if not session.get('logged_in'): return jsonify({'status': 'error'}), 403
    data = request.json
    paciente_id = data['id']
    
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Limpa tudo que é vinculado ao paciente para não dar erro
        cur.execute("DELETE FROM agendamentos WHERE paciente_id = %s", (paciente_id,))
        try: cur.execute("DELETE FROM evolucoes WHERE paciente_id = %s", (paciente_id,))
        except: pass
        try: cur.execute("DELETE FROM avaliacoes_completa WHERE paciente_id = %s", (paciente_id,))
        except: pass
        try: cur.execute("DELETE FROM avaliacao_postural WHERE paciente_id = %s", (paciente_id,))
        except: pass
        try: cur.execute("DELETE FROM avaliacoes WHERE paciente_id = %s", (paciente_id,)) # Tabela antiga
        except: pass
        
        # Por fim, apaga o paciente
        cur.execute("DELETE FROM pacientes WHERE id = %s", (paciente_id,))
        conn.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        conn.rollback()
        print(f"Erro ao excluir: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        conn.close()

# --- AGENDA ---
@app.route('/api/eventos')
def api_eventos():
    conn = get_db_connection()
    cur = conn.cursor()
    query = "SELECT a.id, p.nome, a.start_time, a.end_time, a.obs, a.status FROM agendamentos a JOIN pacientes p ON a.paciente_id = p.id"
    cur.execute(query)
    rows = cur.fetchall()
    conn.close()
    eventos = []
    cores = {'Agendado': '#007bff', 'Confirmado': '#17a2b8', 'Realizado': '#198754', 'Faltou': '#dc3545', 'Cancelado': '#6c757d'}
    for row in rows:
        status = row[5] if row[5] else 'Agendado'
        eventos.append({
            'id': row[0], 'title': f"{row[1]}", 'start': row[2].isoformat(), 'end': row[3].isoformat(),
            'description': row[4], 'extendedProps': {'status': status}, 'color': cores.get(status, '#007bff')
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
            cur.execute("INSERT INTO agendamentos (paciente_id, start_time, end_time, obs, status) VALUES (%s, %s, %s, %s, 'Agendado')", (paciente_id, data_inicio, fim, obs))
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
                        cur.execute("INSERT INTO agendamentos (paciente_id, start_time, end_time, obs, status) VALUES (%s, %s, %s, %s, 'Agendado')", (paciente_id, event_start, event_end, obs))
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
    cur.execute("UPDATE agendamentos SET start_time = %s, end_time = %s WHERE id = %s", (data['start'], data['end'], data['id']))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

@app.route('/api/atualizar_evento', methods=['POST'])
def atualizar_evento():
    data = request.json
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE agendamentos SET status = %s, obs = %s WHERE id = %s", (data['status'], data['obs'], data['id']))
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

# --- PRONTUÁRIO ---
@app.route('/api/evolucoes/<int:paciente_id>', methods=['GET'])
def get_evolucoes(paciente_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT data, texto FROM evolucoes WHERE paciente_id = %s ORDER BY data DESC", (paciente_id,))
    dados = cur.fetchall()
    conn.close()
    lista = []
    for row in dados:
        data_formatada = row[0].strftime("%d/%m/%Y às %H:%M")
        lista.append({'data': data_formatada, 'texto': row[1]})
    return jsonify(lista)

@app.route('/api/nova_evolucao', methods=['POST'])
def nova_evolucao():
    data = request.json
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO evolucoes (paciente_id, texto, data) VALUES (%s, %s, NOW())", (data['paciente_id'], data['texto']))
        conn.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'msg': str(e)}), 500
    finally:
        conn.close()

# --- AVALIAÇÃO COMPLETA ---
@app.route('/api/salvar_avaliacao', methods=['POST'])
def salvar_avaliacao():
    data = request.json
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""INSERT INTO avaliacoes_completa 
            (paciente_id, ocupacao, lateralidade, diagnostico_medico, queixa_principal, hma, hpp, habitos,
             sinais_vitais, avaliacao_dor, inspecao, palpacao, adm, forca_muscular, neuro, testes_especiais,
             diagnostico_cif, objetivos, conduta) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""", 
            (data['paciente_id'], data['ocupacao'], data['lateralidade'], data['diagnostico_medico'], 
            data['queixa_principal'], data['hma'], data['hpp'], data['habitos'],
            data['sinais_vitais'], data['avaliacao_dor'], data['inspecao'], data['palpacao'], 
            data['adm'], data['forca_muscular'], data['neuro'], data['testes_especiais'],
            data['diagnostico_cif'], data['objetivos'], data['conduta']))
        conn.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'msg': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/get_avaliacao/<int:paciente_id>', methods=['GET'])
def get_avaliacao(paciente_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""SELECT ocupacao, lateralidade, diagnostico_medico, queixa_principal, hma, hpp, habitos,
               sinais_vitais, avaliacao_dor, inspecao, palpacao, adm, forca_muscular, neuro, testes_especiais,
               diagnostico_cif, objetivos, conduta, data_avaliacao
        FROM avaliacoes_completa WHERE paciente_id = %s ORDER BY id DESC LIMIT 1""", (paciente_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        return jsonify({'encontrado': True, 'ocupacao': row[0], 'lateralidade': row[1], 'diagnostico_medico': row[2], 
            'queixa_principal': row[3], 'hma': row[4], 'hpp': row[5], 'habitos': row[6], 'sinais_vitais': row[7], 
            'avaliacao_dor': row[8], 'inspecao': row[9], 'palpacao': row[10], 'adm': row[11], 'forca_muscular': row[12], 
            'neuro': row[13], 'testes_especiais': row[14], 'diagnostico_cif': row[15], 'objetivos': row[16], 
            'conduta': row[17], 'data': row[18].strftime("%d/%m/%Y")})
    else:
        return jsonify({'encontrado': False})

# --- FOTOS POSTURAIS ---
@app.route('/api/salvar_fotos', methods=['POST'])
def salvar_fotos():
    data = request.json
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""INSERT INTO avaliacao_postural 
            (paciente_id, foto_frontal, foto_posterior, foto_lat_dir, foto_lat_esq, analise_ia) 
            VALUES (%s, %s, %s, %s, %s, %s)""", 
            (data['paciente_id'], data.get('frontal'), data.get('posterior'), 
            data.get('lat_dir'), data.get('lat_esq'), data.get('analise_ia', 'Aguardando...')))
        conn.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'msg': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/get_fotos/<int:paciente_id>', methods=['GET'])
def get_fotos(paciente_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT foto_frontal, foto_posterior, foto_lat_dir, foto_lat_esq, analise_ia, data_foto FROM avaliacao_postural WHERE paciente_id = %s ORDER BY id DESC LIMIT 1", (paciente_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        return jsonify({'encontrado': True, 'frontal': row[0], 'posterior': row[1], 'lat_dir': row[2], 'lat_esq': row[3], 'analise': row[4], 'data': row[5].strftime("%d/%m/%Y")})
    else:
        return jsonify({'encontrado': False})

if __name__ == '__main__':
    app.run(debug=True)
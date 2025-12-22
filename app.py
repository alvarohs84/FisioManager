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
# ROTA DE REPARO GERAL (Salva-Vidas)
# ==========================================
@app.route('/reparar_banco')
def reparar_banco():
    if not session.get('logged_in'): return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    log = []
    try:
        # 1. Tabela Financeiro
        cursor.execute('''CREATE TABLE IF NOT EXISTS financeiro (
            id SERIAL PRIMARY KEY,
            descricao TEXT NOT NULL,
            valor NUMERIC(10, 2) NOT NULL,
            tipo VARCHAR(10) NOT NULL,
            categoria TEXT,
            data DATE DEFAULT CURRENT_DATE
        );''')
        log.append("Tabela Financeiro: OK")

        # 2. Tabela Evoluções
        cursor.execute('''CREATE TABLE IF NOT EXISTS evolucoes (
            id SERIAL PRIMARY KEY, paciente_id INTEGER REFERENCES pacientes(id) ON DELETE CASCADE,
            data TIMESTAMP DEFAULT CURRENT_TIMESTAMP, texto TEXT);''')
        log.append("Tabela Evoluções: OK")

        # 3. Tabela Avaliação Completa (Criação Base)
        cursor.execute('''CREATE TABLE IF NOT EXISTS avaliacoes_completa (
            id SERIAL PRIMARY KEY, paciente_id INTEGER REFERENCES pacientes(id) ON DELETE CASCADE,
            data_avaliacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ocupacao TEXT, lateralidade TEXT, diagnostico_medico TEXT, queixa_principal TEXT,
            hma TEXT, hpp TEXT, habitos TEXT, sinais_vitais TEXT, avaliacao_dor TEXT,
            inspecao TEXT, palpacao TEXT, adm TEXT, forca_muscular TEXT, neuro TEXT,
            testes_especiais TEXT, diagnostico_cif TEXT, objetivos TEXT, conduta TEXT);''')
        
        # 4. Atualização de Colunas Extras (Pilates, Quiro, Cardio)
        cursor.execute("ALTER TABLE avaliacoes_completa ADD COLUMN IF NOT EXISTS dados_pilates TEXT;")
        cursor.execute("ALTER TABLE avaliacoes_completa ADD COLUMN IF NOT EXISTS dados_quiro TEXT;")
        cursor.execute("ALTER TABLE avaliacoes_completa ADD COLUMN IF NOT EXISTS dados_cardio TEXT;") # <--- IMPORTANTE PARA O TC6
        log.append("Colunas Extras Avaliação (Pilates/Quiro/Cardio): OK")

        # 5. Tabela Fotos
        cursor.execute('''CREATE TABLE IF NOT EXISTS avaliacao_postural (
            id SERIAL PRIMARY KEY, paciente_id INTEGER REFERENCES pacientes(id) ON DELETE CASCADE,
            data_foto TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            foto_frontal TEXT, foto_posterior TEXT, foto_lat_dir TEXT, foto_lat_esq TEXT,
            analise_ia TEXT);''')
        log.append("Tabela Fotos: OK")

        # 6. Status na Agenda
        try:
            cursor.execute("ALTER TABLE agendamentos ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'Agendado';")
        except: pass

        conn.commit()
        return jsonify({'status': 'Sucesso', 'log': log})
    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'Erro Crítico', 'erro': str(e)})
    finally:
        conn.close()

# ==========================================
# ROTAS DE NAVEGAÇÃO
# ==========================================

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
    conn.close()
    return render_template('dashboard.html', total_pacientes=total_pacientes)

@app.route('/pacientes', methods=['GET', 'POST'])
def pacientes():
    if not session.get('logged_in'): return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        nome = request.form['nome']
        dt = request.form.get('data_nascimento') or None
        tel = request.form.get('telefone')
        cursor.execute("INSERT INTO pacientes (nome, data_nascimento, telefone) VALUES (%s, %s, %s)", (nome, dt, tel))
        conn.commit()
        conn.close()
        return redirect(url_for('pacientes')) 
    
    cursor.execute("SELECT id, nome, data_nascimento, telefone FROM pacientes ORDER BY id DESC")
    dados = cursor.fetchall()
    
    lista = []
    hoje = date.today()
    for p in dados:
        idade = "---"
        if p[2]:
            try: idade = f"{hoje.year - p[2].year - ((hoje.month, hoje.day) < (p[2].month, p[2].day))} anos"
            except: pass
        lista.append((p[0], p[1], idade, p[3]))
        
    conn.close()
    return render_template('pacientes.html', pacientes=lista)

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
    cursor.execute("SELECT id, nome, data_nascimento FROM pacientes ORDER BY nome ASC")
    pacientes = cursor.fetchall()
    conn.close()
    return render_template('prontuarios.html', pacientes=pacientes)

# ==========================================
# API INTELIGENTE DO DASHBOARD (GRÁFICOS)
# ==========================================
@app.route('/api/dados_dashboard')
def dados_dashboard():
    if not session.get('logged_in'): return jsonify({}), 403
    conn = get_db_connection()
    cur = conn.cursor()
    
    mes = request.args.get('mes', datetime.now().month, type=int)
    ano = request.args.get('ano', datetime.now().year, type=int)

    # 1. Sessões por Paciente
    cur.execute("""
        SELECT p.nome, COUNT(a.id) FROM agendamentos a 
        JOIN pacientes p ON a.paciente_id = p.id 
        WHERE a.status = 'Realizado' AND EXTRACT(MONTH FROM a.start_time) = %s AND EXTRACT(YEAR FROM a.start_time) = %s 
        GROUP BY p.nome ORDER BY COUNT(a.id) DESC LIMIT 10
    """, (mes, ano))
    raw_sessoes = cur.fetchall()
    
    # 2. Status
    cur.execute("""
        SELECT COALESCE(status, 'Agendado'), COUNT(*) FROM agendamentos 
        WHERE EXTRACT(MONTH FROM start_time) = %s AND EXTRACT(YEAR FROM start_time) = %s GROUP BY 1
    """, (mes, ano))
    raw_status = dict(cur.fetchall())

    # 3. Financeiro (6 meses)
    cur.execute("""
        SELECT TO_CHAR(data, 'MM/YYYY'), tipo, SUM(valor) FROM financeiro 
        WHERE data >= CURRENT_DATE - INTERVAL '5 months' GROUP BY 1, 2 ORDER BY MAX(data) ASC
    """)
    raw_fin = cur.fetchall()

    fin_labels, fin_entradas, fin_saidas, temp_fin = [], [], [], {}
    for data_str, tipo, valor in raw_fin:
        if data_str not in temp_fin: temp_fin[data_str] = {'entrada': 0, 'saida': 0}
        temp_fin[data_str][tipo] = float(valor)
    for m in temp_fin:
        fin_labels.append(m)
        fin_entradas.append(temp_fin[m]['entrada'])
        fin_saidas.append(temp_fin[m]['saida'])

    # 4. Totais
    cur.execute("SELECT SUM(valor) FROM financeiro WHERE tipo='entrada' AND EXTRACT(MONTH FROM data)=%s AND EXTRACT(YEAR FROM data)=%s", (mes, ano))
    faturamento = cur.fetchone()[0] or 0

    conn.close()
    return jsonify({
        'sessoes_paciente': {'nomes': [r[0] for r in raw_sessoes], 'qtd': [r[1] for r in raw_sessoes]},
        'status_agendamentos': {'labels': list(raw_status.keys()), 'values': list(raw_status.values())},
        'financeiro': {'labels': fin_labels, 'entradas': fin_entradas, 'saidas': fin_saidas},
        'resumo_mes': {'faturamento': float(faturamento), 'realizadas': int(raw_status.get('Realizado', 0))}
    })

# ==========================================
# APIs FINANCEIRO
# ==========================================

@app.route('/financeiro')
def financeiro():
    if not session.get('logged_in'): return redirect(url_for('login'))
    return render_template('financeiro.html')

@app.route('/api/financeiro/resumo')
def financeiro_resumo():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT SUM(valor) FROM financeiro WHERE tipo = 'entrada'")
        entradas = cur.fetchone()[0] or 0
        cur.execute("SELECT SUM(valor) FROM financeiro WHERE tipo = 'saida'")
        saidas = cur.fetchone()[0] or 0
        return jsonify({'entradas': float(entradas), 'saidas': float(saidas), 'saldo': float(entradas - saidas)})
    except: return jsonify({'entradas': 0, 'saidas': 0, 'saldo': 0})
    finally: conn.close()

@app.route('/api/financeiro/listar')
def financeiro_listar():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, descricao, valor, tipo, categoria, data FROM financeiro ORDER BY data DESC, id DESC LIMIT 50")
    rows = cur.fetchall()
    conn.close()
    return jsonify([{'id':r[0], 'descricao':r[1], 'valor':float(r[2]), 'tipo':r[3], 'categoria':r[4], 'data':r[5].strftime('%d/%m/%Y')} for r in rows])

@app.route('/api/financeiro/salvar', methods=['POST'])
def financeiro_salvar():
    d = request.json
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO financeiro (descricao, valor, tipo, categoria, data) VALUES (%s, %s, %s, %s, %s)",
                    (d['descricao'], d['valor'], d['tipo'], d['categoria'], d['data']))
        conn.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'msg': str(e)}), 500
    finally: conn.close()

@app.route('/api/financeiro/deletar', methods=['POST'])
def financeiro_deletar():
    d = request.json
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM financeiro WHERE id = %s", (d['id'],))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

# ==========================================
# APIs E FUNÇÕES GERAIS (Pacientes, Agenda, Avaliação)
# ==========================================

# --- EXCLUSÃO SEGURA ---
@app.route('/api/deletar_paciente', methods=['POST'])
def deletar_paciente():
    if not session.get('logged_in'): return jsonify({'status': 'error'}), 403
    data = request.json
    pid = data['id']
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        def delete_if_exists(table_name):
            cur.execute(f"SELECT to_regclass('public.{table_name}')")
            if cur.fetchone()[0]: cur.execute(f"DELETE FROM {table_name} WHERE paciente_id = %s", (pid,))
        
        # Limpa dependências
        for t in ['agendamentos', 'evolucoes', 'avaliacoes_completa', 'avaliacao_postural', 'avaliacoes']:
            delete_if_exists(t)

        cur.execute("DELETE FROM pacientes WHERE id = %s", (pid,))
        conn.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally: conn.close()

# --- APIs DE AGENDA ---
@app.route('/api/eventos')
def api_eventos():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT a.id, p.nome, a.start_time, a.end_time, a.obs, a.status FROM agendamentos a JOIN pacientes p ON a.paciente_id = p.id")
    rows = cur.fetchall()
    conn.close()
    eventos = []
    cores = {'Agendado': '#007bff', 'Confirmado': '#17a2b8', 'Realizado': '#198754', 'Faltou': '#dc3545', 'Cancelado': '#6c757d'}
    for row in rows:
        status = row[5] or 'Agendado'
        eventos.append({'id': row[0], 'title': f"{row[1]}", 'start': row[2].isoformat(), 'end': row[3].isoformat(), 'description': row[4], 'extendedProps': {'status': status}, 'color': cores.get(status, '#007bff')})
    return jsonify(eventos)

@app.route('/api/criar_evento', methods=['POST'])
def criar_evento():
    d = request.json
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        start = datetime.fromisoformat(d['start'])
        cur.execute("INSERT INTO agendamentos (paciente_id, start_time, end_time, obs, status) VALUES (%s, %s, %s, %s, 'Agendado')", 
                    (d['paciente_id'], start, start + timedelta(hours=1), d.get('obs', '')))
        conn.commit()
        return jsonify({'status': 'success'})
    except: return jsonify({'status': 'error'}), 500
    finally: conn.close()

@app.route('/api/mover_evento', methods=['POST'])
def mover_evento():
    d = request.json
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE agendamentos SET start_time = %s, end_time = %s WHERE id = %s", (d['start'], d['end'], d['id']))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

@app.route('/api/atualizar_evento', methods=['POST'])
def atualizar_evento():
    d = request.json
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE agendamentos SET status = %s, obs = %s WHERE id = %s", (d['status'], d['obs'], d['id']))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

@app.route('/api/deletar_evento', methods=['POST'])
def deletar_evento():
    d = request.json
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM agendamentos WHERE id = %s", (d['id'],))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

# --- APIs DE EVOLUÇÃO ---
@app.route('/api/evolucoes/<int:pid>', methods=['GET'])
def get_evolucoes(pid):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT data, texto FROM evolucoes WHERE paciente_id = %s ORDER BY data DESC", (pid,))
    data = [{'data': r[0].strftime("%d/%m/%Y %H:%M"), 'texto': r[1]} for r in cur.fetchall()]
    conn.close()
    return jsonify(data)

@app.route('/api/nova_evolucao', methods=['POST'])
def nova_evolucao():
    d = request.json
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO evolucoes (paciente_id, texto, data) VALUES (%s, %s, NOW())", (d['paciente_id'], d['texto']))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

# --- APIs DE AVALIAÇÃO (COMPLETA + PILATES + QUIRO + CARDIO) ---
@app.route('/api/salvar_avaliacao', methods=['POST'])
def salvar_avaliacao():
    d = request.json
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Prepara campos novos
        dados_pilates = d.get('dados_pilates', '')
        dados_quiro = d.get('dados_quiro', '')
        dados_cardio = d.get('dados_cardio', '') # <--- NOVO (TC6/Cardio)

        cur.execute("""
            INSERT INTO avaliacoes_completa 
            (paciente_id, ocupacao, lateralidade, diagnostico_medico, queixa_principal, hma, hpp, habitos, sinais_vitais, avaliacao_dor, inspecao, palpacao, adm, forca_muscular, neuro, testes_especiais, diagnostico_cif, objetivos, conduta, dados_pilates, dados_quiro, dados_cardio) 
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (d['paciente_id'], d['ocupacao'], d['lateralidade'], d['diagnostico_medico'], d['queixa_principal'], d['hma'], d['hpp'], d['habitos'], d['sinais_vitais'], d['avaliacao_dor'], d['inspecao'], d['palpacao'], d['adm'], d['forca_muscular'], d['neuro'], d['testes_especiais'], d['diagnostico_cif'], d['objetivos'], d['conduta'], dados_pilates, dados_quiro, dados_cardio))
        
        conn.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'msg': str(e)}), 500
    finally: conn.close()

@app.route('/api/get_avaliacao/<int:pid>', methods=['GET'])
def get_avaliacao(pid):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Adicionamos a leitura de dados_cardio
        cur.execute("SELECT ocupacao, lateralidade, diagnostico_medico, queixa_principal, hma, hpp, habitos, sinais_vitais, avaliacao_dor, inspecao, palpacao, adm, forca_muscular, neuro, testes_especiais, diagnostico_cif, objetivos, conduta, data_avaliacao, dados_pilates, dados_quiro, dados_cardio FROM avaliacoes_completa WHERE paciente_id = %s ORDER BY id DESC LIMIT 1", (pid,))
        r = cur.fetchone()
        
        if r: 
            return jsonify({
                'encontrado': True, 
                'ocupacao': r[0], 'lateralidade': r[1], 'diagnostico_medico': r[2], 'queixa_principal': r[3], 'hma': r[4], 'hpp': r[5], 'habitos': r[6], 'sinais_vitais': r[7], 'avaliacao_dor': r[8], 'inspecao': r[9], 'palpacao': r[10], 'adm': r[11], 'forca_muscular': r[12], 'neuro': r[13], 'testes_especiais': r[14], 'diagnostico_cif': r[15], 'objetivos': r[16], 'conduta': r[17], 
                'data': r[18].strftime("%d/%m/%Y"),
                'dados_pilates': r[19] if len(r) > 19 else '', 
                'dados_quiro': r[20] if len(r) > 20 else '',
                'dados_cardio': r[21] if len(r) > 21 else '' # <--- NOVO (TC6/Cardio)
            })
        return jsonify({'encontrado': False})
    except Exception as e:
        return jsonify({'encontrado': False})
    finally:
        conn.close()

@app.route('/api/salvar_fotos', methods=['POST'])
def salvar_fotos():
    d = request.json
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO avaliacao_postural (paciente_id, foto_frontal, foto_posterior, foto_lat_dir, foto_lat_esq, analise_ia) VALUES (%s,%s,%s,%s,%s,%s)", 
                    (d['paciente_id'], d.get('frontal'), d.get('posterior'), d.get('lat_dir'), d.get('lat_esq'), d.get('analise_ia')))
        conn.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'msg': str(e)}), 500
    finally: conn.close()

@app.route('/api/get_fotos/<int:pid>', methods=['GET'])
def get_fotos(pid):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT foto_frontal, foto_posterior, foto_lat_dir, foto_lat_esq, analise_ia, data_foto FROM avaliacao_postural WHERE paciente_id = %s ORDER BY id DESC LIMIT 1", (pid,))
    r = cur.fetchone()
    conn.close()
    if r: return jsonify({'encontrado': True, 'frontal': r[0], 'posterior': r[1], 'lat_dir': r[2], 'lat_esq': r[3], 'analise': r[4], 'data': r[5].strftime("%d/%m/%Y")})
    return jsonify({'encontrado': False})

# --- APIs PACIENTE ---
@app.route('/api/get_paciente/<int:id>', methods=['GET'])
def get_paciente(id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT id, nome, data_nascimento, telefone, cpf, endereco FROM pacientes WHERE id = %s', (id,))
    p = cur.fetchone()
    conn.close()
    if p: return jsonify({'id': p[0], 'nome': p[1], 'data_nascimento': p[2].strftime('%Y-%m-%d') if p[2] else '', 'telefone': p[3], 'cpf': p[4], 'endereco': p[5]})
    return jsonify({'erro': 'Paciente não encontrado'}), 404

@app.route('/api/salvar_paciente', methods=['POST'])
def salvar_paciente():
    data = request.json
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        nome = data.get('nome')
        if not nome: return jsonify({'erro': 'O nome é obrigatório!'}), 400
        args = (nome, data.get('data_nascimento') or None, data.get('telefone') or None, data.get('cpf') or None, data.get('endereco') or None)
        if data.get('id'):
            cur.execute("UPDATE pacientes SET nome=%s, data_nascimento=%s, telefone=%s, cpf=%s, endereco=%s WHERE id=%s", args + (data['id'],))
        else:
            cur.execute("INSERT INTO pacientes (nome, data_nascimento, telefone, cpf, endereco) VALUES (%s, %s, %s, %s, %s)", args)
        conn.commit()
        return jsonify({'mensagem': 'Salvo com sucesso!'})
    except Exception as e:
        conn.rollback()
        return jsonify({'erro': f"Erro no sistema: {str(e)}"}), 500
    finally: conn.close()

@app.route('/delete_paciente_via_form/<int:id>', methods=['POST'])
def delete_paciente_via_form(id):
    if not session.get('logged_in'): return redirect(url_for('login'))
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM pacientes WHERE id = %s", (id,))
        conn.commit()
    except: pass
    finally: conn.close()
    return redirect(url_for('pacientes'))

if __name__ == '__main__':
    app.run(debug=True)
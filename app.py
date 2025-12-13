import streamlit as st
import pandas as pd
import psycopg2
import os
from datetime import datetime

# --- Configuração da Página ---
st.set_page_config(page_title="FisioManager", page_icon="🩺", layout="centered")

# --- Conexão com Banco de Dados (Robusta) ---
def get_db_connection():
    try:
        # Verifica se está rodando localmente (secrets.toml) ou no Render (Variáveis)
        if ".streamlit/secrets.toml" in os.listdir() or os.path.exists(".streamlit/secrets.toml"):
             db_config = st.secrets["postgres"]
             conn = psycopg2.connect(**db_config)
        else:
            # Conexão via Render (Variáveis de Ambiente)
            conn = psycopg2.connect(
                host=os.environ["DB_HOST"],
                database=os.environ["DB_NAME"],
                user=os.environ["DB_USER"],
                password=os.environ["DB_PASS"],
                port=os.environ["DB_PORT"]
            )
        return conn
    except Exception as e:
        st.error(f"❌ Erro de Conexão: {e}")
        return None

def init_db():
    conn = get_db_connection()
    if not conn:
        st.warning("⚠️ O sistema não conseguiu conectar ao banco. Verifique as configurações no Render.")
        return

    c = conn.cursor()
    try:
        # Criação das tabelas se não existirem
        c.execute('''CREATE TABLE IF NOT EXISTS pacientes (
                        id SERIAL PRIMARY KEY, 
                        nome TEXT NOT NULL, 
                        idade INTEGER, 
                        telefone TEXT, 
                        historico TEXT
                    );''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS agendamentos (
                        id SERIAL PRIMARY KEY, 
                        paciente_id INTEGER REFERENCES pacientes(id), 
                        data DATE, 
                        hora TIME, 
                        obs TEXT
                    );''')
        conn.commit()
    except Exception as e:
        st.error(f"Erro ao criar tabelas: {e}")
    finally:
        c.close()
        conn.close()

def run_query(query, params=(), fetch=False):
    conn = get_db_connection()
    if conn:
        c = conn.cursor()
        try:
            c.execute(query, params)
            if fetch:
                data = c.fetchall()
                return data
            conn.commit()
        except Exception as e:
            st.error(f"Erro na operação: {e}")
        finally:
            c.close()
            conn.close()
    return None

# --- Inicialização ---
# Tenta criar as tabelas ao carregar
init_db()

# --- Interface Visual do Usuário ---

st.title("🩺 FisioManager")
st.markdown("---")

# Menu Lateral
menu = ["🏠 Início", "👥 Pacientes", "📅 Agenda", "📝 Novo Agendamento"]
choice = st.sidebar.selectbox("Menu", menu)

# --- 1. Página Inicial ---
if choice == "🏠 Início":
    st.subheader("Painel Geral")
    try:
        total_pacientes = run_query("SELECT COUNT(*) FROM pacientes", fetch=True)[0][0]
        total_agendamentos = run_query("SELECT COUNT(*) FROM agendamentos", fetch=True)[0][0]
        
        c1, c2 = st.columns(2)
        c1.metric("Total de Pacientes", total_pacientes)
        c2.metric("Consultas Agendadas", total_agendamentos)
        
        st.info("Sistema online e conectado ao Banco de Dados PostgreSQL.")
    except:
        st.warning("Não foi possível carregar os dados. Verifique a conexão.")

# --- 2. Gestão de Pacientes ---
elif choice == "👥 Pacientes":
    st.subheader("Gerenciar Pacientes")
    
    tab1, tab2 = st.tabs(["📋 Lista de Pacientes", "➕ Cadastrar Novo"])
    
    with tab1:
        dados = run_query("SELECT id, nome, idade, telefone, historico FROM pacientes ORDER BY id DESC", fetch=True)
        if dados:
            df = pd.DataFrame(dados, columns=["ID", "Nome", "Idade", "Telefone", "Histórico"])
            st.dataframe(df, use_container_width=True)
        else:
            st.info("Nenhum paciente encontrado.")

    with tab2:
        with st.form("form_paciente"):
            nome = st.text_input("Nome Completo")
            c1, c2 = st.columns(2)
            idade = c1.number_input("Idade", min_value=0, max_value=120)
            telefone = c2.text_input("Telefone")
            historico = st.text_area("Histórico / Queixa")
            
            if st.form_submit_button("Salvar Paciente"):
                if nome:
                    run_query("INSERT INTO pacientes (nome, idade, telefone, historico) VALUES (%s, %s, %s, %s)", 
                              (nome, idade, telefone, historico))
                    st.success(f"Paciente {nome} salvo com sucesso!")
                    st.rerun()
                else:
                    st.error("O nome é obrigatório.")

# --- 3. Agenda ---
elif choice == "📅 Agenda":
    st.subheader("Agenda de Consultas")
    
    agenda = run_query('''
        SELECT a.data, a.hora, p.nome, a.obs 
        FROM agendamentos a
        JOIN pacientes p ON a.paciente_id = p.id
        ORDER BY a.data DESC, a.hora ASC
    ''', fetch=True)
    
    if agenda:
        df_agenda = pd.DataFrame(agenda, columns=["Data", "Hora", "Paciente", "Observação"])
        st.dataframe(df_agenda, use_container_width=True)
    else:
        st.info("Nenhuma consulta agendada.")

# --- 4. Novo Agendamento ---
elif choice == "📝 Novo Agendamento":
    st.subheader("Marcar Nova Consulta")
    
    pacientes = run_query("SELECT id, nome FROM pacientes", fetch=True)
    
    if not pacientes:
        st.warning("Cadastre um paciente primeiro na aba 'Pacientes'.")
    else:
        # Cria um dicionário {Nome: ID} para o menu suspenso
        lista_nomes = {nome: id_p for id_p, nome in pacientes}
        selecionado = st.selectbox("Selecione o Paciente", list(lista_nomes.keys()))
        
        c1, c2 = st.columns(2)
        data = c1.date_input("Data", datetime.today())
        hora = c2.time_input("Hora", datetime.now().time())
        obs = st.text_area("Observação da Sessão")
        
        if st.button("Confirmar Agendamento"):
            id_paciente = lista_nomes[selecionado]
            run_query("INSERT INTO agendamentos (paciente_id, data, hora, obs) VALUES (%s, %s, %s, %s)",
                      (id_paciente, data, hora, obs))
            st.success("Agendamento realizado!")
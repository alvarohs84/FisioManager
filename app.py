import streamlit as st
import pandas as pd
import psycopg2
import os
from datetime import datetime
import time

# --- 1. CONFIGURAÇÃO DA PÁGINA (WIDE LAYOUT) ---
st.set_page_config(
    page_title="FisioManager Pro",
    page_icon="🩺",
    layout="wide", # Usa a tela inteira
    initial_sidebar_state="expanded"
)

# --- 2. ESTILO CSS PERSONALIZADO (A MÁGICA DO DESIGN) ---
st.markdown("""
<style>
    /* Fundo geral mais claro e limpo */
    .stApp {
        background-color: #f8f9fa;
    }
    
    /* Estilo dos Cards (Métricas) */
    .css-1r6slb0 {
        background-color: white;
        border-radius: 15px;
        padding: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        border-left: 5px solid #007bff;
    }
    
    /* Títulos mais modernos */
    h1, h2, h3 {
        color: #2c3e50;
        font-family: 'Helvetica Neue', sans-serif;
    }
    
    /* Botões mais profissionais */
    .stButton>button {
        background-color: #007bff;
        color: white;
        border-radius: 8px;
        border: none;
        padding: 10px 24px;
        font-weight: bold;
        width: 100%;
    }
    .stButton>button:hover {
        background-color: #0056b3;
    }
    
    /* Ajuste da Sidebar */
    section[data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #e0e0e0;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. LÓGICA DE LOGIN E BANCO DE DADOS (MANTIDA) ---

def check_password():
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False

    if st.session_state["logged_in"]:
        return True

    # Tela de Login Centralizada e Bonita
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown("<br><br><h2 style='text-align: center;'>🔐 Acesso FisioManager</h2>", unsafe_allow_html=True)
        with st.form("login_form"):
            senha_digitada = st.text_input("Senha de Acesso", type="password")
            submitted = st.form_submit_button("Entrar no Sistema")
            
            if submitted:
                senha_correta = os.environ.get("SYS_PASSWORD")
                if not senha_correta and os.path.exists(".streamlit/secrets.toml"):
                    senha_correta = st.secrets["general"]["password"]
                
                if senha_digitada == senha_correta:
                    st.session_state["logged_in"] = True
                    st.success("Acesso autorizado!")
                    st.rerun()
                else:
                    st.error("Senha incorreta.")
    return False

def get_db_connection():
    try:
        if os.path.exists(".streamlit/secrets.toml"):
             db_config = st.secrets["postgres"]
             return psycopg2.connect(**db_config)
        else:
            return psycopg2.connect(
                host=os.environ["DB_HOST"],
                database=os.environ["DB_NAME"],
                user=os.environ["DB_USER"],
                password=os.environ["DB_PASS"],
                port=os.environ["DB_PORT"]
            )
    except Exception as e:
        st.error(f"❌ Erro de Conexão: {e}")
        return None

def run_query(query, params=(), fetch=False):
    conn = get_db_connection()
    if conn:
        c = conn.cursor()
        try:
            c.execute(query, params)
            if fetch:
                data = c.fetchall()
                conn.close()
                return data
            conn.commit()
            conn.close()
            return None
        except Exception as e:
            conn.close()
            st.error(f"Erro na operação: {e}")
            return None
    return None

def init_db():
    conn = get_db_connection()
    if not conn: return
    c = conn.cursor()
    try:
        c.execute('''CREATE TABLE IF NOT EXISTS pacientes (id SERIAL PRIMARY KEY, nome TEXT NOT NULL, idade INTEGER, telefone TEXT, historico TEXT);''')
        c.execute('''CREATE TABLE IF NOT EXISTS agendamentos (id SERIAL PRIMARY KEY, paciente_id INTEGER REFERENCES pacientes(id), data DATE, hora TIME, obs TEXT);''')
        conn.commit()
    finally:
        c.close()
        conn.close()

# --- 4. EXECUÇÃO PRINCIPAL ---

if not check_password():
    st.stop()

init_db()

# --- MENU LATERAL (SIDEBAR) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3063/3063176.png", width=70) # Ícone médico genérico
    st.title("FisioManager")
    st.caption("Gestão Clínica Inteligente")
    st.markdown("---")
    
    menu_options = {
        "Início": "🏠",
        "Pacientes": "👥",
        "Agenda": "📅",
        "Novo Agendamento": "➕",
        "Sair": "🚪"
    }
    
    choice = st.radio("Navegação", list(menu_options.keys()))
    
    st.markdown("---")
    st.info("💡 Suporte: (XX) 9999-9999")

# --- CONTEÚDO DAS PÁGINAS ---

# 🏠 PÁGINA INICIAL (DASHBOARD)
if choice == "Início":
    st.title(f"{menu_options[choice]} Dashboard Geral")
    st.markdown("Visão geral da sua clínica hoje.")
    
    # Cards de Métricas Estilizados
    try:
        res_pacientes = run_query("SELECT COUNT(*) FROM pacientes", fetch=True)
        total_pacientes = res_pacientes[0][0] if res_pacientes else 0
        
        res_agendamentos = run_query("SELECT COUNT(*) FROM agendamentos", fetch=True)
        total_agendamentos = res_agendamentos[0][0] if res_agendamentos else 0
        
        # Layout de Cards
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric(label="Total de Pacientes", value=total_pacientes, delta="Ativos")
        with c2:
            st.metric(label="Consultas Agendadas", value=total_agendamentos, delta="No sistema")
        with c3:
            st.metric(label="Faturamento (Est.)", value="R$ --", delta="Em breve", delta_color="off")
        
    except Exception as e:
        st.error("Erro ao carregar dashboard.")

    st.markdown("---")
    st.subheader("Atalhos Rápidos")
    col_a, col_b = st.columns(2)
    with col_a:
        st.info("👉 Vá para a aba **'Novo Agendamento'** para marcar uma sessão.")
    with col_b:
        st.success("👉 Vá para a aba **'Pacientes'** para ver fichas completas.")

# 👥 PÁGINA DE PACIENTES
elif choice == "Pacientes":
    c1, c2 = st.columns([3, 1])
    with c1:
        st.title("Gerenciar Pacientes")
    with c2:
        # Botão que simula ação principal (apenas visual aqui)
        st.write("") 
    
    tab1, tab2 = st.tabs(["📋 Base de Dados", "➕ Novo Cadastro"])
    
    with tab1:
        dados = run_query("SELECT id, nome, idade, telefone, historico FROM pacientes ORDER BY id DESC", fetch=True)
        if dados:
            df = pd.DataFrame(dados, columns=["ID", "Nome", "Idade", "Contato", "Histórico Clínico"])
            # Dataframe com estilo
            st.dataframe(
                df, 
                use_container_width=True,
                hide_index=True,
                column_config={
                    "ID": st.column_config.NumberColumn(width="small"),
                    "Histórico Clínico": st.column_config.TextColumn(width="large"),
                }
            )
        else:
            st.warning("Nenhum paciente encontrado.")

    with tab2:
        st.markdown("### Ficha Cadastral")
        with st.form("form_paciente", clear_on_submit=True):
            col_nome, col_idade = st.columns([3, 1])
            nome = col_nome.text_input("Nome Completo")
            idade = col_idade.number_input("Idade", min_value=0, max_value=120)
            
            col_tel, col_vazia = st.columns([1, 1])
            telefone = col_tel.text_input("Telefone / WhatsApp")
            
            historico = st.text_area("Anamnese / Queixa Principal", height=150)
            
            if st.form_submit_button("💾 Salvar Paciente"):
                if nome:
                    run_query("INSERT INTO pacientes (nome, idade, telefone, historico) VALUES (%s, %s, %s, %s)", 
                              (nome, idade, telefone, historico))
                    st.toast(f"Paciente {nome} cadastrado com sucesso!", icon="✅")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Nome é obrigatório.")

# 📅 PÁGINA DE AGENDA
elif choice == "Agenda":
    st.title("Agenda de Consultas")
    
    col_filter, col_calendar = st.columns([1, 3])
    
    with col_filter:
        st.markdown("### Filtros")
        data_filtro = st.date_input("Filtrar por data", datetime.today())
        st.info("Em breve: Visualização mensal completa.")

    with col_calendar:
        # Busca apenas agendamentos a partir de hoje (exemplo de melhoria) ou todos
        agenda = run_query('''
            SELECT a.data, a.hora, p.nome, a.obs 
            FROM agendamentos a
            JOIN pacientes p ON a.paciente_id = p.id
            ORDER BY a.data DESC, a.hora ASC
        ''', fetch=True)
        
        if agenda:
            df_agenda = pd.DataFrame(agenda, columns=["Data", "Hora", "Paciente", "Observação"])
            # Formata a data para ficar bonita (DD/MM/AAAA)
            df_agenda['Data'] = pd.to_datetime(df_agenda['Data']).dt.strftime('%d/%m/%Y')
            
            st.dataframe(
                df_agenda,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Hora": st.column_config.TimeColumn(format="HH:mm"),
                }
            )
        else:
            st.info("Nenhum agendamento encontrado.")

# ➕ NOVO AGENDAMENTO
elif choice == "Novo Agendamento":
    st.title("Agendar Sessão")
    
    with st.container():
        st.markdown("Preencha os dados abaixo para confirmar a reserva.")
        
        pacientes = run_query("SELECT id, nome FROM pacientes", fetch=True)
        
        if not pacientes:
            st.error("⚠️ Cadastre pacientes primeiro.")
        else:
            lista_nomes = {nome: id_p for id_p, nome in pacientes}
            
            with st.form("form_agendamento"):
                col_p, col_d = st.columns([2, 1])
                selecionado = col_p.selectbox("Paciente", list(lista_nomes.keys()))
                data = col_d.date_input("Data da Sessão", datetime.today())
                
                col_h, col_o = st.columns([1, 2])
                hora = col_h.time_input("Horário", datetime.now().time())
                obs = col_o.text_input("Observação Rápida (Ex: Sessão 3/10)")
                
                if st.form_submit_button("Confirmar Agendamento"):
                    id_paciente = lista_nomes[selecionado]
                    run_query("INSERT INTO agendamentos (paciente_id, data, hora, obs) VALUES (%s, %s, %s, %s)",
                              (id_paciente, data, hora, obs))
                    st.toast("Agendamento Confirmado!", icon="📆")

elif choice == "Sair":
    st.session_state["logged_in"] = False
    st.rerun()
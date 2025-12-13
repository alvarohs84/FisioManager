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
    layout="wide", # Ocupa a tela toda
    initial_sidebar_state="expanded"
)

# --- 2. CSS CUSTOMIZADO (DESIGN SYSTEM) ---
# Aqui acontece a mágica visual. Mudamos cores, fontes e bordas.
st.markdown("""
<style>
    /* Fundo geral levemente cinza para não cansar a vista */
    .stApp {
        background-color: #f4f6f9;
    }
    
    /* Estilo da Sidebar */
    section[data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #e0e0e0;
    }
    
    /* Cartões de Métricas (KPIs) */
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        padding: 15px 25px;
        border-radius: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    
    /* Botões Primários (Azul Profissional) */
    .stButton>button {
        background-color: #007bff;
        color: white;
        border-radius: 8px;
        border: none;
        height: 3em;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background-color: #0056b3;
        box-shadow: 0 4px 8px rgba(0,123,255,0.2);
    }
    
    /* Tabelas mais limpas */
    div[data-testid="stDataFrame"] {
        background-color: white;
        padding: 10px;
        border-radius: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    
    /* Cabeçalhos */
    h1, h2, h3 {
        color: #2c3e50;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. FUNÇÕES DE BACKEND (Conexão e Lógica) ---

def check_password():
    """Gerencia o login com visual aprimorado"""
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False

    if st.session_state["logged_in"]:
        return True

    # Layout de Login Centralizado
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        container = st.container()
        with container:
            st.markdown("<h2 style='text-align: center;'>🔐 Acesso Clínico</h2>", unsafe_allow_html=True)
            st.info("Ambiente Seguro - FisioManager")
            
            with st.form("login_form"):
                senha = st.text_input("Senha de Acesso", type="password")
                submit = st.form_submit_button("Entrar no Sistema", use_container_width=True)
                
                if submit:
                    # Busca senha no Render ou Local
                    senha_correta = os.environ.get("SYS_PASSWORD")
                    if not senha_correta and os.path.exists(".streamlit/secrets.toml"):
                        senha_correta = st.secrets["general"]["password"]
                    
                    if senha == senha_correta:
                        st.session_state["logged_in"] = True
                        st.toast("Login realizado com sucesso!", icon="✅")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Acesso negado.")
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
        st.error(f"❌ Falha de Conexão: {e}")
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
            st.error(f"Erro de Execução: {e}")
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

# --- 4. APLICAÇÃO PRINCIPAL ---

if not check_password():
    st.stop()

init_db() # Garante tabelas criadas

# --- SIDEBAR (MENU LATERAL) ---
with st.sidebar:
    st.title("🩺 FisioManager")
    st.caption("v 2.0 Professional")
    st.markdown("---")
    
    # Menu com ícones visuais
    choice = st.radio(
        "Navegação", 
        ["Dashboard", "Pacientes", "Agenda", "Novo Agendamento"],
        captions=["Visão Geral", "Base de Dados", "Calendário", "Marcar Sessão"]
    )
    
    st.markdown("---")
    st.info("📞 Suporte Técnico\n(XX) 9999-9999")
    
    if st.button("Sair (Logout)"):
        st.session_state["logged_in"] = False
        st.rerun()

# --- CONTEÚDO DAS PÁGINAS ---

# 🏠 DASHBOARD (Página Inicial)
if choice == "Dashboard":
    st.title("📊 Painel de Controle")
    st.markdown("Visão geral da performance da clínica.")
    
    # Bloco de Métricas (Cards)
    try:
        res_pacientes = run_query("SELECT COUNT(*) FROM pacientes", fetch=True)
        total_p = res_pacientes[0][0] if res_pacientes else 0
        
        res_agend = run_query("SELECT COUNT(*) FROM agendamentos", fetch=True)
        total_a = res_agend[0][0] if res_agend else 0
        
        # Colunas para layout horizontal
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Pacientes Totais", total_p, delta="Cadastrados")
        c2.metric("Consultas Agendadas", total_a, delta="No sistema")
        c3.metric("Faturamento (Mês)", "R$ --", delta="Em breve", delta_color="off")
        c4.metric("Status do Sistema", "Online", delta="PostgreSQL")
        
    except Exception as e:
        st.error("Erro ao carregar métricas.")
        
    st.markdown("---")
    st.subheader("Acesso Rápido")
    col_a, col_b = st.columns(2)
    with col_a:
        st.info("👉 Para cadastrar um novo paciente, vá na aba **Pacientes**.")
    with col_b:
        st.success("👉 Para marcar uma consulta, use a aba **Novo Agendamento**.")

# 👥 PACIENTES
elif choice == "Pacientes":
    col_header, col_btn = st.columns([4, 1])
    col_header.title("Gestão de Pacientes")
    
    tab_list, tab_new = st.tabs(["📂 Base de Pacientes", "➕ Novo Cadastro"])
    
    with tab_list:
        dados = run_query("SELECT id, nome, idade, telefone, historico FROM pacientes ORDER BY id DESC", fetch=True)
        if dados:
            df = pd.DataFrame(dados, columns=["ID", "Nome", "Idade", "Telefone", "Histórico"])
            # Tabela Interativa e Bonita
            st.dataframe(
                df, 
                use_container_width=True,
                hide_index=True,
                column_config={
                    "ID": st.column_config.NumberColumn(width="small"),
                    "Histórico": st.column_config.TextColumn(width="large"),
                }
            )
        else:
            st.warning("Nenhum paciente encontrado na base de dados.")

    with tab_new:
        st.markdown("### Ficha Cadastral")
        with st.form("form_paciente", clear_on_submit=True):
            # Layout em Grid (Lado a Lado)
            c_nome, c_idade = st.columns([3, 1])
            nome = c_nome.text_input("Nome Completo")
            idade = c_idade.number_input("Idade", min_value=0, step=1)
            
            c_tel, c_blank = st.columns([1, 1])
            telefone = c_tel.text_input("Telefone / Celular")
            
            historico = st.text_area("Anamnese / Observações Clínicas", height=150)
            
            if st.form_submit_button("💾 Salvar Ficha do Paciente"):
                if nome:
                    run_query("INSERT INTO pacientes (nome, idade, telefone, historico) VALUES (%s, %s, %s, %s)", 
                              (nome, idade, telefone, historico))
                    st.toast(f"Paciente {nome} cadastrado com sucesso!", icon="✅")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("O campo Nome é obrigatório.")

# 📅 AGENDA
elif choice == "Agenda":
    st.title("Agenda Clínica")
    
    col_kpi, col_table = st.columns([1, 3])
    
    with col_kpi:
        st.markdown("### 🔍 Filtros")
        data_sel = st.date_input("Filtrar Data", datetime.today())
        st.caption("Selecione uma data para ver os horários.")
        st.info("Dica: A agenda mostra os próximos compromissos em ordem.")

    with col_table:
        agenda = run_query('''
            SELECT a.data, a.hora, p.nome, a.obs 
            FROM agendamentos a
            JOIN pacientes p ON a.paciente_id = p.id
            ORDER BY a.data DESC, a.hora ASC
        ''', fetch=True)
        
        if agenda:
            df_agenda = pd.DataFrame(agenda, columns=["Data", "Hora", "Paciente", "Observação"])
            # Formatação de Data Brasileira
            df_agenda['Data'] = pd.to_datetime(df_agenda['Data']).dt.strftime('%d/%m/%Y')
            
            st.dataframe(
                df_agenda,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Hora": st.column_config.TimeColumn(format="HH:mm"),
                    "Observação": st.column_config.TextColumn(width="medium")
                }
            )
        else:
            st.info("Nenhum agendamento encontrado.")

# ➕ NOVO AGENDAMENTO
elif choice == "Novo Agendamento":
    st.title("Agendar Sessão")
    st.markdown("Preencha os dados abaixo para reservar um horário.")
    
    pacientes = run_query("SELECT id, nome FROM pacientes", fetch=True)
    
    if not pacientes:
        st.warning("⚠️ Você precisa cadastrar pacientes antes de agendar.")
    else:
        lista_nomes = {nome: id_p for id_p, nome in pacientes}
        
        with st.container(): # Container para dar um visual de "bloco"
            with st.form("form_agendamento"):
                # Linha 1: Paciente e Data
                c1, c2 = st.columns([2, 1])
                selecionado = c1.selectbox("Selecione o Paciente", list(lista_nomes.keys()))
                data = c2.date_input("Data da Consulta", datetime.today())
                
                # Linha 2: Hora e Obs
                c3, c4 = st.columns([1, 2])
                hora = c3.time_input("Horário", datetime.now().time())
                obs = c4.text_input("Motivo / Observação (Opcional)")
                
                # Botão de Ação Full Width
                if st.form_submit_button("✅ Confirmar Agendamento", use_container_width=True):
                    id_paciente = lista_nomes[selecionado]
                    run_query("INSERT INTO agendamentos (paciente_id, data, hora, obs) VALUES (%s, %s, %s, %s)",
                              (id_paciente, data, hora, obs))
                    st.toast("Agendamento realizado com sucesso!", icon="📆")
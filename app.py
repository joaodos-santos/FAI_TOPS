import streamlit as st
import json
import tempfile
import os
from fpdf import FPDF
from pathlib import Path

# ==========================================
# CONFIGURAÇÃO INICIAL E ESTADOS
# ==========================================
st.set_page_config(page_title="Gerador de FAI", layout="wide")

# Inicialização das variáveis de sessão
if 'admin_auth' not in st.session_state:
    st.session_state.admin_auth = False
if 'show_exit_dialog' not in st.session_state:
    st.session_state.show_exit_dialog = False
if 'erro_login' not in st.session_state:
    st.session_state.erro_login = False

# --- FUNÇÕES DE CALLBACK (Executam antes da tela renderizar) ---
def tentar_login():
    senha = st.session_state.input_senha
    try:
        senha_correta = st.secrets["senha_admin"]
    except:
        senha_correta = "fab2026"
        
    if senha == senha_correta:
        st.session_state.admin_auth = True
        st.session_state.curso_selector = None  # Limpa o seletor de forma segura
        st.session_state.erro_login = False
    else:
        st.session_state.erro_login = True

def limpar_memoria_admin():
    for k in list(st.session_state.keys()):
        if k.startswith(('sigla_pasta', 'nome_cabecalho', 'titulo', 'subtitulo', 'instrucoes', 'enunciado_', 'pud_', 'texto_', 'pontos_', 'num_itens_q', 'num_questoes')):
            del st.session_state[k]

def confirmar_saida():
    st.session_state.admin_auth = False
    st.session_state.show_exit_dialog = False
    limpar_memoria_admin()

def cancelar_saida():
    st.session_state.show_exit_dialog = False
    st.session_state.curso_selector = None # Reverte a seleção de forma segura


CURSOS_DIR = Path("cursos")
if not CURSOS_DIR.exists():
    CURSOS_DIR.mkdir()

st.sidebar.image("https://upload.wikimedia.org/wikipedia/commons/thumb/1/13/Emblema_da_For%C3%A7a_A%C3%A9rea_Brasileira.svg/1200px-Emblema_da_For%C3%A7a_A%C3%A9rea_Brasileira.svg.png", width=100)
st.sidebar.title("Navegação")

cursos_disponiveis = [d.name for d in CURSOS_DIR.iterdir() if d.is_dir()]
cursos_disponiveis.sort()

# ==========================================
# LÓGICA DA BARRA LATERAL (LOGIN / NAVEGAÇÃO)
# ==========================================
curso_selecionado = st.sidebar.selectbox(
    "Selecione a FAI do Curso:", 
    cursos_disponiveis if cursos_disponiveis else ["Nenhum"],
    index=None,
    placeholder="Escolha um curso...",
    key="curso_selector"
)

st.sidebar.divider()

# Acesso do Coordenador
if not st.session_state.admin_auth:
    with st.sidebar.expander("🔒 Acesso do Coordenador"):
        st.text_input("Senha de Acesso", type="password", key="input_senha")
        st.button("Entrar no Painel", use_container_width=True, on_click=tentar_login)
        
        if st.session_state.erro_login:
            st.error("Senha incorreta!")
else:
    st.sidebar.success("✅ Logado como Coordenador")
    
    # 1. Se clicar no botão de Sair explicitamente
    if st.sidebar.button("🚪 Sair do Painel", use_container_width=True):
        st.session_state.show_exit_dialog = True
        
    # 2. Se tentar selecionar um curso na barra enquanto edita
    if st.session_state.curso_selector is not None:
        st.session_state.show_exit_dialog = True

# ==========================================
# MODAIS E PDF
# ==========================================
@st.dialog("⚠️ Confirmação de Saída")
def modal_sair_painel():
    st.warning("Quaisquer alterações não salvas no Construtor Visual serão perdidas.")
    st.write("Deseja realmente sair do Painel do Coordenador?")
    
    col1, col2 = st.columns(2)
    with col1:
        st.button("✅ Sim, Sair", use_container_width=True, type="primary", on_click=confirmar_saida)
    with col2:
        st.button("❌ Não, Continuar editando", use_container_width=True, on_click=cancelar_saida)

if st.session_state.show_exit_dialog:
    modal_sair_painel()

class PDF(FPDF):
    def set_config(self, config_data):
        self.config_data = config_data
        
    def header(self):
        if hasattr(self, 'config_data'):
            self.set_font("helvetica", "B", 14)
            self.cell(0, 8, self.config_data['cabecalho'].get('curso',''), align="C", new_x="LMARGIN", new_y="NEXT")
            self.set_font("helvetica", "B", 12)
            self.cell(0, 8, self.config_data['cabecalho'].get('titulo',''), align="C", new_x="LMARGIN", new_y="NEXT")
            self.cell(0, 8, self.config_data['cabecalho'].get('subtitulo',''), align="C", new_x="LMARGIN", new_y="NEXT")
            self.ln(5)

def gerar_arquivo_pdf(config, respostas, aluno, tutor, nota_final, is_vazia):
    pdf = PDF()
    pdf.set_config(config)
    pdf.add_page()
    aluno_str = aluno.upper() if aluno else ""
    tutor_str = tutor.upper() if tutor else ""
    
    pdf.set_font("helvetica", "B", 11)
    pdf.cell(130, 8, f"ALUNO: {aluno_str}", border=0)
    if is_vazia:
        pdf.cell(0, 8, "", border=0, align="R", new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.set_text_color(0, 51, 102) 
        pdf.cell(0, 8, f"NOTA FINAL: {nota_final:.2f} / 10.00", border=0, align="R", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
    
    pdf.set_font("helvetica", "", 10)
    pdf.cell(0, 8, f"INSTRUTOR: {tutor_str}", border=0, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    
    if config.get("instrucoes"):
        pdf.set_font("helvetica", "I", 9)
        pdf.multi_cell(0, 5, text=config['instrucoes'], new_x="LMARGIN", new_y="NEXT")
        pdf.ln(5)
    
    for q in config.get('questoes', []):
        linhas_enunciado = max(1, len(q['enunciado']) // 90 + 1)
        altura_estimada = (linhas_enunciado * 7) + (len(q['itens']) * 6) + 12
        if "pud" in q: altura_estimada += 6
            
        if pdf.get_y() + altura_estimada > 275:
            pdf.add_page()
        
        pdf.set_fill_color(240, 240, 240)
        pdf.set_font("helvetica", "B", 10)
        pdf.multi_cell(0, 7, text=q['enunciado'], border="LTR", fill=True, new_x="LMARGIN", new_y="NEXT")
        
        pdf.set_fill_color(255, 255, 255)
        pdf.set_font("helvetica", "", 10)
        
        num_itens = len(q['itens'])
        for idx, item_resp in enumerate(respostas[q['numero']]):
            if is_vazia:
                resp_str = "[   ] SIM   [   ] PARC.   [   ] NÃO"
            else:
                resp_val = item_resp['resposta'].upper() if item_resp['resposta'] else "     "
                resp_str = f"[ {resp_val} ]"
                
            texto_item = f"- {item_resp['texto']} [{item_resp['pontos']} pts]   ->   {resp_str}"
            borda = "LR"
            if idx == num_itens - 1 and "pud" not in q: borda = "LBR"
                
            pdf.multi_cell(0, 6, text=texto_item, border=borda, fill=True, new_x="LMARGIN", new_y="NEXT")
        
        if "pud" in q:
            pdf.set_font("helvetica", "I", 9)
            pdf.multi_cell(0, 6, text=q['pud'], border="LBR", fill=True, align="R", new_x="LMARGIN", new_y="NEXT")
        
        pdf.ln(4) 
        
    if pdf.get_y() > 245: pdf.add_page()
    pdf.ln(15)
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(0, 10, "_"*60, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, "INSTRUTOR(a)", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "", 10)
    pdf.cell(0, 5, tutor_str, align="C", new_x="LMARGIN", new_y="NEXT")
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        pdf.output(tmp.name)
        tmp_path = tmp.name
        
    with open(tmp_path, "rb") as f:
        pdf_bytes = f.read()
    os.unlink(tmp_path) 
    return pdf_bytes

@st.dialog("⚠️ Atenção: Itens não avaliados")
def modal_confirmacao_fai(missing_items, pdf_bytes, file_name):
    st.write("Os seguintes itens ficaram em branco e terão **nota zero** contabilizada:")
    for item in missing_items:
        st.markdown(f"- {item}")
    st.write("Deseja gerar a ficha assim mesmo?")
    st.download_button(label="✅ Estou ciente, Baixar PDF", data=pdf_bytes, file_name=file_name, mime="application/pdf", type="primary")
    st.info("🔗 [Assinar digitalmente no gov.br](https://assinador.iti.br/)", icon="✍️")

def show_success_download(pdf_bytes, file_name, nota_final, is_vazia):
    if is_vazia:
        st.success("Ficha avaliativa vazia pronta para impressão.")
    else:
        st.success(f"Ficha avaliativa preenchida gerada! Nota calculada: {nota_final:.2f} pontos.")
    col_down, col_link = st.columns([1, 2])
    with col_down:
        st.download_button(label="📥 Baixar PDF", data=pdf_bytes, file_name=file_name, mime="application/pdf")
    with col_link:
        st.info("🔗 [Assinar digitalmente no gov.br](https://assinador.iti.br/)", icon="✍️")


# ==========================================
# PAINEL DO COORDENADOR (CONSTRUTOR E EDITOR)
# ==========================================
if st.session_state.admin_auth:
    st.title("🛠️ Painel do Coordenador")
    
    acao_admin = st.radio("Selecione a Ação:", ["🌟 Criar Nova FAI do Zero", "✏️ Editar FAI Existente"], horizontal=True)
    
    if acao_admin == "✏️ Editar FAI Existente":
        curso_editar = st.selectbox("Escolha o curso para carregar os dados:", cursos_disponiveis)
        if st.button("📥 Carregar Dados para Edição", type="primary"):
            limpar_memoria_admin()
            
            cfg_path = CURSOS_DIR / curso_editar / "fai_config.json"
            with open(cfg_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            
            st.session_state['sigla_pasta'] = curso_editar
            st.session_state['nome_cabecalho'] = cfg['cabecalho'].get('curso', '')
            st.session_state['titulo'] = cfg['cabecalho'].get('titulo', '')
            st.session_state['subtitulo'] = cfg['cabecalho'].get('subtitulo', '')
            st.session_state['instrucoes'] = cfg.get('instrucoes', '')
            
            st.session_state['num_questoes'] = len(cfg.get('questoes', []))
            for i, q in enumerate(cfg.get('questoes', []), 1):
                st.session_state[f"enunciado_{i}"] = q.get('enunciado', '')
                st.session_state[f"pud_{i}"] = q.get('pud', '')
                st.session_state[f"num_itens_q{i}"] = len(q.get('itens', []))
                for j, item in enumerate(q.get('itens', []), 1):
                    st.session_state[f"texto_{i}_{j}"] = item.get('texto', '')
                    st.session_state[f"pontos_{i}_{j}"] = float(item.get('pontos', 0.0))
            
            st.success(f"Dados do {curso_editar} carregados com sucesso! Role para baixo para editar.")
            
    st.divider()
    st.write("### Construtor Visual")
    
    col_sigla, col_curso = st.columns(2)
    with col_sigla:
        sigla = st.text_input("Sigla do Curso (Ex: TOP045) - Sem espaços", key="sigla_pasta").upper()
    with col_curso:
        st.text_input("Turma no Cabeçalho (Ex: Curso TOP045 1/2026)", key="nome_cabecalho")
        
    st.text_input("Título Principal", value="Ficha de Avaliação Individual", key="titulo")
    st.text_input("Subtítulo (Nome extenso do curso)", key="subtitulo")
    st.text_area("Instruções e Ambiente", height=150, key="instrucoes")
    
    st.divider()
    st.subheader("Questões da Avaliação")
    
    if "num_questoes" not in st.session_state or st.session_state.num_questoes == 0:
        st.session_state.num_questoes = 1

    questoes_config = []
    
    for q_idx in range(1, st.session_state.num_questoes + 1):
        with st.container(border=True):
            st.markdown(f"#### Questão {q_idx}")
            enunciado = st.text_area("Enunciado da Questão", key=f"enunciado_{q_idx}")
            pud = st.text_input("Item PUD (Opcional - Ex: Item PUD: 1.2.1.b)", key=f"pud_{q_idx}")
            
            if f"num_itens_q{q_idx}" not in st.session_state:
                st.session_state[f"num_itens_q{q_idx}"] = 1
            
            itens_da_questao = []
            st.write("**Itens Avaliativos:**")
            for i_idx in range(1, st.session_state[f"num_itens_q{q_idx}"] + 1):
                c1, c2 = st.columns([4, 1])
                with c1:
                    texto = st.text_input(f"Texto do Item {q_idx}.{i_idx}", key=f"texto_{q_idx}_{i_idx}")
                with c2:
                    pontos = st.number_input(f"Pontos", min_value=0.0, step=0.05, format="%.3f", key=f"pontos_{q_idx}_{i_idx}")
                
                if texto:
                    itens_da_questao.append({"texto": texto, "pontos": pontos})
            
            if st.button(f"➕ Adicionar Item na Questão {q_idx}"):
                st.session_state[f"num_itens_q{q_idx}"] += 1
                st.rerun()
            
            if enunciado:
                q_dict = {"numero": str(q_idx), "enunciado": enunciado, "itens": itens_da_questao}
                if pud: q_dict["pud"] = pud
                questoes_config.append(q_dict)

    if st.button("➕ Adicionar Nova Questão"):
        st.session_state.num_questoes += 1
        st.rerun()
        
    st.divider()
    
    curso_existe = sigla and sigla.upper() in [d.upper() for d in cursos_disponiveis]
    pode_salvar = True
    
    if acao_admin == "🌟 Criar Nova FAI do Zero" and curso_existe:
        st.error(f"🛑 BLOQUEADO: O curso **{sigla.upper()}** já existe. Para modificá-lo, selecione 'Editar FAI Existente' no topo da página.")
        pode_salvar = False
        
    if st.button("🚀 Publicar FAI no Sistema", type="primary", disabled=not pode_salvar):
        if not st.session_state.get('sigla_pasta') or not st.session_state.get('nome_cabecalho'):
            st.error("A Sigla do Curso e a Turma no Cabeçalho são obrigatórias!")
        else:
            json_final = {
                "cabecalho": {
                    "curso": st.session_state.get('nome_cabecalho'),
                    "titulo": st.session_state.get('titulo'),
                    "subtitulo": st.session_state.get('subtitulo')
                },
                "instrucoes": st.session_state.get('instrucoes'),
                "questoes": questoes_config
            }
            json_str = json.dumps(json_final, indent=2, ensure_ascii=False)
            
            with st.spinner("Conectando ao repositório e publicando..."):
                try:
                    from github import Github
                    g = Github(st.secrets["github_token"])
                    repo = g.get_repo(st.secrets["github_repo"])
                    sigla_pasta_final = st.session_state.get('sigla_pasta').upper()
                    caminho_arquivo = f"cursos/{sigla_pasta_final}/fai_config.json"
                    
                    try:
                        contents = repo.get_contents(caminho_arquivo)
                        repo.update_file(contents.path, f"Atualizando FAI {sigla_pasta_final} via Painel", json_str, contents.sha)
                        st.success(f"✅ FAI de {sigla_pasta_final} editada e salva com sucesso! O portal atualizará em breve.")
                    except:
                        repo.create_file(caminho_arquivo, f"Criando FAI {sigla_pasta_final} via Painel", json_str)
                        st.success(f"✅ Nova FAI de {sigla_pasta_final} criada com sucesso! O portal atualizará em breve.")
                except Exception as e:
                    st.error(f"Erro ao publicar: Verifique o Token do Github e a conexão. Detalhes: {e}")
                    
    st.stop()


# ==========================================
# INTERFACE PADRÃO (PREENCHIMENTO DA FAI)
# ==========================================

if not st.session_state.curso_selector:
    st.title("FAI ONLINE DIGITAL - CURSOS TOP")
    st.info("👈 Selecione ao lado o curso desejado para iniciar o preenchimento da Ficha de Avaliação Individual.")
    st.stop()

config_path = CURSOS_DIR / st.session_state.curso_selector / "fai_config.json"
with open(config_path, 'r', encoding='utf-8') as f:
    config = json.load(f)

st.title(config['cabecalho'].get('titulo',''))
st.subheader(f"{config['cabecalho'].get('curso','')} - {config['cabecalho'].get('subtitulo','')}")

if config.get("instrucoes"):
    with st.expander("Instruções e Ambiente", expanded=True):
        st.write(config['instrucoes'])

st.divider()
col1, col2 = st.columns(2)
with col1:
    aluno = st.text_input("Nome do Aluno")
with col2:
    tutor = st.text_input("Nome do Tutor / Instrutor")

st.divider()
respostas = {}

if config.get('questoes'):
    with st.form("fai_form"):
        for q in config['questoes']:
            st.markdown(f"**{q['enunciado']}**")
            respostas[q['numero']] = []
            
            for i, item in enumerate(q['itens']):
                col_item, col_resp = st.columns([3, 1])
                with col_item:
                    st.write(f"{item['texto']} **({item['pontos']} pts)**")
                with col_resp:
                    resp = st.radio(
                        f"Avaliação {q['numero']}.{i}",
                        options=["Sim", "Parcialmente", "Não"],
                        horizontal=True,
                        label_visibility="collapsed",
                        key=f"q_{q['numero']}_item_{i}",
                        index=None 
                    )
                    respostas[q['numero']].append({"texto": item['texto'], "pontos": item['pontos'], "resposta": resp})
            
            if "pud" in q:
                st.caption(f"_{q['pud']}_")
            st.write("---")
        
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            submitted_preenchida = st.form_submit_button("✅ Gerar FAI Preenchida")
        with col_btn2:
            submitted_vazia = st.form_submit_button("🖨️ Gerar FAI Vazia (Para Impressão)")

    if submitted_preenchida or submitted_vazia:
        nota_final = 0.0
        missing_items = []
        
        if submitted_preenchida:
            for q in config['questoes']:
                for idx, item_resp in enumerate(respostas[q['numero']]):
                    if item_resp['resposta'] is None:
                        missing_items.append(f"**Questão {q['numero']}** - {item_resp['texto']}")
                    elif item_resp['resposta'] == "Sim":
                        nota_final += item_resp['pontos']
                    elif item_resp['resposta'] == "Parcialmente":
                        nota_final += item_resp['pontos'] / 2.0
                        
            nome_arq_aluno = aluno.replace(' ', '_') if aluno else "PREENCHIDA"
            file_name = f"{st.session_state.curso_selector}_FAI_{nome_arq_aluno}.pdf"
            
            pdf_bytes = gerar_arquivo_pdf(config, respostas, aluno, tutor, nota_final, is_vazia=False)
            
            if missing_items:
                modal_confirmacao_fai(missing_items, pdf_bytes, file_name)
            else:
                show_success_download(pdf_bytes, file_name, nota_final, is_vazia=False)
                
        else:
            file_name = f"{st.session_state.curso_selector}_FAI_IMPRESSAO.pdf"
            pdf_bytes = gerar_arquivo_pdf(config, respostas, aluno, tutor, nota_final, is_vazia=True)
            show_success_download(pdf_bytes, file_name, nota_final, is_vazia=True)
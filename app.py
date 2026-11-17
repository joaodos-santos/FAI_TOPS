import streamlit as st
import json
import tempfile
import os
from fpdf import FPDF
from pathlib import Path

# Configuração inicial da página
st.set_page_config(page_title="Gerador de FAI", layout="wide")

CURSOS_DIR = Path("cursos")
if not CURSOS_DIR.exists():
    CURSOS_DIR.mkdir()

cursos_disponiveis = [d.name for d in CURSOS_DIR.iterdir() if d.is_dir()]
cursos_disponiveis.sort()

st.sidebar.title("Navegação")
if not cursos_disponiveis:
    st.warning("Nenhum curso encontrado. Crie as pastas e adicione o fai_config.json.")
    st.stop()

# Ajuste 1: Adicionado index=None e placeholder para não selecionar o primeiro curso automaticamente
curso_selecionado = st.sidebar.selectbox(
    "Selecione a FAI do Curso:", 
    cursos_disponiveis,
    index=None,
    placeholder="Escolha um curso..."
)

# Ajuste 2: Tela Inicial de Boas-Vindas
if not curso_selecionado:
    st.title("FAI ONLINE DIGITAL CURSOS TOP")
    st.info("👈 Selecione ao lado o curso desejado para iniciar o preenchimento da Ficha de Avaliação Individual.")
    st.stop()

config_path = CURSOS_DIR / curso_selecionado / "fai_config.json"

with open(config_path, 'r', encoding='utf-8') as f:
    config = json.load(f)

# Classe do FPDF
class PDF(FPDF):
    def header(self):
        self.set_font("helvetica", "B", 14)
        self.cell(0, 8, config['cabecalho']['curso'], align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_font("helvetica", "B", 12)
        self.cell(0, 8, config['cabecalho']['titulo'], align="C", new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 8, config['cabecalho']['subtitulo'], align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(5)

# Função isolada para criar o arquivo PDF e devolver os bytes em memória
def gerar_arquivo_pdf(respostas, aluno, tutor, nota_final, is_vazia):
    pdf = PDF()
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
    
    if "instrucoes" in config:
        pdf.set_font("helvetica", "I", 9)
        pdf.multi_cell(0, 5, text=config['instrucoes'], new_x="LMARGIN", new_y="NEXT")
        pdf.ln(5)
    
    for q in config['questoes']:
        linhas_enunciado = max(1, len(q['enunciado']) // 90 + 1)
        altura_estimada = (linhas_enunciado * 7) + (len(q['itens']) * 6) + 12
        if "pud" in q:
            altura_estimada += 6
            
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
            if idx == num_itens - 1 and "pud" not in q:
                borda = "LBR"
                
            pdf.multi_cell(0, 6, text=texto_item, border=borda, fill=True, new_x="LMARGIN", new_y="NEXT")
        
        if "pud" in q:
            pdf.set_font("helvetica", "I", 9)
            pdf.multi_cell(0, 6, text=q['pud'], border="LBR", fill=True, align="R", new_x="LMARGIN", new_y="NEXT")
        
        pdf.ln(4) 
        
    if pdf.get_y() > 245:
        pdf.add_page()
        
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
def modal_confirmacao(missing_items, pdf_bytes, file_name):
    st.write("Os seguintes itens ficaram em branco e terão **nota zero** contabilizada:")
    for item in missing_items:
        st.markdown(f"- {item}")
    
    st.write("Deseja gerar a ficha assim mesmo?")
    
    st.download_button(
        label="✅ Estou ciente, Baixar PDF",
        data=pdf_bytes,
        file_name=file_name,
        mime="application/pdf",
        type="primary"
    )
    st.info("🔗 [Assinar digitalmente no gov.br](https://assinador.iti.br/)", icon="✍️")

def show_success_download(pdf_bytes, file_name, nota_final, is_vazia):
    if is_vazia:
        st.success("Ficha avaliativa vazia pronta para impressão.")
    else:
        st.success(f"Ficha avaliativa preenchida gerada! Nota calculada: {nota_final:.2f} pontos.")
        
    col_down, col_link = st.columns([1, 2])
    with col_down:
        st.download_button(
            label="📥 Baixar PDF",
            data=pdf_bytes,
            file_name=file_name,
            mime="application/pdf"
        )
    with col_link:
        st.info("🔗 [Assinar digitalmente no gov.br](https://assinador.iti.br/)", icon="✍️")

# ==========================================
# INTERFACE DA FAI SELECIONADA
# ==========================================

st.title(config['cabecalho']['titulo'])
st.subheader(f"{config['cabecalho']['curso']} - {config['cabecalho']['subtitulo']}")

if "instrucoes" in config:
    with st.expander("Instruções", expanded=True):
        st.write(config['instrucoes'])

st.divider()
col1, col2 = st.columns(2)
with col1:
    aluno = st.text_input("Nome do Aluno")
with col2:
    tutor = st.text_input("Nome do Tutor / Instrutor")

st.divider()

respostas = {}

# Se houver questões configuradas, desenha o formulário
if config['questoes']:
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
                    respostas[q['numero']].append({
                        "texto": item['texto'], 
                        "pontos": item['pontos'], 
                        "resposta": resp
                    })
            
            if "pud" in q:
                st.caption(f"_{q['pud']}_")
            st.write("---")
        
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            submitted_preenchida = st.form_submit_button("✅ Gerar FAI Preenchida")
        with col_btn2:
            submitted_vazia = st.form_submit_button("🖨️ Gerar FAI Vazia (Para Impressão)")

    # ==========================================
    # PROCESSAMENTO DE SUBMISSÃO
    # ==========================================
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
            file_name = f"{curso_selecionado}_FAI_{nome_arq_aluno}.pdf"
            
            pdf_bytes = gerar_arquivo_pdf(respostas, aluno, tutor, nota_final, is_vazia=False)
            
            if missing_items:
                modal_confirmacao(missing_items, pdf_bytes, file_name)
            else:
                show_success_download(pdf_bytes, file_name, nota_final, is_vazia=False)
                
        else:
            file_name = f"{curso_selecionado}_FAI_IMPRESSAO.pdf"
            pdf_bytes = gerar_arquivo_pdf(respostas, aluno, tutor, nota_final, is_vazia=True)
            show_success_download(pdf_bytes, file_name, nota_final, is_vazia=True)
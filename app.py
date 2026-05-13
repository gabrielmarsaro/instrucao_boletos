import streamlit as st
import pandas as pd
from supabase import create_client, Client
import unicodedata
from datetime import datetime
import io

# ==========================================
# CONFIGURAÇÃO DE PÁGINA E SUPABASE
# ==========================================
st.set_page_config(
    page_title="Kóre Cash | Hub de Recebíveis",
    page_icon="logo_kore.svg", # Puxa a sua logo para a aba do navegador
    layout="wide"
)

@st.cache_resource
def init_supabase() -> Client:
    # Substitua st.secrets se rodar localmente sem o secrets.toml
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_supabase()

# ==========================================
# FUNÇÕES AUXILIARES (CNAB & DADOS)
# ==========================================
def remove_acentos(texto):
    if pd.isna(texto): return ""
    texto = str(texto)
    nfkd = unicodedata.normalize('NFKD', texto)
    return u"".join([c for c in nfkd if not unicodedata.combining(c)]).upper()

def formata_alfa(texto, tamanho):
    texto_limpo = remove_acentos(texto)
    return texto_limpo[:tamanho].ljust(tamanho, ' ')

def formata_num(numero, tamanho):
    if pd.isna(numero): numero = 0
    num_str = str(numero).replace('.', '').replace(',', '').replace('-', '').replace('/', '')
    return num_str[-tamanho:].zfill(tamanho)

# ==========================================
# GERAÇÃO DOS SEGMENTOS CNAB 240 (BB)
# ==========================================
def formatar_convenio_bb(convenio, is_teste=False):
    """
    O BB exige a formatação exata de 20 posições para o convênio:
    9 posições convênio + 0014 + 2 posições carteira + 3 posições variação + 2 espaços (ou TS para teste)
    """
    conv_str = str(convenio['convenio']).zfill(9)
    cart_str = str(convenio['carteira']).zfill(2)
    var_str = str(convenio['variacao']).zfill(3)
    final = "TS" if is_teste else "  "
    return f"{conv_str}0014{cart_str}{var_str}{final}"

def gerar_header_arquivo(convenio):
    banco = "001"
    lote = "0000"
    registro = "0"
    brancos1 = " " * 9
    inscricao_tipo = "2" # 2 para CNPJ
    cnpj = formata_num(convenio['cnpj'], 14)
    # Chamada da nova formatação de convênio BB
    codigo_convenio = formatar_convenio_bb(convenio)
    agencia = formata_num(convenio['agencia'], 5)
    dv_agencia = formata_alfa(convenio['dv_agencia'], 1)
    conta = formata_num(convenio['conta'], 12)
    dv_conta = formata_alfa(convenio['dv_conta'], 1)
    dv_ag_conta = " "
    nome_empresa = formata_alfa(convenio['razao_social'], 30)
    nome_banco = formata_alfa("BANCO DO BRASIL S.A.", 30)
    brancos2 = " " * 10
    codigo_remessa = "1"
    data_geracao = datetime.now().strftime("%d%m%Y")
    hora_geracao = datetime.now().strftime("%H%M%S")
    nsa = formata_num(1, 6) # Número sequencial do arquivo
    versao_layout = "083"
    densidade = "00000"
    reservado_banco = " " * 20
    reservado_empresa = " " * 20
    brancos3 = " " * 29
    
    return f"{banco}{lote}{registro}{brancos1}{inscricao_tipo}{cnpj}{codigo_convenio}{agencia}{dv_agencia}{conta}{dv_conta}{dv_ag_conta}{nome_empresa}{nome_banco}{brancos2}{codigo_remessa}{data_geracao}{hora_geracao}{nsa}{versao_layout}{densidade}{reservado_banco}{reservado_empresa}{brancos3}"

def gerar_header_lote(convenio, num_lote):
    banco = "001"
    lote = formata_num(num_lote, 4)
    registro = "1"
    operacao = "R"
    servico = "01" # Cobrança
    forma_lancamento = "  "
    versao_layout = "042"
    brancos1 = " "
    inscricao_tipo = "2"
    cnpj = formata_num(convenio['cnpj'], 15)
    # Chamada da nova formatação de convênio BB
    codigo_convenio = formatar_convenio_bb(convenio)
    agencia = formata_num(convenio['agencia'], 5)
    dv_agencia = formata_alfa(convenio['dv_agencia'], 1)
    conta = formata_num(convenio['conta'], 12)
    dv_conta = formata_alfa(convenio['dv_conta'], 1)
    dv_ag_conta = " "
    nome_empresa = formata_alfa(convenio['razao_social'], 30)
    mensagem_1 = formata_alfa("", 40)
    mensagem_2 = formata_alfa("", 40)
    nsa = formata_num(1, 8)
    data_gravacao = datetime.now().strftime("%d%m%Y")
    data_credito = formata_num(0, 8)
    brancos2 = " " * 33
    
    return f"{banco}{lote}{registro}{operacao}{servico}{forma_lancamento}{versao_layout}{brancos1}{inscricao_tipo}{cnpj}{codigo_convenio}{agencia}{dv_agencia}{conta}{dv_conta}{dv_ag_conta}{nome_empresa}{mensagem_1}{mensagem_2}{nsa}{data_gravacao}{data_credito}{brancos2}"

def gerar_segmento_p(convenio, boleto, num_lote, num_registro, instrucao, nova_data=None):
    banco = "001"
    lote = formata_num(num_lote, 4)
    registro = "3"
    num_seq_registro = formata_num(num_registro, 5)
    segmento = "P"
    brancos1 = " "
    cod_movimento = formata_num(instrucao[:2], 2) 
    agencia = formata_num(convenio['agencia'], 5)
    dv_agencia = formata_alfa(convenio['dv_agencia'], 1)
    conta = formata_num(convenio['conta'], 12)
    dv_conta = formata_alfa(convenio['dv_conta'], 1)
    dv_ag_conta = " "
    nosso_numero = formata_alfa(boleto['nosso numero'], 20)
    cod_carteira = formata_num(convenio['carteira'], 1)
    forma_cadastramento = "1"
    tipo_documento = "1"
    emissao_boleto = "2"
    distribuicao = "2"
    num_documento = formata_alfa(boleto['nº documento'], 15)
    
    # LÓGICA CRÍTICA: Substituição da data de vencimento
    if cod_movimento == "06" and nova_data:
        vencimento = formata_num(nova_data.strftime('%d%m%Y'), 8)
    else:
        vencimento = formata_num(pd.to_datetime(boleto['vencimento líquido']).strftime('%d%m%Y'), 8)
        
    valor = formata_num(float(boleto['montante']) * 100, 15)
    agencia_cobradora = "00000"
    dv_ag_cobradora = " "
    especie_titulo = "02" # Duplicata Mercantil
    aceite = "N"
    data_emissao = datetime.now().strftime("%d%m%Y")
    juros = "1"
    data_juros = formata_num(0, 8)
    valor_juros = formata_num(0, 15)
    cod_desconto = "0"
    data_desconto = formata_num(0, 8)
    valor_desconto = formata_num(0, 15)
    valor_iof = formata_num(0, 15)
    valor_abatimento = formata_num(0, 15)
    uso_empresa = formata_alfa(boleto['cliente'], 25)
    
    if cod_movimento in ["45", "46"]:
        cod_protesto = "8" 
    else:
        cod_protesto = "3" 
        
    dias_protesto = "00"
    cod_baixa = "0"
    dias_baixa = "000"
    moeda = "00" 
    uso_bb = formata_num(0, 10)
    brancos2 = " "
    
    return f"{banco}{lote}{registro}{num_seq_registro}{segmento}{brancos1}{cod_movimento}{agencia}{dv_agencia}{conta}{dv_conta}{dv_ag_conta}{nosso_numero}{cod_carteira}{forma_cadastramento}{tipo_documento}{emissao_boleto}{distribuicao}{num_documento}{vencimento}{valor}{agencia_cobradora}{dv_ag_cobradora}{especie_titulo}{aceite}{data_emissao}{juros}{data_juros}{valor_juros}{cod_desconto}{data_desconto}{valor_desconto}{valor_iof}{valor_abatimento}{uso_empresa}{cod_protesto}{dias_protesto}{cod_baixa}{dias_baixa}{moeda}{uso_bb}{brancos2}"

def gerar_segmento_q(cliente_db, num_lote, num_registro, instrucao):
    banco = "001"
    lote = formata_num(num_lote, 4)
    registro = "3"
    num_seq_registro = formata_num(num_registro, 5)
    segmento = "Q"
    brancos1 = " "
    cod_movimento = formata_num(instrucao[:2], 2)
    
    cnpj_cpf_limpo = str(cliente_db['cnpj_cpf']).replace('.', '').replace('-', '').replace('/', '')
    tipo_inscricao = "2" if len(cnpj_cpf_limpo) > 11 else "1"
    inscricao = formata_num(cnpj_cpf_limpo, 15)
    
    nome = formata_alfa(cliente_db['nome'], 40)
    endereco = formata_alfa(cliente_db['endereco'], 40)
    bairro = formata_alfa(cliente_db['bairro'], 15)
    cep = formata_num(cliente_db['cep'], 8)
    cidade = formata_alfa(cliente_db['cidade'], 15)
    uf = formata_alfa(cliente_db['uf'], 2)
    
    tipo_avalista = "0"
    inscricao_avalista = formata_num(0, 15)
    nome_avalista = formata_alfa("", 40)
    banco_correspondente = "000"
    nosso_num_banco_corr = formata_alfa("", 20)
    
    # Lógica Crítica: Preenchimento do Agente Negativador (Posições 233 e 234)
    if cod_movimento in ["45", "46"]:
        uso_febraban = "10      " # 10 para Serasa
    else:
        uso_febraban = "        " # 8 espaços em branco
    
    return f"{banco}{lote}{registro}{num_seq_registro}{segmento}{brancos1}{cod_movimento}{tipo_inscricao}{inscricao}{nome}{endereco}{bairro}{cep}{cidade}{uf}{tipo_avalista}{inscricao_avalista}{nome_avalista}{banco_correspondente}{nosso_num_banco_corr}{uso_febraban}"

def gerar_segmento_r(num_lote, num_registro, instrucao, multa_percentual=0, data_multa=None, mensagem=""):
    banco = "001"
    lote = formata_num(num_lote, 4)
    registro = "3"
    num_seq_registro = formata_num(num_registro, 5)
    segmento = "R"
    brancos1 = " "
    cod_movimento = formata_num(instrucao[:2], 2)
    
    # Descontos 2 e 3 (Não utilizaremos agora, então preenchemos com zeros/vazio)
    cod_desc2 = "0"
    data_desc2 = formata_num(0, 8)
    val_desc2 = formata_num(0, 15)
    cod_desc3 = "0"
    data_desc3 = formata_num(0, 8)
    val_desc3 = formata_num(0, 15)
    
    # MULTA: Código 2 para Percentual
    if multa_percentual > 0:
        cod_multa = "2"
        # Data da multa: Se não informada, o BB aceita a data do vencimento
        dt_multa = formata_num(data_multa.strftime('%d%m%Y'), 8) if data_multa else formata_num(0, 8)
        val_multa = formata_num(float(multa_percentual) * 100, 15)
    else:
        cod_multa = "0"
        dt_multa = formata_num(0, 8)
        val_multa = formata_num(0, 15)
    
    info_sacado = formata_alfa("", 10)
    msg3 = formata_alfa(mensagem, 40) # Mensagem que sai no boleto
    msg4 = formata_alfa("", 40)
    brancos2 = " " * 20
    ocor_sacado = formata_num(0, 8)
    cod_banco_debito = formata_num(0, 3)
    cod_agencia_debito = formata_num(0, 5)
    dv_agencia_debito = " "
    conta_debito = formata_num(0, 12)
    dv_conta_debito = " "
    dv_ag_conta_debito = " "
    aviso_debito = "0"
    brancos3 = " " * 9

    return f"{banco}{lote}{registro}{num_seq_registro}{segmento}{brancos1}{cod_movimento}{cod_desc2}{data_desc2}{val_desc2}{cod_desc3}{data_desc3}{val_desc3}{cod_multa}{dt_multa}{val_multa}{info_sacado}{msg3}{msg4}{brancos2}{ocor_sacado}{cod_banco_debito}{cod_agencia_debito}{dv_agencia_debito}{conta_debito}{dv_conta_debito}{dv_ag_conta_debito}{aviso_debito}{brancos3}"

def gerar_trailer_lote(num_lote, total_registros):
    banco = "001"
    lote = formata_num(num_lote, 4)
    registro = "5"
    brancos1 = " " * 9
    qtd_registros = formata_num(total_registros, 6)
    qtd_cobranca_simples = formata_num(0, 6)
    valor_cobranca_simples = formata_num(0, 17)
    qtd_cobranca_vinculada = formata_num(0, 6)
    valor_cobranca_vinculada = formata_num(0, 17)
    qtd_cobranca_caucionada = formata_num(0, 6)
    valor_cobranca_caucionada = formata_num(0, 17)
    qtd_cobranca_descontada = formata_num(0, 6)
    valor_cobranca_descontada = formata_num(0, 17)
    num_aviso = formata_alfa("", 8)
    brancos2 = " " * 117
    
    return f"{banco}{lote}{registro}{brancos1}{qtd_registros}{qtd_cobranca_simples}{valor_cobranca_simples}{qtd_cobranca_vinculada}{valor_cobranca_vinculada}{qtd_cobranca_caucionada}{valor_cobranca_caucionada}{qtd_cobranca_descontada}{valor_cobranca_descontada}{num_aviso}{brancos2}"

def gerar_trailer_arquivo(total_lotes, total_registros):
    banco = "001"
    lote = "9999"
    registro = "9"
    brancos1 = " " * 9
    qtd_lotes = formata_num(total_lotes, 6)
    qtd_registros = formata_num(total_registros, 6)
    qtd_contas_concil = formata_num(0, 6)
    brancos2 = " " * 205
    
    return f"{banco}{lote}{registro}{brancos1}{qtd_lotes}{qtd_registros}{qtd_contas_concil}{brancos2}"

# ==========================================
# FLUXO DE AUTENTICAÇÃO E LAYOUT
# ==========================================
# CSS para esconder o menu, o rodapé e criar uma barra de topo institucional
    st.markdown("""
       <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        /* Cria uma barra azul no topo da página inteira */
        .stApp {
            border-top: 8px solid #003087; 
        }
        /* Ajusta o espaçamento dos botões */
        div.stButton > button {
            border-radius: 4px;
        }
    </style>
""", unsafe_allow_html=True)

if 'user' not in st.session_state:
    st.session_state.user = None

# 1. INICIALIZAÇÃO DO ESTADO (No topo, antes de tudo)
if 'login_error' not in st.session_state:
    st.session_state.login_error = False

if not st.session_state.user:
    st.write("")
    st.write("")
    st.write("")
    
    col_esq, col_login, col_dir = st.columns([1, 1.4, 1])
    
    with col_login:
        # LOGO E TÍTULO
        col_img_esq, col_img_centro, col_img_dir = st.columns([1, 2, 1])
        with col_img_centro:
            st.image("logo_kore.svg", use_container_width=True)
        
        st.markdown("<p style='text-align: center; color: #555555; font-size: 16px; margin-top: -25px; margin-bottom: 0px;'>Hub de Recebíveis e Integração Financeira</p>", unsafe_allow_html=True)
        st.markdown("<hr style='border: 1.5px solid #F9D616; width: 60%; margin: -5px auto 30px auto;'>", unsafe_allow_html=True)        
        
        # INPUTS
        email = st.text_input("E-mail corporativo", key="main_email")
        senha = st.text_input("Senha", type="password", key="main_password")
        
        st.write("") 

        # BOTÃO DE ACESSO
        if st.button("Acessar Sistema", type="primary", use_container_width=True):
            try:
                res = supabase.auth.sign_in_with_password({"email": email, "password": senha})
                st.session_state.user = res.user
                st.session_state.login_error = False
                st.rerun()
            except Exception as e:
                # ATIVA O MODO DE ERRO
                st.session_state.login_error = True
                # O st.rerun() aqui força o Streamlit a ler o código de novo e mostrar o botão
                st.rerun()

        # ÁREA DINÂMICA DE BOTÕES (REAGE AO ERRO)
        st.write("")
        
        if st.session_state.login_error:
            # MOSTRA MENSAGEM DE ERRO
            st.error("Utilizador ou senha incorretos.")
            
            # MOSTRA BOTÕES LADO A LADO SE HOUVER ERRO
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Criar Conta", use_container_width=True, key="btn_criar_erro"):
                    try:
                        supabase.auth.sign_up({"email": email, "password": senha})
                        st.success("Verifique o seu e-mail!")
                    except: st.error("Erro ao criar.")
            
            with c2:
                # O BOTÃO "ESQUECI A SENHA" APARECE AQUI
                if st.button("Esqueci a Senha 🔑", use_container_width=True, key="btn_forgot"):
                    if not email:
                        st.warning("Introduza o seu e-mail acima.")
                    else:
                        try:
                            supabase.auth.reset_password_for_email(email)
                            st.success("Link de recuperação enviado!")
                        except: st.error("Erro ao processar pedido.")
        
        else:
            # SE NÃO HOUVER ERRO, MOSTRA APENAS O CRIAR CONTA (CENTRALIZADO)
            if st.button("Criar Conta", use_container_width=True, key="btn_criar_normal"):
                try:
                    supabase.auth.sign_up({"email": email, "password": senha})
                    st.success("Solicitação enviada para o e-mail.")
                except: st.error("Erro ao processar.")

    st.stop()

# ==========================================
# MENU LATERAL (SIDEBAR) - SEMPRE VISÍVEL
# ==========================================
with st.sidebar:
    st.image("logo_kore.svg", use_container_width=True)
    st.markdown("<h3 style='text-align: center; color: #003087;'>Kóre Cash</h3>", unsafe_allow_html=True)
    st.divider()
    
    st.subheader("📥 Planilhas Modelo")
    st.write("Baixe os arquivos CSV no padrão correto (ANSI) para importação.")
    
    # Gerador do Template de Clientes
    df_template_cli = pd.DataFrame(columns=['cliente', 'cnpj', 'nome', 'endereco', 'bairro', 'cep', 'cidade', 'uf'])
    csv_template_cli = df_template_cli.to_csv(index=False, sep=';', encoding='windows-1252')
    st.download_button(
        label="👥 Baixar Modelo de Clientes",
        data=csv_template_cli,
        file_name="modelo_clientes_kore.csv",
        mime="text/csv",
        use_container_width=True
    )
    
    # Gerador do Template de Boletos
    df_template_bol = pd.DataFrame(columns=['nosso numero', 'nº documento', 'vencimento líquido', 'total corrigido', 'montante', 'cliente'])
    csv_template_bol = df_template_bol.to_csv(index=False, sep=';', encoding='windows-1252')
    st.download_button(
        label="📄 Baixar Modelo de Boletos",
        data=csv_template_bol,
        file_name="modelo_boletos_kore.csv",
        mime="text/csv",
        use_container_width=True
    )
    
    st.divider()
    
    # Bônus: Botão de Sair / Logout
    if st.button("Sair / Logout", use_container_width=True):
        st.session_state.user = None
        st.rerun()

# ==========================================
# INTERFACE PRINCIPAL (ABAS)
# ==========================================
st.title("Gerador de Remessa CNAB 240")

# Reordenando as abas e nomeando as variáveis de forma explícita
# A ordem aqui define como aparece na tela da esquerda para a direita
aba_remessa, aba_clientes, aba_convenios = st.tabs([
    "⚙️ Gerar Remessa", 
    "👥 Meus Clientes", 
    "🏦 Meus Convênios"
])

# ---- ABA: MEUS CONVÊNIOS ----
with aba_convenios:
    st.header("Gestão de Convênios Bancários")
    
    with st.expander("Cadastrar Novo Convênio"):
        with st.form("form_convenio"):
            c1, c2 = st.columns(2)
            cnpj_conv = c1.text_input("CNPJ da Empresa")
            razao_conv = c2.text_input("Razão Social")
            
            c3, c4, c5, c6 = st.columns(4)
            ag = c3.text_input("Agência")
            dv_ag = c4.text_input("DV Agência")
            cc = c5.text_input("Conta")
            dv_cc = c6.text_input("DV Conta")
            
            c7, c8, c9 = st.columns(3)
            conv = c7.text_input("Código do Convênio")
            cart = c8.text_input("Carteira")
            var = c9.text_input("Variação")
            
            submit_conv = st.form_submit_button("Salvar Convênio")
            if submit_conv:
                data = {
                    "user_id": st.session_state.user.id, "cnpj": cnpj_conv, "razao_social": razao_conv,
                    "agencia": ag, "dv_agencia": dv_ag, "conta": cc, "dv_conta": dv_cc,
                    "convenio": conv, "carteira": cart, "variacao": var
                }
                supabase.table("convenios").insert(data).execute()
                st.success("Convênio salvo!")
                st.rerun()

    st.subheader("Convênios Cadastrados")
    res_conv = supabase.table("convenios").select("*").execute()
    df_conv = pd.DataFrame(res_conv.data)
    if not df_conv.empty:
        st.dataframe(df_conv.drop(columns=['user_id', 'created_at']), use_container_width=True)
        
        st.write("Gerenciar Convênios")
        # Dicionário Invisível de UUIDs para Convênios
        dict_conv = {f"{row['razao_social']} (CC: {row['conta']})": row['id'] for idx, row in df_conv.iterrows()}
        conv_selecionado = st.selectbox("Selecione para excluir:", list(dict_conv.keys()))
        if st.button("Excluir Convênio Selecionado"):
            supabase.table("convenios").delete().eq("id", dict_conv[conv_selecionado]).execute()
            st.success("Convênio excluído!")
            st.rerun()
    else:
        st.info("Nenhum convênio cadastrado.")

# ---- ABA: MEUS CLIENTES ----
with aba_clientes:
    st.header("Base de Sacados (Clientes)")
    
    col_cad, col_imp = st.columns(2)
    
    with col_cad:
        with st.expander("Cadastrar Manualmente"):
            with st.form("form_cliente"):
                id_plan = st.text_input("Código Único do Cliente (Ex: CL-001)")
                doc = st.text_input("CNPJ/CPF")
                nome = st.text_input("Nome/Razão Social")
                end = st.text_input("Endereço")
                bairro = st.text_input("Bairro")
                c1, c2, c3 = st.columns(3)
                cep = c1.text_input("CEP")
                cidade = c2.text_input("Cidade")
                uf = c3.text_input("UF (Ex: SP)")
                
                if st.form_submit_button("Salvar Cliente"):
                    dados_cli = {
                        "user_id": st.session_state.user.id, "id_cliente_planilha": id_plan,
                        "cnpj_cpf": doc, "nome": nome, "endereco": end, "bairro": bairro,
                        "cep": cep, "cidade": cidade, "uf": uf
                    }
                    supabase.table("clientes").insert(dados_cli).execute()
                    st.success("Cliente salvo!")
                    st.rerun()
                    
    with col_imp:
        with st.expander("Importação em Lote (.csv)"):
            st.markdown("Baixe o template, preencha os dados no Excel, **salve como CSV (Separado por vírgulas)** e faça o upload.")
            
            # --- GERADOR DO TEMPLATE PARA DOWNLOAD (Em ANSI/windows-1252) ---
            df_template_cli = pd.DataFrame(columns=['cliente', 'cnpj', 'nome', 'endereco', 'bairro', 'cep', 'cidade', 'uf'])
            csv_template_cli = df_template_cli.to_csv(index=False, sep=';', encoding='windows-1252')
            
            st.download_button(
                label="⬇️ Baixar Template de Clientes",
                data=csv_template_cli,
                file_name="template_clientes_kore.csv",
                mime="text/csv",
                use_container_width=True
            )
            
            st.markdown("---")
            
            # --- UPLOAD DO ARQUIVO CSV ---
            arquivo_clientes = st.file_uploader("Subir arquivo CSV", type=["csv"], key="up_cli")
            
            if arquivo_clientes and st.button("Processar Importação"):
                try:
                    # Lê o CSV exigindo ponto e vírgula e formato ANSI
                    df_imp = pd.read_csv(arquivo_clientes, sep=';', encoding='windows-1252', dtype=str)
                    df_imp.columns = df_imp.columns.str.strip().str.lower()
                    
                    df_imp = df_imp.rename(columns={"cliente": "id_cliente_planilha", "cnpj": "cnpj_cpf"})
                    df_imp['user_id'] = st.session_state.user.id
                    
                    records = df_imp.to_dict(orient='records')
                    supabase.table("clientes").insert(records).execute()
                    
                    st.success(f"{len(records)} clientes importados com sucesso!")
                    st.rerun()
                except Exception as e:
                    st.error("Erro na leitura. Verifique se salvou como CSV separado por vírgulas (;).")
                    st.error(f"Detalhe técnico: {e}")

    st.subheader("Clientes Cadastrados")
    res_cli = supabase.table("clientes").select("*").execute()
    df_cli = pd.DataFrame(res_cli.data)
    
    if not df_cli.empty:
        st.dataframe(df_cli.drop(columns=['user_id', 'created_at']), use_container_width=True)
        
        st.write("Gerenciar Clientes")
        # Regra Crítica: Dicionário invisível para mapear exibição -> UUID
        dict_cli = {f"{row['nome']} ({row['id_cliente_planilha']})": row['id'] for idx, row in df_cli.iterrows()}
        
        c_edit, c_del = st.columns(2)
        with c_del:
            clientes_para_excluir = st.multiselect("Selecione clientes para excluir em lote:", list(dict_cli.keys()))
            if st.button("Excluir Selecionados", type="primary"):
                uuids_del = [dict_cli[c] for c in clientes_para_excluir]
                for uid in uuids_del:
                    supabase.table("clientes").delete().eq("id", uid).execute()
                st.success("Clientes excluídos!")
                st.rerun()
    else:
        st.info("Nenhum cliente cadastrado.")

# ---- ABA: GERAR REMESSA (O CORE) ----
if 'lotes' not in st.session_state:
    st.session_state.lotes = []

with aba_remessa:
    st.header("Processamento de Remessa")
    
    if df_conv.empty:
        st.warning("Cadastre um convênio na Aba 'Meus Convênios' antes de gerar remessas.")
    else:
        dict_conv_remessa = {f"{row['razao_social']} - Ag/Cc: {row['agencia']}/{row['conta']}": row for idx, row in df_conv.iterrows()}
        conv_escolhido = st.selectbox("Selecione o Convênio:", list(dict_conv_remessa.keys()))
        
        lista_instrucoes = [
            "01 - Entrada de títulos",
            "02 - Pedido de baixa",
            "04 - Concessão de Abatimento",
            "05 - Cancelamento de Abatimento",
            "06 - Alteração de Vencimento",
            "07 - Concessão de Desconto",
            "08 - Cancelamento de Desconto",
            "09 - Protestar",
            "10 - Cancela/Sustação da Instrução de protesto",
            "12 - Alterar Juros de Mora",
            "13 - Dispensar Juros de Mora",
            "14 - Cobrar Multa",
            "15 - Dispensar Multa",
            "16 - Ratificar dados da Concessão de Desconto",
            "19 - Altera Prazo Limite de Recebimento",
            "20 - Dispensar Prazo Limite de Recebimento",
            "21 - Altera do Número do Título dado pelo Beneficiário",
            "22 - Alteração do Número de Controle do Participante",
            "23 - Alteração de Nome e Endereço do Pagador",
            "30 - Recusa da Alegação do Sacado",
            "31 - Alteração de Outros Dados",
            "34 - Altera Data Para Concessão de Desconto",
            "40 - Alteração de modalidade",
            "45 - Inclusão de Negativação sem protesto",
            "46 - Exclusão de Negativação sem protesto",
            "47 - Alteração do Valor Nominal do Boleto"
        ]
        
        instrucao = st.selectbox("Instrução da Remessa:", lista_instrucoes)

        # --- NOVOS CAMPOS CONDICIONAIS (AJUSTE 2) ---
        col_input1, col_input2, col_input3 = st.columns(3)
        
        nova_data_vencimento = None
        if instrucao.startswith("06"):
            nova_data_vencimento = col_input1.date_input("Novo Vencimento:")

        # Campos para Segmento R (Multas e Mensagens)
        # O BB permite multa de no máximo 10% dependendo do contrato
        multa_perc = col_input2.number_input("Multa pós-vencimento (%)", min_value=0.0, max_value=10.0, step=0.1)
        msg_instrucao = col_input3.text_input("Mensagem (Segmento R)", max_chars=40)
        # --------------------------------------------

        st.markdown("Colunas exigidas na planilha: `nosso numero`, `nº documento`, `vencimento líquido`, `total corrigido`, `montante`, `cliente`")
        arquivo_boletos = st.file_uploader("Upload da Planilha de Boletos (.xlsx)", type=["xlsx", "xls"], key="up_bol")
        
        if arquivo_boletos:
            df_boletos = pd.read_excel(arquivo_boletos)
            st.dataframe(df_boletos.head(3))
            
            if st.button("Adicionar ao Lote"):
                # Agora incluímos 'multa' e 'mensagem' no dicionário que vai para o carrinho
                st.session_state.lotes.append({
                    "convenio": dict_conv_remessa[conv_escolhido],
                    "instrucao": instrucao,
                    "df": df_boletos,
                    "nova_data": nova_data_vencimento,
                    "multa": multa_perc,
                    "mensagem": msg_instrucao
                })
                st.success(f"Lote adicionado! (Multa: {multa_perc}% | Mensagem: {msg_instrucao if msg_instrucao else 'N/A'})")

        if st.session_state.lotes:
            st.subheader(f"Carrinho: {len(st.session_state.lotes)} lote(s) pronto(s)")
            if st.button("Limpar Carrinho"):
                st.session_state.lotes = []
                st.rerun()
                
            if st.button("🚀 Gerar Arquivo Remessa Final", type="primary"):
                if df_cli.empty:
                    st.error("Sua base de clientes está vazia. Cadastre na Aba 'Meus Clientes' para gerar os Segmentos Q.")
                    st.stop()
                
                linhas_arquivo = []
                total_lotes_arquivo = len(st.session_state.lotes)
                total_registros_arquivo = 0 
                
                clientes_map = df_cli.set_index('id_cliente_planilha').to_dict('index')
                
                for index_lote, lote in enumerate(st.session_state.lotes, start=1):
                    conv = lote['convenio']
                    df_bol = lote['df']
                    inst = lote['instrucao']
                    nova_data_lote = lote.get('nova_data') 
                    
                    if index_lote == 1:
                        linhas_arquivo.append(gerar_header_arquivo(conv))
                        total_registros_arquivo += 1
                        
                    linhas_arquivo.append(gerar_header_lote(conv, index_lote))
                    
                    qtd_registros_lote = 0
                    seq_registro_lote = 1 
                    
                    for idx, row_boleto in df_bol.iterrows():
                        codigo_cliente = str(row_boleto['cliente']).strip()
                        
                        if codigo_cliente not in clientes_map:
                            st.warning(f"Atenção: Cliente '{codigo_cliente}' não encontrado no Banco de Dados. Boleto {row_boleto['nosso numero']} pulado.")
                            continue
                            
                        dados_cliente_db = clientes_map[codigo_cliente]
                        
                        linhas_arquivo.append(gerar_segmento_p(conv, row_boleto, index_lote, seq_registro_lote, inst, nova_data_lote))
                        seq_registro_lote += 1
                        qtd_registros_lote += 1
                        
                        linhas_arquivo.append(gerar_segmento_q(dados_cliente_db, index_lote, seq_registro_lote, inst))
                        seq_registro_lote += 1
                        qtd_registros_lote += 1

                    # Resgata dados do Segmento R salvos no lote
                        perc_multa = lote.get('multa', 0)
                        msg_r = lote.get('mensagem', "")
                        
                        # Sempre geraremos o R se houver multa ou mensagem[cite: 1]
                        if perc_multa > 0 or msg_r != "":
                            # Usamos o vencimento do boleto como data base da multa
                            dt_venc = pd.to_datetime(row_boleto['vencimento líquido'])
                            
                            linhas_arquivo.append(gerar_segmento_r(index_lote, seq_registro_lote, inst, perc_multa, dt_venc, msg_r))
                            seq_registro_lote += 1
                            qtd_registros_lote += 1
                    
                    registros_total_lote_formatado = qtd_registros_lote + 2
                    linhas_arquivo.append(gerar_trailer_lote(index_lote, registros_total_lote_formatado))
                    total_registros_arquivo += registros_total_lote_formatado
                
                total_registros_arquivo += 1 
                linhas_arquivo.append(gerar_trailer_arquivo(total_lotes_arquivo, total_registros_arquivo))
                
                texto_remessa = "\r\n".join(linhas_arquivo) + "\r\n" 
                
                erros_tamanho = [i for i, linha in enumerate(linhas_arquivo) if len(linha) != 240]
                if erros_tamanho:
                    st.error(f"Erro Crítico de Layout: As linhas {erros_tamanho} não possuem 240 posições exatas. Revise as funções de formatação.")
                else:
                    st.success("Remessa processada com sucesso!")
                    
                    # O windows-1252 garante o padrão ANSI / 1 byte por caractere exigido pela Febraban/BB
                    buffer = io.BytesIO(texto_remessa.encode('windows-1252')) 
                    st.download_button(
                        label="⬇️ Baixar Arquivo .REM",
                        data=buffer,
                        file_name=f"CB{datetime.now().strftime('%d%m')}.REM", 
                        mime="text/plain"
                    )

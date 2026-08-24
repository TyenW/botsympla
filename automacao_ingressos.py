import pandas as pd
from playwright.sync_api import sync_playwright
import time
import os
import shutil
import pypdf
import threading

# Importações para a interface gráfica moderna
import tkinter as tk
from tkinter import messagebox, filedialog
import customtkinter as ctk

# =========================================================
# CONFIGURAÇÕES PADRÃO (VALORES INICIAIS DA INTERFACE)
# =========================================================
DIRETORIO_SCRIPT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CSV = os.path.join(DIRETORIO_SCRIPT, 'lista_participantes.csv')
DEFAULT_EMAIL = "email_padrao@dominio.com.br"
DEFAULT_QUANTIDADE = "1"
DEFAULT_URL = ""
PASTA_DOWNLOADS = os.path.join(DIRETORIO_SCRIPT, 'Ingressos_Salvos')
PASTA_PERFIL = os.path.join(DIRETORIO_SCRIPT, 'Perfil_Navegador')

def formatar_url_evento(entrada):
    """Formatador inteligente: aceita tanto o ID numérico do evento quanto a URL completa do Sympla."""
    entrada = entrada.strip()
    if not entrada:
        return ""
    if entrada.isdigit():
        return f"https://organizador.sympla.com.br/participantes-administrar?id={entrada}"
    if entrada.lower().startswith("id=") or entrada.lower().startswith("?id="):
        id_num = entrada.split("=")[-1].strip()
        return f"https://organizador.sympla.com.br/participantes-administrar?id={id_num}"
    if entrada.lower().startswith("http://") or entrada.lower().startswith("https://"):
        return entrada
    if "sympla.com.br" in entrada.lower():
        return f"https://{entrada}"
    return f"https://organizador.sympla.com.br/participantes-administrar?id={entrada}"

def criar_contexto_chrome(p, caminho_perfil):
    """Cria um contexto persistente do Chrome sem nenhuma flag suspeita para evitar o bloqueio de segurança do Cloudflare e do Google"""
    context = p.chromium.launch_persistent_context(
        user_data_dir=caminho_perfil,
        headless=False,
        channel="chrome",
        accept_downloads=True,
        no_viewport=True,
        ignore_default_args=["--enable-automation"],
        args=[
            "--disable-blink-features=AutomationControlled",
            "--disable-popup-blocking",
            "--start-maximized"
        ]
    )
    try:
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
    except Exception:
        pass

    def auto_desbloquear_popup(nova_pagina):
        try:
            if nova_pagina.url and nova_pagina.url != "about:blank":
                nova_pagina.bring_to_front()
        except Exception:
            pass
    try:
        context.on("page", auto_desbloquear_popup)
    except Exception:
        pass
    return context

def navegar_seguro(page, url, timeout=15000):
    """Navega para a URL sem travar aguardando scripts de terceiros ou conexões pendentes do Sympla"""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=timeout)
    except Exception:
        try:
            page.goto(url, wait_until="commit", timeout=5000)
        except Exception:
            pass

if not os.path.exists(PASTA_DOWNLOADS):
    os.makedirs(PASTA_DOWNLOADS)

# Configuração visual padrão do CustomTkinter
ctk.set_appearance_mode("Dark")    # Tema Escuro Premium por padrão
ctk.set_default_color_theme("blue") # Cor de destaque padrão

# =========================================================
# CLASSE DA INTERFACE GRÁFICA PROFISSIONAL
# =========================================================
class AutomacaoApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Configurações de Janela
        self.title("Robô de Ingressos Sympla")
        self.geometry("860x620")
        self.minsize(820, 580)
        
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=4) # Coluna de configurações (mais larga)
        self.grid_columnconfigure(1, weight=3) # Coluna de controle e status

        # Inicializa arquivo de logs para esta sessão
        try:
            with open("automacao.log", "w", encoding="utf-8") as f_log:
                f_log.write("=== LOG DE AUTOMAÇÃO - SESSÃO INICIADA ===\n")
        except Exception:
            pass

        # 1. Cabeçalho Principal (Ocupa ambas as colunas)
        self.frame_header = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_header.grid(row=0, column=0, columnspan=2, padx=30, pady=(25, 10), sticky="ew")
        
        self.lbl_titulo = ctk.CTkLabel(
            self.frame_header, text="SYMPLA TICKET BOT", 
            font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold")
        )
        self.lbl_titulo.pack(anchor="w")
        
        self.lbl_subtitulo = ctk.CTkLabel(
            self.frame_header, text="Gerenciamento automático e emissão em lote de ingressos.", 
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color="#8A8A8A"
        )
        self.lbl_subtitulo.pack(anchor="w", pady=(2, 0))

        # 2. Painel de Configurações (Esquerda)
        self.frame_config = ctk.CTkFrame(self)
        self.frame_config.grid(row=1, column=0, padx=(30, 15), pady=(10, 30), sticky="nsew")
        self.frame_config.grid_columnconfigure(0, weight=1)

        self.lbl_config_title = ctk.CTkLabel(
            self.frame_config, text="Configurações do Evento",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold")
        )
        self.lbl_config_title.grid(row=0, column=0, padx=20, pady=(15, 10), sticky="w")

        # 1. URL ou ID do Evento
        self.lbl_url = ctk.CTkLabel(self.frame_config, text="URL OU ID DO EVENTO SYMPLA", font=ctk.CTkFont(size=11, weight="bold"), text_color="#A0A0A0")
        self.lbl_url.grid(row=1, column=0, padx=20, pady=(10, 2), sticky="w")
        
        self.frame_url_field = ctk.CTkFrame(self.frame_config, fg_color="transparent")
        self.frame_url_field.grid(row=2, column=0, padx=20, pady=(0, 10), sticky="ew")
        self.frame_url_field.grid_columnconfigure(0, weight=1)

        self.entry_url = ctk.CTkEntry(
            self.frame_url_field, 
            height=32,
            placeholder_text="Digite o ID (ex: 3545453) ou a URL completa"
        )
        self.entry_url.insert(0, DEFAULT_URL)
        self.entry_url.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        self.btn_detectar_url = ctk.CTkButton(
            self.frame_url_field, text="Detectar", width=105, height=32,
            fg_color="#0284C7", hover_color="#0369A1",
            command=self.iniciar_detecao_sympla
        )
        self.btn_detectar_url.grid(row=0, column=1, sticky="e")

        # 2. Perfil de Navegador Chrome (Garante suporte a múltiplas contas)
        self.lbl_perfil = ctk.CTkLabel(self.frame_config, text="PERFIL DO NAVEGADOR CHROME (CONTA)", font=ctk.CTkFont(size=11, weight="bold"), text_color="#A0A0A0")
        self.lbl_perfil.grid(row=3, column=0, padx=20, pady=(5, 2), sticky="w")

        self.frame_perfil_field = ctk.CTkFrame(self.frame_config, fg_color="transparent")
        self.frame_perfil_field.grid(row=4, column=0, padx=20, pady=(0, 10), sticky="ew")
        self.frame_perfil_field.grid_columnconfigure(0, weight=1)

        perfis_iniciais = self.listar_perfis_disponiveis()
        self.combo_perfil = ctk.CTkComboBox(
            self.frame_perfil_field,
            values=perfis_iniciais,
            height=32
        )
        self.combo_perfil.set(perfis_iniciais[0] if perfis_iniciais else "Perfil_Navegador")
        self.combo_perfil.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        self.btn_login_perfil = ctk.CTkButton(
            self.frame_perfil_field, text="Fazer Login", width=105, height=32,
            fg_color="#D97706", hover_color="#B45309",
            command=self.iniciar_login_sympla
        )
        self.btn_login_perfil.grid(row=0, column=1, sticky="e")

        # 3. Email Padrão
        self.lbl_email = ctk.CTkLabel(self.frame_config, text="E-MAIL DE REGISTRO DOS INGRESSOS", font=ctk.CTkFont(size=11, weight="bold"), text_color="#A0A0A0")
        self.lbl_email.grid(row=5, column=0, padx=20, pady=(5, 2), sticky="w")
        self.entry_email = ctk.CTkEntry(self.frame_config, height=32)
        self.entry_email.insert(0, DEFAULT_EMAIL)
        self.entry_email.grid(row=6, column=0, padx=20, pady=(0, 10), sticky="ew")

        # 4. Quantidade de Ingressos
        self.lbl_quantidade = ctk.CTkLabel(self.frame_config, text="QUANTIDADE DE INGRESSOS POR PARTICIPANTE", font=ctk.CTkFont(size=11, weight="bold"), text_color="#A0A0A0")
        self.lbl_quantidade.grid(row=7, column=0, padx=20, pady=(5, 2), sticky="w")
        self.entry_quantidade = ctk.CTkEntry(self.frame_config, height=32)
        self.entry_quantidade.insert(0, DEFAULT_QUANTIDADE)
        self.entry_quantidade.grid(row=8, column=0, padx=20, pady=(0, 10), sticky="ew")

        # 5. Arquivo CSV
        self.lbl_csv = ctk.CTkLabel(self.frame_config, text="ARQUIVO CSV DE PARTICIPANTES", font=ctk.CTkFont(size=11, weight="bold"), text_color="#A0A0A0")
        self.lbl_csv.grid(row=9, column=0, padx=20, pady=(5, 2), sticky="w")
        
        self.frame_csv_field = ctk.CTkFrame(self.frame_config, fg_color="transparent")
        self.frame_csv_field.grid(row=10, column=0, padx=20, pady=(0, 15), sticky="ew")
        self.frame_csv_field.grid_columnconfigure(0, weight=1)
        
        # Combobox para listar CSVs da pasta e permitir seleção ou caminho personalizado
        csvs_iniciais = self.listar_csvs_disponiveis()
        self.combo_csv = ctk.CTkComboBox(
            self.frame_csv_field,
            values=csvs_iniciais if csvs_iniciais else ["lista_participantes.csv"],
            command=self.on_csv_combo_select,
            height=32
        )
        valor_padrao = DEFAULT_CSV if os.path.exists(DEFAULT_CSV) else (os.path.join(DIRETORIO_SCRIPT, csvs_iniciais[0]) if csvs_iniciais else DEFAULT_CSV)
        self.combo_csv.set(valor_padrao)
        self.combo_csv.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        
        self.btn_csv = ctk.CTkButton(self.frame_csv_field, text="Procurar...", width=105, height=32, command=self.selecionar_csv)
        self.btn_csv.grid(row=0, column=1, sticky="e")

        # Atualiza o rótulo com a quantidade exata de arquivos CSV encontrados
        self.atualizar_lista_csv()

        # 3. Painel de Controle e Status (Direita)
        self.frame_painel = ctk.CTkFrame(self)
        self.frame_painel.grid(row=1, column=1, padx=(15, 30), pady=(10, 30), sticky="nsew")
        self.frame_painel.grid_columnconfigure(0, weight=1)

        self.lbl_painel_title = ctk.CTkLabel(
            self.frame_painel, text="Painel de Controle",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold")
        )
        self.lbl_painel_title.grid(row=0, column=0, padx=20, pady=(15, 10), sticky="w")

        # Cartão de Status do Processo
        self.card_status = ctk.CTkFrame(self.frame_painel, fg_color="#1E1E2F", border_width=1, border_color="#334155")
        self.card_status.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        self.card_status.grid_columnconfigure(0, weight=1)

        # Badge e Texto de Status Geral
        self.frame_badge_row = ctk.CTkFrame(self.card_status, fg_color="transparent")
        self.frame_badge_row.grid(row=0, column=0, padx=15, pady=(15, 5), sticky="w")

        self.badge_status = ctk.CTkLabel(
            self.frame_badge_row, text=" PRONTO ",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#A3A3A3",
            fg_color="#2E2E2E",
            corner_radius=12
        )
        self.badge_status.pack(side="left")

        self.lbl_status_geral = ctk.CTkLabel(
            self.frame_badge_row, text="Pronto para iniciar",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold")
        )
        self.lbl_status_geral.pack(side="left", padx=10)

        # Progresso Estatístico
        self.lbl_progresso = ctk.CTkLabel(
            self.card_status, text="Nenhum processo ativo", 
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#8A8A8A"
        )
        self.lbl_progresso.grid(row=1, column=0, padx=15, pady=(5, 5), sticky="w")

        # Barra de Progresso Customizada
        self.barra_progresso = ctk.CTkProgressBar(self.card_status, height=8, progress_color="#3D5A80")
        self.barra_progresso.grid(row=2, column=0, padx=15, pady=(2, 15), sticky="ew")
        self.barra_progresso.set(0)

        # Status Detalhado (Última ação / Log curto)
        self.frame_details = ctk.CTkFrame(self.frame_painel, fg_color="transparent")
        self.frame_details.grid(row=2, column=0, padx=20, pady=(5, 10), sticky="ew")
        
        self.lbl_status_detalhes_titulo = ctk.CTkLabel(
            self.frame_details, text="ÚLTIMA AÇÃO REGISTRADA:", 
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#64748B"
        )
        self.lbl_status_detalhes_titulo.pack(anchor="w")
        
        self.lbl_status_detalhes = ctk.CTkLabel(
            self.frame_details, text="Aguardando comando...", 
            font=ctk.CTkFont(family="Segoe UI", size=11, slant="italic"),
            text_color="#94A3B8"
        )
        self.lbl_status_detalhes.pack(anchor="w")

        # Botões de Ação
        self.frame_actions = ctk.CTkFrame(self.frame_painel, fg_color="transparent")
        self.frame_actions.grid(row=3, column=0, padx=20, pady=(15, 20), sticky="ew")
        self.frame_actions.grid_columnconfigure(0, weight=1)

        self.btn_rodar = ctk.CTkButton(
            self.frame_actions, text="INICIAR AUTOMAÇÃO", 
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            height=44, fg_color="#1E3A8A", hover_color="#1D4ED8",
            command=self.iniciar_automacao
        )
        self.btn_rodar.grid(row=0, column=0, pady=(0, 10), sticky="ew")

        self.btn_organizar = ctk.CTkButton(
            self.frame_actions, text="ORGANIZAR INGRESSOS", 
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            height=44, fg_color="#065F46", hover_color="#047857",
            command=self.iniciar_organizacao
        )
        self.btn_organizar.grid(row=1, column=0, sticky="ew")

    # =========================================================
    # FUNÇÕES DE PERFIL E DETECÇÃO DE CONTAS/EVENTOS SYMPLA
    # =========================================================
    def listar_perfis_disponiveis(self):
        """Retorna os nomes das pastas de perfil do Chrome encontradas no diretório do script"""
        perfis = []
        try:
            if os.path.exists(DIRETORIO_SCRIPT):
                for item in os.listdir(DIRETORIO_SCRIPT):
                    caminho = os.path.join(DIRETORIO_SCRIPT, item)
                    if os.path.isdir(caminho) and (item.startswith("Perfil_") or item.startswith("perfil_")):
                        perfis.append(item)
        except Exception:
            pass
        if "Perfil_Navegador" not in perfis:
            perfis.insert(0, "Perfil_Navegador")
        return sorted(list(set(perfis)))

    def obter_caminho_perfil(self):
        """Retorna o caminho absoluto da pasta de perfil selecionada no Combobox"""
        nome_perfil = self.combo_perfil.get().strip() if hasattr(self, "combo_perfil") else "Perfil_Navegador"
        if not nome_perfil:
            nome_perfil = "Perfil_Navegador"
        caminho = os.path.join(DIRETORIO_SCRIPT, nome_perfil)
        if not os.path.exists(caminho):
            os.makedirs(caminho, exist_ok=True)
        return caminho

    def aguardar_autenticacao_ou_confirmacao(self, context, page, mensagem_status, selector_esperado=None, timeout_max=300):
        """
        Aguarda a autenticação do usuário no Chrome de forma fluida e não-bloqueante.
        Monitora em tempo real se o usuário concluiu o login no navegador ou se clicou no botão de confirmação.
        """
        self.definir_status("automacao", mensagem_status)
        self.log(f"{mensagem_status} (Você pode interagir normalmente no Chrome).")

        confirmado = threading.Event()
        top_ref = [None]

        def criar_painel_flutuante():
            try:
                top = ctk.CTkToplevel(self)
                top.title("Aguardando Entrada no Sympla")
                top.geometry("460x190")
                top.resizable(False, False)
                top.attributes("-topmost", True)
                top_ref[0] = top

                lbl_info = ctk.CTkLabel(
                    top,
                    text="O Chrome foi aberto para você realizar o login.\n\n"
                         "Por favor, faça o login na sua conta do Sympla no Chrome.\n"
                         "Esta janela fechará automaticamente assim que o login for detectado.",
                    font=ctk.CTkFont(family="Segoe UI", size=12),
                    wraplength=420
                )
                lbl_info.pack(padx=20, pady=(20, 15))

                btn_confirmar = ctk.CTkButton(
                    top,
                    text="Já concluí o Login no Chrome",
                    fg_color="#059669", hover_color="#047857",
                    font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                    height=36,
                    command=lambda: (confirmado.set(), top.destroy() if top.winfo_exists() else None)
                )
                btn_confirmar.pack(padx=20, pady=(0, 15))

                def fechar_manual():
                    confirmado.set()
                    if top.winfo_exists():
                        top.destroy()
                top.protocol("WM_DELETE_WINDOW", fechar_manual)
            except Exception:
                confirmado.set()

        self.after(0, criar_painel_flutuante)

        inicio = time.time()
        while time.time() - inicio < timeout_max:
            if confirmado.is_set():
                break

            try:
                # 1. Caso seletor específico seja esperado (ex: botão 'Adicionar Pedido')
                if selector_esperado and page.locator(selector_esperado).is_visible():
                    self.log("✅ Elemento de evento detectado com sucesso no Chrome!")
                    confirmado.set()
                    break

                # 2. Detecção genérica de login no Sympla (apenas na área do organizador e com seletores estritos de usuário logado)
                url_atual = page.url.lower()
                if "organizador.sympla.com.br" in url_atual and "login" not in url_atual:
                    if any(p_path in url_atual for p_path in ["/eventos", "/painel", "participantes-administrar"]):
                        self.log("✅ Login no Sympla detectado automaticamente!")
                        confirmado.set()
                        break
                    if page.locator("a.btn-primary:has-text('Adicionar Pedido'), .user-name, .profile-name, .organizer-name, .header-user-name, a[href*='logout'], a[href*='sair']").first.is_visible():
                        self.log("✅ Login no Sympla detectado automaticamente!")
                        confirmado.set()
            except Exception:
                pass

            try:
                page.wait_for_timeout(300)
            except Exception:
                time.sleep(0.3)

        def destruir_painel():
            if top_ref[0] and top_ref[0].winfo_exists():
                try:
                    top_ref[0].destroy()
                except Exception:
                    pass
        self.after(0, destruir_painel)

    def iniciar_login_sympla(self):
        self.alterar_estado_botoes("disabled")
        self.definir_status("automacao", "Aguardando login no Sympla...")
        self.log("Abrindo Chrome para realizar login no Sympla...")
        threading.Thread(target=self.abrir_navegador_para_login, daemon=True).start()

    def abrir_navegador_para_login(self):
        caminho_perfil = self.obter_caminho_perfil()
        nome_pasta_perfil = os.path.basename(caminho_perfil)
        try:
            with sync_playwright() as p:
                self.log(f"Abrindo Chrome para login (Perfil: {nome_pasta_perfil})...")
                context = criar_contexto_chrome(p, caminho_perfil)
                
                # Aba 1: Tela de Login no Sympla Organizador
                page_sympla = context.pages[0] if context.pages else context.new_page()
                navegar_seguro(page_sympla, "https://organizador.sympla.com.br/login")
                
                # Aba 2: Login no Google Accounts
                try:
                    page_google = context.new_page()
                    navegar_seguro(page_google, "https://accounts.google.com/")
                except Exception:
                    pass

                self.aguardar_autenticacao_ou_confirmacao(
                    context,
                    page_sympla,
                    f"Aguardando login no perfil '{nome_pasta_perfil}' pelo Chrome..."
                )
                
                context.close()
                self.log("Sessão de login salva com sucesso no perfil.")
                self.definir_status("concluido", "Login salvo com sucesso.")
        except Exception as e_log:
            self.log(f"Erro ao abrir navegador para login: {e_log}")
            self.definir_status("erro", "Erro ao realizar login.")
        finally:
            self.alterar_estado_botoes("normal")

    def iniciar_detecao_sympla(self):
        self.alterar_estado_botoes("disabled")
        self.definir_status("automacao", "Detectando contas e eventos no Sympla...")
        self.log("Conectando ao Chrome para detectar perfil logado e eventos no Sympla...")
        threading.Thread(target=self.detectar_perfis_eventos_sympla, daemon=True).start()

    def detectar_perfis_eventos_sympla(self):
        caminho_perfil = self.obter_caminho_perfil()
        nome_pasta_perfil = os.path.basename(caminho_perfil)
        
        try:
            with sync_playwright() as p:
                self.log(f"Abrindo Chrome (Perfil: {nome_pasta_perfil})...")
                context = criar_contexto_chrome(p, caminho_perfil)
                page = context.pages[0] if context.pages else context.new_page()

                self.log("Acessando painel do organizador Sympla...")
                navegar_seguro(page, "https://organizador.sympla.com.br/eventos")
                time.sleep(1.5)

                # Se estiver na página de login, solicita ao usuário para logar
                if "login" in page.url.lower() or page.locator("input[type='email'], input[name='email']").is_visible():
                    self.aguardar_autenticacao_ou_confirmacao(
                        context,
                        page,
                        f"Por favor, faça login na sua conta do Sympla no Chrome ({nome_pasta_perfil})."
                    )
                    navegar_seguro(page, "https://organizador.sympla.com.br/eventos")
                    time.sleep(1.5)

                conta_logada = "Conta Organizadora"
                try:
                    elem_conta = page.locator(".user-name, .profile-name, .organizer-name, .header-user-name, span.name, .user-info").first
                    if elem_conta.is_visible():
                        conta_logada = elem_conta.inner_text().strip()
                except Exception:
                    pass

                # Coleta eventos disponíveis na página
                eventos_encontrados = []
                ids_vistos = set()

                try:
                    anchors = page.locator("a[href*='id=']").all()
                    for a in anchors:
                        try:
                            href = a.get_attribute("href") or ""
                            texto = a.inner_text().strip()
                            if "id=" in href:
                                id_num = href.split("id=")[-1].split("&")[0].strip()
                                if id_num.isdigit() and id_num not in ids_vistos:
                                    ids_vistos.add(id_num)
                                    titulo = texto.split("\n")[0].strip() if texto else f"Evento {id_num}"
                                    if not titulo or len(titulo) < 2:
                                        titulo = f"Evento #{id_num}"
                                    eventos_encontrados.append({
                                        "id": id_num,
                                        "titulo": titulo,
                                        "url": f"https://organizador.sympla.com.br/participantes-administrar?id={id_num}"
                                    })
                        except Exception:
                            continue
                except Exception as e_scan:
                    self.log(f"Aviso ao escanear eventos: {e_scan}")

                context.close()

                if not eventos_encontrados:
                    self.log("Aviso: Nenhum evento foi localizado automaticamente nesta conta. Insira o ID manualmente.")
                    self.definir_status("idle")
                    self.exibir_alerta("Aviso", "Nenhum evento com ID numérico foi encontrado automaticamente. Insira o ID no campo.")
                elif len(eventos_encontrados) == 1:
                    ev = eventos_encontrados[0]
                    def atualizar_unico():
                        self.entry_url.delete(0, "end")
                        self.entry_url.insert(0, ev["id"])
                    self.after(0, atualizar_unico)
                    self.log(f"Evento detectado e selecionado: {ev['titulo']} (ID: {ev['id']})")
                    self.definir_status("concluido", "Evento detectado com sucesso.")
                else:
                    self.log(f"{len(eventos_encontrados)} eventos detectados na conta '{conta_logada}'. Exibindo seleção...")
                    self.after(0, lambda: self.exibir_janela_selecao_eventos(conta_logada, eventos_encontrados))
                    self.definir_status("idle")

        except Exception as e_det:
            self.log(f"Erro ao escanear conta/eventos Sympla: {e_det}")
            self.definir_status("erro", "Erro no escaneamento.")
        finally:
            self.alterar_estado_botoes("normal")

    def exibir_janela_selecao_eventos(self, conta_logada, lista_eventos):
        """Abre uma janela modal moderna para o usuário escolher o evento detectado"""
        top = ctk.CTkToplevel(self)
        top.title("Eventos Detectados no Sympla")
        top.geometry("520x400")
        top.grab_set()

        lbl_topo = ctk.CTkLabel(
            top, 
            text=f"Conta Detectada: {conta_logada}", 
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color="#38BDF8"
        )
        lbl_topo.pack(padx=20, pady=(15, 5), anchor="w")

        lbl_inst = ctk.CTkLabel(
            top, 
            text="Selecione abaixo o evento desejado para emitir os ingressos:", 
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#A0A0A0"
        )
        lbl_inst.pack(padx=20, pady=(0, 10), anchor="w")

        scroll_frame = ctk.CTkScrollableFrame(top, width=470, height=260)
        scroll_frame.pack(padx=20, pady=10, fill="both", expand=True)

        for ev in lista_eventos:
            id_ev = ev["id"]
            titulo_ev = ev["titulo"]

            btn_ev = ctk.CTkButton(
                scroll_frame,
                text=f"{titulo_ev} (ID: {id_ev})",
                anchor="w",
                height=42,
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                fg_color="#1E293B",
                hover_color="#334155",
                command=lambda i=id_ev: self._selecionar_evento_dialogo(top, i)
            )
            btn_ev.pack(fill="x", pady=4, padx=5)

    def _selecionar_evento_dialogo(self, top_window, id_evento):
        self.entry_url.delete(0, "end")
        self.entry_url.insert(0, id_evento)
        self.log(f"Evento configurado no sistema: ID {id_evento}")
        top_window.destroy()

    # =========================================================
    # FUNÇÕES DE SELEÇÃO E GERENCIAMENTO DE CSV
    # =========================================================
    def listar_csvs_disponiveis(self):
        """Retorna a lista de nomes dos arquivos CSV encontrados no diretório do script"""
        csvs = []
        try:
            if os.path.exists(DIRETORIO_SCRIPT):
                for f in os.listdir(DIRETORIO_SCRIPT):
                    if f.lower().endswith('.csv') and os.path.isfile(os.path.join(DIRETORIO_SCRIPT, f)):
                        csvs.append(f)
        except Exception:
            pass
        return sorted(csvs)

    def atualizar_lista_csv(self):
        """Atualiza o Combobox e o rótulo mostrando a quantidade de arquivos CSV encontrados"""
        csvs = self.listar_csvs_disponiveis()
        qtd = len(csvs)
        
        if qtd == 0:
            texto_lbl = "ARQUIVO CSV DE PARTICIPANTES (Nenhum CSV na pasta)"
        elif qtd == 1:
            texto_lbl = "ARQUIVO CSV DE PARTICIPANTES (1 CSV encontrado)"
        else:
            texto_lbl = f"ARQUIVO CSV DE PARTICIPANTES ({qtd} CSVs encontrados)"
        
        self.lbl_csv.configure(text=texto_lbl)
        if csvs:
            self.combo_csv.configure(values=csvs)

    def on_csv_combo_select(self, escolha):
        """Resolve o caminho ao selecionar um CSV no combobox"""
        caminho_completo = os.path.join(DIRETORIO_SCRIPT, escolha)
        if os.path.exists(caminho_completo):
            self.combo_csv.set(caminho_completo)

    def selecionar_csv(self):
        """Abre o explorador de arquivos para escolher um CSV"""
        caminho = filedialog.askopenfilename(
            title="Selecionar Lista de Participantes",
            filetypes=[("Arquivos CSV", "*.csv"), ("Todos os arquivos", "*.*")]
        )
        if caminho:
            self.combo_csv.set(caminho)
            self.atualizar_lista_csv()

    def log(self, mensagem):
        """Grava a mensagem no arquivo de logs e exibe a última linha na interface"""
        msg_limpa = mensagem.strip()
        if msg_limpa:
            # Atualiza o label de status detalhado com a última linha
            def atualizar():
                self.lbl_status_detalhes.configure(text=msg_limpa)
            self.after(0, atualizar)
            
            # Grava no log completo
            try:
                with open("automacao.log", "a", encoding="utf-8") as f_log:
                    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                    f_log.write(f"[{timestamp}] {mensagem}\n")
            except Exception:
                pass

    def definir_status(self, status_type, texto=""):
        """Atualiza o badge de status e rótulo principal de forma segura"""
        def atualizar():
            if status_type == "idle":
                self.badge_status.configure(
                    text=" PRONTO ",
                    text_color="#A3A3A3",
                    fg_color="#2E2E2E"
                )
                self.lbl_status_geral.configure(text="Pronto para iniciar")
            elif status_type == "automacao":
                self.badge_status.configure(
                    text=" EMISSÃO ATIVA ",
                    text_color="#38BDF8",
                    fg_color="#0C4A6E"
                )
                self.lbl_status_geral.configure(text=texto if texto else "Processando ingressos...")
            elif status_type == "organizacao":
                self.badge_status.configure(
                    text=" ORGANIZANDO ",
                    text_color="#34D399",
                    fg_color="#064E3B"
                )
                self.lbl_status_geral.configure(text=texto if texto else "Organizando arquivos PDF...")
            elif status_type == "concluido":
                self.badge_status.configure(
                    text=" FINALIZADO ",
                    text_color="#10B981",
                    fg_color="#064E3B"
                )
                self.lbl_status_geral.configure(text=texto if texto else "Processo finalizado com sucesso!")
            elif status_type == "erro":
                self.badge_status.configure(
                    text=" ERRO ",
                    text_color="#F87171",
                    fg_color="#7F1D1D"
                )
                self.lbl_status_geral.configure(text=texto if texto else "Ocorreu um erro no processo.")
        self.after(0, atualizar)

    def atualizar_progresso(self, atual, total, texto_status):
        """Atualiza a barra e o texto suavemente"""
        def atualizar():
            fracao = atual / total if total > 0 else 0
            self.barra_progresso.set(fracao)
            self.lbl_progresso.configure(text=f"{texto_status} ({int(fracao * 100)}%)")
        self.after(0, atualizar)

    def alterar_estado_botoes(self, estado):
        """Desativa ou ativa botões e entradas durante o processamento"""
        def atualizar():
            self.btn_rodar.configure(state=estado)
            self.btn_organizar.configure(state=estado)
            self.btn_csv.configure(state=estado)
            self.btn_detectar_url.configure(state=estado)
            self.btn_login_perfil.configure(state=estado)
            self.entry_url.configure(state=estado)
            self.entry_email.configure(state=estado)
            self.entry_quantidade.configure(state=estado)
            self.combo_csv.configure(state=estado)
            self.combo_perfil.configure(state=estado)
        self.after(0, atualizar)

    def exibir_alerta(self, titulo, mensagem):
        """Exibe um diálogo de alerta de forma thread-safe e bloqueia a thread de execução até o OK"""
        event = threading.Event()
        def alertar():
            messagebox.showinfo(titulo, mensagem)
            event.set()
        self.after(0, alertar)
        event.wait()

    # =========================================================
    # GERENCIAMENTO DE THREADS
    # =========================================================
    def iniciar_automacao(self):
        self.alterar_estado_botoes("disabled")
        self.definir_status("automacao", "Lendo arquivo de participantes...")
        self.log("Iniciando execução do processo de automação...")
        threading.Thread(target=self.rodar_automacao, daemon=True).start()

    def iniciar_organizacao(self):
        self.alterar_estado_botoes("disabled")
        self.definir_status("organizacao", "Iniciando organizador...")
        self.log("Analisando pasta de downloads...")
        threading.Thread(target=self.organizar, daemon=True).start()

    # =========================================================
    # LÓGICAS ORIGINAIS DO ROBÔ
    # =========================================================
    def rodar_automacao(self):
        # Coleta configurações atualizadas da interface
        entrada_url = self.entry_url.get().strip()
        url_evento = formatar_url_evento(entrada_url)
        email_padrao = self.entry_email.get().strip()
        quantidade_ingressos = self.entry_quantidade.get().strip()
        arquivo_csv = self.combo_csv.get().strip()

        if not url_evento or "SEU_ID_AQUI" in url_evento:
            self.log("❌ Erro: Por favor, insira um ID de evento válido (ex: 3545453) ou a URL de administração.")
            self.definir_status("erro", "ID ou URL do evento inválido.")
            self.alterar_estado_botoes("normal")
            return

        if not os.path.isabs(arquivo_csv):
            arquivo_csv = os.path.join(DIRETORIO_SCRIPT, arquivo_csv)

        # 1. Verifica quais participantes já possuem ingressos PDF baixados na pasta de destino (ou subpastas)
        self.log("Verificando se existem PDFs de participantes já emitidos...")
        nomes_com_pdf = []
        linhas_restantes = []
        cabecalho = None
        
        try:
            with open(arquivo_csv, 'r', encoding='utf-8-sig') as f:
                linhas = f.readlines()
            
            for linha in linhas:
                linha_limpa = linha.strip()
                if not linha_limpa:
                    continue
                
                nome = linha_limpa.replace(',', ';').split(';')[0].strip()
                
                # Se for cabeçalho
                if nome.lower() in ['nome completo', 'nome', 'aluno', 'participante', 'nomes', '']:
                    cabecalho = linha
                    continue
                
                # Gera o nome seguro do arquivo PDF correspondente
                nome_arquivo_seguro = "".join([c for c in nome if c.isalpha() or c.isdigit() or c==' ']).rstrip()
                
                # Procura pelo arquivo PDF em toda a estrutura da pasta de downloads
                pdf_ja_existe = False
                if os.path.exists(PASTA_DOWNLOADS):
                    for root, dirs, files in os.walk(PASTA_DOWNLOADS):
                        for file in files:
                            if file.lower() == f"{nome_arquivo_seguro.lower()}.pdf":
                                pdf_ja_existe = True
                                break
                        if pdf_ja_existe:
                            break
                
                if pdf_ja_existe:
                    nomes_com_pdf.append(nome)
                else:
                    linhas_restantes.append(linha)
            
            # Se existirem participantes já emitidos, atualiza o arquivo CSV para removê-los
            if nomes_com_pdf:
                self.log(f"Removendo {len(nomes_com_pdf)} participantes do CSV que já têm ingressos PDF...")
                with open(arquivo_csv, 'w', encoding='utf-8-sig', newline='') as f:
                    if cabecalho:
                        f.write(cabecalho)
                    for linha in linhas_restantes:
                        f.write(linha)
                self.log("CSV atualizado com sucesso.")
            else:
                self.log("Nenhum ingresso anterior foi detectado.")
                
        except FileNotFoundError:
            self.log(f"❌ Erro: O arquivo '{arquivo_csv}' não foi encontrado.")
            self.definir_status("erro", "Arquivo CSV não encontrado.")
            self.alterar_estado_botoes("normal")
            return
        except Exception as e_csv:
            self.log(f"Aviso ao filtrar CSV: {e_csv}")

        # 2. Carrega a lista final de nomes do CSV atualizado
        lista_nomes = []
        try:
            with open(arquivo_csv, 'r', encoding='utf-8-sig') as f:
                for linha in f:
                    linha_limpa = linha.strip()
                    if not linha_limpa: continue
                    nome = linha_limpa.replace(',', ';').split(';')[0].strip()
                    if nome.lower() in ['nome completo', 'nome', 'aluno', 'participante', 'nomes', '']: continue
                    lista_nomes.append(nome)
            self.log(f"Total de nomes a emitir: {len(lista_nomes)}")
        except FileNotFoundError:
            self.log(f"❌ Erro: O arquivo '{arquivo_csv}' não foi encontrado.")
            self.definir_status("erro", "Arquivo CSV não encontrado.")
            self.alterar_estado_botoes("normal")
            return

        total = len(lista_nomes)
        
        # Se não restar nenhum participante, finaliza imediatamente de forma amigável
        if total == 0:
            self.log("Todos os participantes já possuem ingressos emitidos!")
            self.definir_status("concluido", "Todos os ingressos já foram emitidos!")
            self.exibir_alerta("Concluído", "Todos os participantes do CSV já possuem ingressos salvos.")
            self.alterar_estado_botoes("normal")
            return

        self.atualizar_progresso(0, total, "Preparando navegador...")

        try:
            with sync_playwright() as p:
                caminho_perfil = self.obter_caminho_perfil()
                self.log(f"Abrindo navegador Chrome (Perfil: {os.path.basename(caminho_perfil)})...")
                context = criar_contexto_chrome(p, caminho_perfil)
                page = context.pages[0] if context.pages else context.new_page()

                # Navega para a página do evento no Sympla
                self.log(f"Navegando para a página do evento no Sympla...")
                navegar_seguro(page, url_evento)
                time.sleep(1.5)

                # Se o botão de adicionar pedido ainda não estiver visível (ex: precisa de login), aguarda o usuário no Chrome
                try:
                    bot_visivel = page.locator("a.btn-primary:has-text('Adicionar Pedido')").is_visible()
                except Exception:
                    bot_visivel = False

                if not bot_visivel:
                    self.aguardar_autenticacao_ou_confirmacao(
                        context,
                        page,
                        "Aguardando o carregamento da página do evento no Chrome...",
                        selector_esperado="a.btn-primary:has-text('Adicionar Pedido')"
                    )
                    if "participantes-administrar" not in page.url.lower():
                        navegar_seguro(page, url_evento)
                        time.sleep(1.5)

                for count, nome_completo in enumerate(lista_nomes, start=1):
                    self.definir_status("automacao", f"Emitindo ingressos de {nome_completo}")
                    self.atualizar_progresso(count, total, f"Processando: {count} de {total}")
                    self.log(f"[{count}/{total}] Iniciando formulário de: {nome_completo}")
                    
                    try:
                        nome_arquivo_seguro = "".join([c for c in nome_completo if c.isalpha() or c.isdigit() or c==' ']).rstrip()
                        
                        # Clique em Adicionar Pedido
                        page.click("a.btn-primary:has-text('Adicionar Pedido')")
                        time.sleep(1.5)
                        
                        # Aguarda o elemento select
                        try:
                            page.wait_for_selector("select.quant-add-order", state="visible", timeout=3000)
                        except:
                            page.wait_for_selector("select.quant-add-order", state="attached", timeout=5000)
                        
                        select_elemento = page.locator("select.quant-add-order").first
                        
                        try:
                            page.wait_for_selector(f"select.quant-add-order option[value='{quantidade_ingressos}']", state="attached", timeout=3000)
                        except:
                            pass
                        
                        try:
                            opcoes = [opt.get_attribute("value") for opt in select_elemento.locator("option").all()]
                        except Exception as e_opt:
                            self.log(f"Aviso: Falha ao diagnosticar dropdown: {e_opt}")
                        
                        select2_selecionado = False
                        try:
                            select2_trigger = page.locator("select.quant-add-order + span.select2, .select2-selection, .select2-container").first
                            select2_trigger.click()
                            time.sleep(0.5)
                            
                            page.wait_for_selector("li.select2-results__option", state="visible", timeout=3000)
                            
                            opcao = page.locator(f"li.select2-results__option:has-text('{quantidade_ingressos}')").first
                            opcao.click()
                            select2_selecionado = True
                        except Exception:
                            pass
                        
                        if not select2_selecionado:
                            try:
                                select_elemento.focus()
                                time.sleep(0.5)
                                page.keyboard.press("Home")
                                time.sleep(0.3)
                                
                                opcoes = [opt.get_attribute("value") for opt in select_elemento.locator("option").all()]
                                if quantidade_ingressos in opcoes:
                                    target_index = opcoes.index(quantidade_ingressos)
                                    for _ in range(target_index):
                                        page.keyboard.press("ArrowDown")
                                        time.sleep(0.2)
                                    page.keyboard.press("Enter")
                                    page.keyboard.press("Tab")
                                else:
                                    select_elemento.evaluate(f"el => {{ el.value = '{quantidade_ingressos}'; el.dispatchEvent(new Event('change', {{ bubbles: true }})); el.dispatchEvent(new Event('input', {{ bubbles: true }})); }}")
                            except Exception:
                                try:
                                    select_elemento.evaluate(f"el => {{ el.value = '{quantidade_ingressos}'; el.dispatchEvent(new Event('change', {{ bubbles: true }})); el.dispatchEvent(new Event('input', {{ bubbles: true }})); }}")
                                except:
                                    select_elemento.select_option(quantidade_ingressos, force=True)
                        
                        time.sleep(2.5)
                        
                        # Continuar
                        page.click("a:has-text('Continuar'), button:has-text('Continuar'), a.btn-warning:has-text('Continuar')")
                        page.wait_for_selector('input[name="first-name"]', timeout=15000)
                        
                        # Preenche os N ingressos sequenciais
                        for i in range(1, int(quantidade_ingressos) + 1):
                            idx = i - 1
                            input_nome = page.locator('input[name="first-name"]').nth(idx)
                            
                            if not input_nome.is_visible():
                                try:
                                    page.locator(f"text=/Ingresso nº {i}/").first.click(timeout=3000)
                                    time.sleep(0.5)
                                except Exception:
                                    pass
                            
                            input_nome.fill(nome_completo, force=True)
                            page.locator('input[name="last-name"]').nth(idx).fill(str(i), force=True)
                            page.locator('input[name="email"]').nth(idx).fill(email_padrao, force=True)
                            time.sleep(0.2)
                        
                        self.log(f"Finalizando pedido de {nome_completo}...")
                        page.click("button.btn-warning:has-text('Finalizar')")
                        
                        # Download do PDF original
                        try:
                            page.wait_for_selector("i.icon-icon-printer, .icon-icon-printer", timeout=15000)
                            
                            with context.expect_page() as new_page_info:
                                page.click("i.icon-icon-printer, .icon-icon-printer")
                            
                            new_page = new_page_info.value
                            new_page.wait_for_load_state("load")
                            pdf_url = new_page.url
                            new_page.close()
                            
                            resposta = context.request.get(pdf_url)
                            if resposta.ok:
                                pdf_bytes = resposta.body()
                                caminho_salvar = os.path.join(PASTA_DOWNLOADS, f"{nome_arquivo_seguro}.pdf")
                                with open(caminho_salvar, "wb") as f_pdf:
                                    f_pdf.write(pdf_bytes)
                                self.log(f"Salvo: {nome_arquivo_seguro}.pdf")
                            else:
                                self.log(f"Falha de download HTTP {resposta.status} para {nome_completo}")
                            
                        except Exception as e_pdf_dl:
                            self.log(f"Aviso: Falha ao salvar PDF de {nome_completo}: {e_pdf_dl}")
                            time.sleep(2)
                        
                        # Retorna ao painel
                        try:
                            page.click("button.close, button:has-text('Fechar')", timeout=2000)
                        except:
                            pass
                        
                        navegar_seguro(page, url_evento)
                        time.sleep(1)
                        
                    except Exception as e_loop:
                        self.log(f"Erro em {nome_completo}. Pulando participante... Detalhe: {e_loop}")
                        navegar_seguro(page, url_evento)
                        time.sleep(1)
                
                self.log("Processamento completo finalizado.")
                self.definir_status("concluido", "Todos os participantes foram processados.")
                self.exibir_alerta("Processo Concluído", "A emissão automatizada de todos os ingressos terminou.")
                context.close()
        except Exception as e_run:
            self.log(f"Erro no navegador: {str(e_run)}")
            self.definir_status("erro", "Erro no motor do navegador.")
        finally:
            self.alterar_estado_botoes("normal")

    def organizar(self):
        if not os.path.exists(PASTA_DOWNLOADS):
            self.log(f"❌ Erro: Pasta '{PASTA_DOWNLOADS}' não encontrada.")
            self.definir_status("erro", "Diretório de downloads inexistente.")
            self.alterar_estado_botoes("normal")
            return

        arquivos = [arq for arq in os.listdir(PASTA_DOWNLOADS) if os.path.isfile(os.path.join(PASTA_DOWNLOADS, arq))]
        total = len(arquivos)
        
        if total == 0:
            self.log("Nenhum arquivo encontrado para organizar.")
            self.definir_status("idle")
            self.alterar_estado_botoes("normal")
            return

        try:
            for count, arquivo in enumerate(arquivos, start=1):
                if not arquivo.lower().endswith('.pdf'):
                    continue
                    
                self.definir_status("organizacao", f"Verificando {arquivo}")
                self.atualizar_progresso(count, total, f"Organizando: {count} de {total}")
                caminho_completo = os.path.join(PASTA_DOWNLOADS, arquivo)
                
                try:
                    # 1. Validação de estrutura PDF
                    try:
                        reader = pypdf.PdfReader(caminho_completo)
                        _ = len(reader.pages) 
                    except Exception:
                        self.log(f"Reparando PDF: '{arquivo}'...")
                        try:
                            reader = pypdf.PdfReader(caminho_completo, strict=False)
                            writer = pypdf.PdfWriter()
                            
                            for p_page in reader.pages:
                                writer.add_page(p_page)
                            
                            caminho_temp = caminho_completo + ".temp"
                            with open(caminho_temp, "wb") as f_out:
                                writer.write(f_out)
                            
                            os.replace(caminho_temp, caminho_completo)
                        except Exception as e_fix:
                            self.log(f"❌ Falha irreparável em '{arquivo}': {e_fix}")
                            continue

                    # 2. Divisão por Categoria (Ex: VIP, Pista, Setor A) baseada na última palavra do nome
                    nome_sem_extensao = arquivo[:-4].strip()
                    partes_nome = nome_sem_extensao.split()
                    
                    if len(partes_nome) > 1:
                        categoria = partes_nome[-1].upper()
                    else:
                        categoria = "GERAL"
                        
                    pasta_categoria = os.path.join(PASTA_DOWNLOADS, categoria)
                    
                    if not os.path.exists(pasta_categoria):
                        os.makedirs(pasta_categoria)
                        
                    caminho_destino = os.path.join(pasta_categoria, arquivo)
                    
                    if not os.path.exists(caminho_destino):
                        shutil.move(caminho_completo, caminho_destino)
                        self.log(f"Organizado: {arquivo} -> Pasta {categoria}")
                    else:
                        self.log(f"Aviso: {arquivo} já existe na pasta {categoria}.")
                    
                except Exception as e_file:
                    self.log(f"Erro em {arquivo}: {e_file}")
                    
            self.log("Todos os ingressos salvos foram organizados por categorias.")
            self.definir_status("concluido", "Ingressos organizados com sucesso.")
            self.exibir_alerta("Organização Concluída", "Arquivos PDF foram validados e movidos para as pastas de suas respectivas categorias.")
        except Exception as e_org:
            self.log(f"Erro grave no organizador: {str(e_org)}")
            self.definir_status("erro", "Erro ao mover arquivos.")
        finally:
            self.alterar_estado_botoes("normal")

# =========================================================
# INICIALIZAÇÃO
# =========================================================
if __name__ == '__main__':
    app = AutomacaoApp()
    app.mainloop()
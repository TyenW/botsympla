# Sympla Ticket Bot: Automação de Ingressos e Gestão de Participantes

Sistema automatizado desenvolvido em Python com interface gráfica (CustomTkinter) e Playwright para emissão em lote de ingressos no portal Sympla e organização de arquivos PDF por categoria.

## Funcionalidades Principais

* **Emissão Automatizada em Lote:** Emissão em lote de ingressos a partir de listas de participantes em formato CSV.
* **Filtro de Antiduplicidade:** Identifica ingressos já gerados no diretório de destino e atualiza a lista de participantes, permitindo a continuidade do processo sem duplicidades.
* **Organização Automática por Categoria:** Classifica e move os arquivos PDF para subpastas de acordo com a categoria informada no nome do participante (exemplo: VIP, Pista, Setor A, Geral).
* **Detecção Automática de Eventos:** Conecta-se à conta do organizador e lista os eventos disponíveis para automação.
* **Gestão de Múltiplos Perfis:** Permite isolar e gerenciar diferentes perfis de navegadores salvos para operar múltiplas contas de organizadores.
* **Interface Gráfica Integrada:** Painel com controle de status, registros de log em tempo real e barra de progresso.

## Tecnologias Utilizadas

* **Python 3.10+**
* **CustomTkinter:** Interface gráfica de usuário.
* **Playwright:** Automação e navegação web.
* **Pandas:** Leitura e manipulação de dados CSV.
* **PyPDF:** Validação e estruturação de arquivos PDF.

## Pré-requisitos

1. Python 3.10 ou superior instalado.
2. Google Chrome instalado no sistema operacional.

## Instalação

1. Clone o repositório ou faça o download do projeto:
   ```bash
   git clone https://github.com/usuario/botsympla.git
   cd botsympla
   ```

2. Instale as dependências necessárias:
   ```bash
   pip install pandas playwright customtkinter pypdf
   ```

3. Instale os navegadores do Playwright:
   ```bash
   playwright install chromium
   ```

## Formato do Arquivo CSV

O arquivo CSV suporta até 3 colunas separadas por vírgula (ou ponto e vírgula): `Nome Completo`, `Setor` (ou Categoria) e `Quantidade` (opcional - quantidade de ingressos individual por participante):

```csv
Nome Completo, Setor, Quantidade
João Silva, VIP, 2
Maria Santos, Pista, 1
Carlos Oliveira, Setor A, 3
Ana Souza, Geral, 1
Pedro Henrique, VIP, 4
```

*Nota: Se a 3ª coluna (`Quantidade`) for omitida para algum participante, a quantidade padrão configurada na tela da aplicação será utilizada.*

## Instruções de Uso

### 1. Inicialização
Execute o script principal:
```bash
python automacao_ingressos.py
```

### 2. Autenticação na Conta Sympla
* Selecione o perfil de navegador desejado no campo "PERFIL DO NAVEGADOR CHROME".
* Clique no botão "Fazer Login".
* Realize a autenticação na janela do navegador.
* Após concluir a autenticação no Sympla, confirme a mensagem de validação no sistema.

### 3. Seleção do Evento
* Informe o ID do evento (exemplo: `3545453`) ou a URL de administração.
* Opcionalmente, utilize o botão "Detectar Eventos" para listar os eventos ativos da conta autenticada.

### 4. Seleção do Arquivo CSV
* Selecione o arquivo CSV na lista suspensa do sistema ou utilize o botão "Procurar..." para localizar o arquivo no disco.

### 5. Execução do Processo
* Clique em "RODAR AUTOMAÇÃO" para iniciar a emissão dos ingressos.
* Clique em "ORGANIZAR INGRESSOS" para processar e mover os PDFs baixados para suas respectivas pastas por categoria.

## Estrutura do Repositório

```text
botsympla/
│
├── automacao_ingressos.py    # Código-fonte principal e interface gráfica
├── lista_participantes.csv   # Arquivo CSV de exemplo
├── Ingressos_Salvos/         # Diretório de destino dos PDFs emitidos e organizados
├── Perfil_Navegador/         # Diretório de perfil e sessão do navegador
├── automacao.log             # Registro de logs da aplicação
└── README.md                 # Documentação do projeto
```

## Licença

Este projeto é disponibilizado sob a licença MIT.

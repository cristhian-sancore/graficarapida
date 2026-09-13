# 🖨️ Gráfica Rápida Express - Plataforma Completa e Segura

Sistema web de alta performance para **Gráficas Rápida e Empresas de Impressão Digital/Off-Set**, com **Autenticação Segura (PBKDF2/SHA256)**, **Portal do Cliente Protegido**, **Kanban de Produção**, **Gestão de Estoque**, **Orçamentista Manual** e **Controle Financeiro de Caixa**.

---

## 🚀 Como Executar o Sistema

### Opção 1: Via Docker & Docker Compose (Recomendado) 🐳
Com o Docker instalado, execute com um único comando:
```bash
docker-compose up -d --build
```
Acesse o sistema no seu navegador em:
👉 **http://127.0.0.1:8050**

---

### Opção 2: Execução Direta via Python 🐍

#### Pré-requisitos
- **Python 3.8+** instalado.
- Dependências instaladas via `pip install -r requirements.txt`.

#### Passos para Iniciar
1. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

2. Execute o servidor Python:
   ```bash
   python app.py
   ```

3. Acesse no seu navegador em:
   👉 **http://127.0.0.1:8050**

---

## 🔒 Segurança & Autenticação (Proteção LGPD / Sem Vazamento de Dados)

### 👤 Autenticação do Cliente
- **Registro & Login de Conta**: O cliente cadastra seu e-mail, WhatsApp e define uma senha criptografada.
- **Isolamento Total**: O cliente só tem acesso aos **seus próprios pedidos, suas próprias artes e seus orçamentos**.
- **Token de Sessão (`X-Client-Token`)**: Protege todas as APIs do cliente contra consultas não autorizadas por terceiros.

### 🛡️ Autenticação do Administrador
- **Usuário Padrão**: `admin`
- **Senha Padrão**: `admin123`
- **Token de Sessão Admin (`X-Admin-Token`)**: Bloqueia completamente qualquer tentativa de alteração de status, visualização do caixa ou edição de produtos sem um login ativo.

---

## ✨ Funcionalidades Principais

### 🛍️ Loja Online do Cliente
- **Catálogo Dinâmico & Calculadora em Tempo Real**:
  - Personalização de formato, papel, acabamento e tiragens com desconto progressivo.
  - Upload de arquivos de arte (PDF/CDR/PNG/JPG) com preview ou contratação de criação de arte (+R$ 35,00).
- **Checkout com Cupons & PIX**:
  - Geração de QR Code PIX + Copia e Cola com 5% de desconto.
  - Validação de cupons promocionais (ex: `PRIMEIRACOMPRA10`, `VIP15`).

### 👤 Portal Exclusivo do Cliente (`Área do Cliente`)
- **Histórico & Repetir Pedidos**: Repetir pedidos anteriores com 1 clique.
- **Minhas Artes Salvas**: Biblioteca privada para guardar logotipos e vetores com segurança.
- **Solicitar Orçamento Especial**: Pedir cotações sob medida para projetos especiais.

### 🛡️ Painel do Administrador (Área Admin)
- **📋 Kanban de Produção**:
  - Quadro visual estilo Trello (`Análise de Arte` ➔ `Em Impressão` ➔ `Acabamento & Corte` ➔ `Pronto / Expedição`).
- **📊 Dashboard & KPIs**: Gráficos de receita bruta, total de pedidos e número de clientes.
- **📄 Emissão de Ordem de Serviço (OS)**: Impressão formatada da comanda para a equipe de produção.
- **📦 Gestão de Produtos (CRUD)**: Edição de produtos e preços.
- **🏭 Controle de Estoque de Insumos**: Alerta automático de estoque baixo (`⚠️ Baixo Estoque`).
- **💰 Controle de Caixa (Financeiro)**: Entradas, saídas e sangrias com saldo em tempo real.
- **📝 Orçamentista Manual**: Gerador de orçamentos para balcão e WhatsApp.
- **🎟️ Gestão de Cupons**: Criar e inativar cupons de desconto.

---

## 🛠 Arquitetura de Arquivos

```
c:\NAO-APAGAR\GRAFICA RAPIDA\
├── app.py                  # Servidor Flask REST API e banco SQLite3 seguro
├── grafica.db              # Banco de dados relacional SQLite com criptografia de senhas
├── static/
│   ├── css/
│   │   └── style.css       # Design System Glassmorphic moderno
│   ├── js/
│   │   └── app.js          # Lógica frontend SPA e autenticação
│   └── uploads/            # Armazenamento de artes enviadas
├── templates/
│   └── index.html          # Interface principal SPA
├── MANUAL_SISTEMA.md       # Guia completo do usuário e administrador
└── README.md               # Este arquivo de instruções
```

import os
import sys
import sqlite3
import json
import uuid
import random
import urllib.request
import urllib.parse
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['SECRET_KEY'] = 'grafica-rapida-express-secret-key-2026'
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32MB max upload

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Se o diretÃ³rio /app/data existir (Portainer volume), salva o banco em /app/data/grafica.db
default_db_dir = '/app/data' if os.path.exists('/app/data') else BASE_DIR
default_db_path = os.path.join(default_db_dir, 'grafica.db')

DB_PATH = os.environ.get('DB_PATH', default_db_path)
db_dir = os.path.dirname(DB_PATH)
if db_dir:
    os.makedirs(db_dir, exist_ok=True)

DATABASE_URL = os.environ.get('DATABASE_URL') or os.environ.get('POSTGRES_URL')

class RowDict(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            vals = list(self.values())
            if 0 <= key < len(vals):
                return vals[key]
            raise IndexError("RowDict index out of range")
        return super().__getitem__(key)

class DBWrapper:
    def __init__(self, conn, is_postgres=False):
        self.conn = conn
        self.is_postgres = is_postgres

    def cursor(self):
        return CursorWrapper(self.conn.cursor(), self.conn, self.is_postgres)

    def commit(self):
        return self.conn.commit()

    def rollback(self):
        return self.conn.rollback()

    def close(self):
        return self.conn.close()

class CursorWrapper:
    def __init__(self, cursor, conn, is_postgres=False):
        self.cursor = cursor
        self.conn = conn
        self.is_postgres = is_postgres
        self.last_inserted_id = None

    def execute(self, query, params=None):
        if self.is_postgres:
            query_pg = query.replace('?', '%s')
            query_pg = query_pg.replace('INTEGER PRIMARY KEY AUTOINCREMENT', 'SERIAL PRIMARY KEY')
            query_pg = query_pg.replace('DATETIME', 'TIMESTAMP')
            
            is_insert = 'INSERT INTO' in query_pg.upper()
            if is_insert and 'RETURNING' not in query_pg.upper():
                query_pg = query_pg.rstrip().rstrip(';') + ' RETURNING id;'

            if params is None:
                self.cursor.execute(query_pg)
            else:
                self.cursor.execute(query_pg, params)

            if is_insert:
                try:
                    res = self.cursor.fetchone()
                    if res:
                        self.last_inserted_id = res['id'] if isinstance(res, (dict, RowDict)) and 'id' in res else res[0]
                except Exception:
                    pass
            return self.cursor
        else:
            if params is None:
                return self.cursor.execute(query)
            return self.cursor.execute(query, params)

    def executemany(self, query, seq_of_params):
        if self.is_postgres:
            query_pg = query.replace('?', '%s')
            query_pg = query_pg.replace('INTEGER PRIMARY KEY AUTOINCREMENT', 'SERIAL PRIMARY KEY')
            query_pg = query_pg.replace('DATETIME', 'TIMESTAMP')
            return self.cursor.executemany(query_pg, seq_of_params)
        else:
            return self.cursor.executemany(query, seq_of_params)

    def __getattr__(self, name):
        return getattr(self.cursor, name)

    def fetchone(self):
        row = self.cursor.fetchone()
        if not row:
            return None
        if isinstance(row, (dict, RowDict)):
            return RowDict(row)
        if hasattr(row, 'keys'):
            return RowDict({k: row[k] for k in row.keys()})
        if isinstance(row, (list, tuple)):
            return RowDict({i: row[i] for i in range(len(row))})
        return row

    def fetchall(self):
        rows = self.cursor.fetchall()
        if not rows:
            return []
        res = []
        for r in rows:
            if isinstance(r, (dict, RowDict)):
                res.append(RowDict(r))
            elif hasattr(r, 'keys'):
                res.append(RowDict({k: r[k] for k in r.keys()}))
            elif isinstance(r, (list, tuple)):
                res.append(RowDict({i: r[i] for i in range(len(r))}))
            else:
                res.append(r)
        return res


    @property
    def lastrowid(self):
        if self.is_postgres:
            return self.last_inserted_id or 1
        return self.cursor.lastrowid

def get_db():
    if DATABASE_URL and ('postgres://' in DATABASE_URL or 'postgresql://' in DATABASE_URL):
        import psycopg2
        import psycopg2.extras
        pg_url = DATABASE_URL.replace('postgres://', 'postgresql://')
        conn = psycopg2.connect(pg_url, cursor_factory=psycopg2.extras.RealDictCursor)
        return DBWrapper(conn, is_postgres=True)
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return DBWrapper(conn, is_postgres=False)

def safe_add_column(cursor, conn, table, column_def):
    try:
        cursor.execute(f'ALTER TABLE {table} ADD COLUMN {column_def}')
        conn.commit()
    except Exception:
        conn.rollback()

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Chat Interno
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mensagens_chat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referencia_codigo TEXT NOT NULL,
            remetente_tipo TEXT NOT NULL,
            remetente_nome TEXT NOT NULL,
            telefone_cliente TEXT,
            mensagem TEXT NOT NULL,
            lida INTEGER DEFAULT 0,
            data_envio DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ConfiguraÃ§Ãµes do Site / CMS / Evolution API
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS configuracoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_grafica TEXT NOT NULL,
            whatsapp TEXT NOT NULL,
            chave_pix TEXT NOT NULL,
            banner_titulo TEXT,
            banner_subtitulo TEXT,
            aviso_topo TEXT,
            desconto_pix REAL DEFAULT 5.0,
            taxa_entrega REAL DEFAULT 15.0,
            evolution_api_url TEXT,
            evolution_api_key TEXT,
            evolution_instance TEXT,
            validar_whatsapp_ativo INTEGER DEFAULT 1
        )
    ''')
    conn.commit()
    
    # MigraÃ§Ãµes das configuraÃ§Ãµes da Evolution API
    safe_add_column(cursor, conn, 'configuracoes', 'evolution_api_url TEXT')
    safe_add_column(cursor, conn, 'configuracoes', 'evolution_api_key TEXT')
    safe_add_column(cursor, conn, 'configuracoes', 'evolution_instance TEXT')
    safe_add_column(cursor, conn, 'configuracoes', 'validar_whatsapp_ativo INTEGER DEFAULT 1')

    # Produtos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            categoria TEXT NOT NULL,
            descricao TEXT,
            preco_base REAL NOT NULL,
            imagem_url TEXT,
            tamanhos_json TEXT,
            papeis_json TEXT,
            acabamentos_json TEXT,
            tiragens_json TEXT,
            ativo INTEGER DEFAULT 1,
            destaque INTEGER DEFAULT 0
        )
    ''')
    conn.commit()

    # Clientes com AutenticaÃ§Ã£o e CÃ³digo WhatsApp
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            telefone TEXT NOT NULL,
            senha_hash TEXT NOT NULL,
            endereco TEXT,
            cpf_cnpj TEXT,
            token_sessao TEXT,
            codigo_validacao TEXT,
            status_validacao TEXT DEFAULT 'Pendente',
            data_cadastro DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()

    safe_add_column(cursor, conn, 'clientes', 'senha_hash TEXT')
    safe_add_column(cursor, conn, 'clientes', 'token_sessao TEXT')
    safe_add_column(cursor, conn, 'clientes', 'codigo_validacao TEXT')
    safe_add_column(cursor, conn, 'clientes', 'status_validacao TEXT DEFAULT \'Pendente\'')

    # UsuÃ¡rios Administradores
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios_admin (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE NOT NULL,
            senha_hash TEXT NOT NULL,
            nome TEXT NOT NULL,
            token_sessao TEXT,
            data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Biblioteca de Artes do Cliente
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cliente_artes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER NOT NULL,
            nome_arquivo TEXT NOT NULL,
            url_arquivo TEXT NOT NULL,
            tamanho_bytes INTEGER DEFAULT 0,
            data_upload DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (cliente_id) REFERENCES clientes(id)
        )
    ''')

    # Pedidos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pedidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo_pedido TEXT UNIQUE NOT NULL,
            cliente_id INTEGER,
            cliente_nome TEXT NOT NULL,
            cliente_telefone TEXT NOT NULL,
            cliente_email TEXT,
            total REAL NOT NULL,
            desconto REAL DEFAULT 0.0,
            taxa_entrega REAL DEFAULT 0.0,
            metodo_pagamento TEXT NOT NULL,
            status_pagamento TEXT DEFAULT 'Aguardando Pagamento',
            status_producao TEXT DEFAULT 'Aguardando Pagamento',
            tipo_entrega TEXT DEFAULT 'Balcao',
            endereco_entrega TEXT,
            observacoes TEXT,
            cupom_aplicado TEXT,
            data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP,
            data_atualizacao DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (cliente_id) REFERENCES clientes(id)
        )
    ''')

    # Itens do Pedido
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS itens_pedido (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pedido_id INTEGER NOT NULL,
            produto_id INTEGER,
            produto_nome TEXT NOT NULL,
            tamanho TEXT,
            papel TEXT,
            acabamento TEXT,
            quantidade INTEGER NOT NULL,
            preco_unitario REAL NOT NULL,
            preco_total REAL NOT NULL,
            arte_url TEXT,
            criar_arte INTEGER DEFAULT 0,
            detalhes_arte TEXT,
            FOREIGN KEY (pedido_id) REFERENCES pedidos(id)
        )
    ''')

    # MovimentaÃ§Ãµes de Caixa
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS caixa_movimentacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT NOT NULL,
            categoria TEXT NOT NULL,
            descricao TEXT NOT NULL,
            valor REAL NOT NULL,
            forma_pagamento TEXT DEFAULT 'Dinheiro',
            pedido_id INTEGER,
            usuario TEXT DEFAULT 'Admin',
            data_movimento DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Estoque de Insumos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS estoque_insumos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_insumo TEXT NOT NULL,
            categoria TEXT NOT NULL,
            quantidade_atual REAL NOT NULL,
            quantidade_minima REAL NOT NULL,
            unidade_medida TEXT NOT NULL,
            custo_unitario REAL DEFAULT 0.0
        )
    ''')

    # OrÃ§amentos Personalizados
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orcamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo_orcamento TEXT UNIQUE NOT NULL,
            cliente_nome TEXT NOT NULL,
            cliente_telefone TEXT NOT NULL,
            descricao TEXT NOT NULL,
            valor_estimado REAL NOT NULL,
            status TEXT DEFAULT 'Pendente',
            data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    safe_add_column(cursor, conn, 'orcamentos', 'cliente_id INTEGER')

    # Cupons de Desconto
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cupons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT UNIQUE NOT NULL,
            porcentagem_desconto REAL NOT NULL,
            valor_minimo REAL DEFAULT 0.0,
            limite_usos INTEGER DEFAULT 100,
            usos_atuais INTEGER DEFAULT 0,
            ativo INTEGER DEFAULT 1
        )
    ''')

    # ConfiguraÃ§Ãµes Iniciais
    cursor.execute('SELECT COUNT(*) AS total FROM configuracoes')
    r_cfg = cursor.fetchone()
    total_cfg = r_cfg['total'] if isinstance(r_cfg, dict) or hasattr(r_cfg, 'keys') else r_cfg[0]
    if total_cfg == 0:
        cursor.execute('''
            INSERT INTO configuracoes (nome_grafica, whatsapp, chave_pix, banner_titulo, banner_subtitulo, aviso_topo, evolution_api_url, evolution_api_key, evolution_instance, validar_whatsapp_ativo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            'GrÃ¡fica RÃ¡pida Express',
            '5511999998888',
            'pix@graficarapidaexpress.com.br',
            'Sua ImpressÃ£o RÃ¡pida, Sem ComplicaÃ§Ã£o!',
            'CartÃµes de visita, panfletos, banners, adesivos e brindes com entrega expressa e qualidade profissional.',
            'âš¡ Atendimento Express: Pedidos feitos atÃ© as 12h ficam prontos no mesmo dia!',
            'https://api.evolution.com.br',
            'API_KEY_EVOLUTION_EXEMPLO',
            'grafica-express',
            1
        ))
        conn.commit()

    # Admin PadrÃ£o (admin / admin123)
    cursor.execute('SELECT COUNT(*) AS total FROM usuarios_admin')
    r_adm = cursor.fetchone()
    total_adm = r_adm['total'] if isinstance(r_adm, dict) or hasattr(r_adm, 'keys') else r_adm[0]
    if total_adm == 0:
        cursor.execute('''
            INSERT INTO usuarios_admin (usuario, senha_hash, nome)
            VALUES (?, ?, ?)
        ''', ('admin', generate_password_hash('admin123'), 'Administrador Geral'))
        conn.commit()

    # Produtos Iniciais
    cursor.execute('SELECT COUNT(*) AS total FROM produtos')
    r_prod = cursor.fetchone()
    total_prod = r_prod['total'] if isinstance(r_prod, dict) or hasattr(r_prod, 'keys') else r_prod[0]
    if total_prod == 0:
        produtos_padrao = [
            (
                'CartÃ£o de Visita Premium',
                'CartÃµes',
                'Impressione seus clientes com cartÃµes de alta gramatura e verniz brilhante.',
                35.00,
                'https://images.unsplash.com/photo-1589939705384-5185137a7f0f?w=600&auto=format&fit=crop&q=80',
                json.dumps(['9 x 5 cm', '9 x 10 cm (Duplo/Dobrado)']),
                json.dumps(['Couche 300g (Encorpado)', 'Couche 250g', 'Reciclato 240g']),
                json.dumps(['Verniz UV Total Frente', 'Verniz Localizado + LaminaÃ§Ã£o Fosca', 'Corte Reto PadrÃ£o', 'Cantos Arredondados']),
                json.dumps([
                    {'qtd': 100, 'preco': 35.00},
                    {'qtd': 500, 'preco': 65.00},
                    {'qtd': 1000, 'preco': 95.00},
                    {'qtd': 2500, 'preco': 180.00}
                ]),
                1, 1
            ),
            (
                'Panfletos & Folders Promocionais',
                'Panfletos',
                'Divulgue sua empresa com panfletos coloridos de alta definiÃ§Ã£o.',
                50.00,
                'https://images.unsplash.com/photo-1561070791-2526d30994b5?w=600&auto=format&fit=crop&q=80',
                json.dumps(['A6 (10 x 14 cm)', 'A5 (14 x 20 cm)', 'A4 (21 x 29 cm)']),
                json.dumps(['Couche 115g (Standard)', 'Couche 150g (Premium)', 'Offset 90g']),
                json.dumps(['ImpressÃ£o Frente (4x0)', 'ImpressÃ£o Frente e Verso (4x4)', 'Dobra Central']),
                json.dumps([
                    {'qtd': 500, 'preco': 90.00},
                    {'qtd': 1000, 'preco': 140.00},
                    {'qtd': 2500, 'preco': 260.00},
                    {'qtd': 5000, 'preco': 420.00}
                ]),
                1, 1
            ),
            (
                'Banner em Lona com IlhÃ³s / BastÃ£o',
                'Banners',
                'Alta durabilidade para fachadas, eventos, promoÃ§Ãµes e sinalizaÃ§Ã£o.',
                60.00,
                'https://images.unsplash.com/photo-1542744094-3a31b272c490?w=600&auto=format&fit=crop&q=80',
                json.dumps(['60 x 90 cm', '80 x 120 cm', '100 x 150 cm', '200 x 100 cm']),
                json.dumps(['Lona 440g Brilho (Alta Resistencia)', 'Lona 440g Fosca Anti-reflexo']),
                json.dumps(['BastÃ£o de Madeira + CordÃ£o', 'IlhÃ³s nos 4 Cantos', 'IlhÃ³s a cada 50cm']),
                json.dumps([
                    {'qtd': 1, 'preco': 60.00},
                    {'qtd': 3, 'preco': 150.00},
                    {'qtd': 5, 'preco': 220.00}
                ]),
                1, 1
            ),
            (
                'Adesivos & Etiquetas Vinil',
                'Adesivos',
                'Adesivos Ã  prova d\'Ã¡gua cortados no formato do seu logotipo.',
                45.00,
                'https://images.unsplash.com/photo-1572375992501-4b0892d50c69?w=600&auto=format&fit=crop&q=80',
                json.dumps(['3 x 3 cm', '5 x 5 cm', '7 x 7 cm', '10 x 10 cm']),
                json.dumps(['Vinil Brilho ImpermeÃ¡vel', 'Vinil Transparente', 'Vinil Fosco']),
                json.dumps(['Corte EletrÃ´nico Especial', 'Corte Quadrado/Retangular', 'Cartela sem Corte']),
                json.dumps([
                    {'qtd': 100, 'preco': 45.00},
                    {'qtd': 500, 'preco': 110.00},
                    {'qtd': 1000, 'preco': 190.00}
                ]),
                1, 1
            ),
            (
                'TalÃµes & Blocos de Pedidos / Recibos',
                'TalÃµes',
                'Blocos autocopiativos personalizados com a marca da sua empresa.',
                75.00,
                'https://images.unsplash.com/photo-1586075010923-2dd4570fb338?w=600&auto=format&fit=crop&q=80',
                json.dumps(['1/4 de Folha (10 x 15 cm)', '1/2 Folha (15 x 21 cm)', 'A4 (21 x 29 cm)']),
                json.dumps(['Sulfite 75g (1 Via)', 'Autocopiativo 2 Vias (Branco/CanÃ¡rio)', 'Autocopiativo 3 Vias']),
                json.dumps(['Blocagem 50 Folhas', 'NumeraÃ§Ã£o SeqÃ¼encial', 'Serrilha p/ Destaque']),
                json.dumps([
                    {'qtd': 5, 'preco': 75.00},
                    {'qtd': 10, 'preco': 130.00},
                    {'qtd': 20, 'preco': 220.00}
                ]),
                1, 0
            ),
            (
                'Envelopes Personalizados',
                'Envelopes',
                'Envelopes de carta e ofÃ­cio impressos com sua marca e dados.',
                85.00,
                'https://images.unsplash.com/photo-1579783902614-a3fb3927b675?w=600&auto=format&fit=crop&q=80',
                json.dumps(['Saco A4 (24 x 34 cm)', 'OfÃ­cio (11 x 22 cm)', 'Carta (11 x 16 cm)']),
                json.dumps(['Offset 90g', 'Offset 120g Encorpado']),
                json.dumps(['ImpressÃ£o Frente', 'Aba Gomada / Fita Dupla Face']),
                json.dumps([
                    {'qtd': 100, 'preco': 85.00},
                    {'qtd': 500, 'preco': 210.00},
                    {'qtd': 1000, 'preco': 360.00}
                ]),
                1, 0
            )
        ]
        cursor.executemany('''
            INSERT INTO produtos (nome, categoria, descricao, preco_base, imagem_url, tamanhos_json, papeis_json, acabamentos_json, tiragens_json, ativo, destaque)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', produtos_padrao)

    # Insumos Iniciais
    cursor.execute('SELECT COUNT(*) AS total FROM estoque_insumos')
    r_ins = cursor.fetchone()
    total_ins = r_ins['total'] if isinstance(r_ins, dict) or hasattr(r_ins, 'keys') else r_ins[0]
    if total_ins == 0:
        insumos_padrao = [
            ('Papel Couche 300g (Folhas A3+)', 'PapÃ©is', 450, 100, 'Folhas', 0.80),
            ('Papel Couche 115g (Folhas A3+)', 'PapÃ©is', 1200, 250, 'Folhas', 0.35),
            ('Bobina de Lona 440g Brilho (1.60m)', 'MÃ­dias Grandes', 85, 20, 'Metros', 12.50),
            ('Bobina de Vinil Adesivo Brilho', 'Adesivos', 110, 30, 'Metros', 9.00),
            ('Toner Preto Alta Capacidade (CMYK)', 'Suprimentos', 4, 1, 'Unidades', 240.00),
            ('Toner Ciano / Magenta / Amarelo', 'Suprimentos', 6, 2, 'Kits', 480.00),
            ('BastÃµes de Madeira para Banners', 'Acabamentos', 140, 30, 'Metros', 2.20)
        ]
        for ins in insumos_padrao:
            cursor.execute('''
                INSERT INTO estoque_insumos (nome_insumo, categoria, quantidade_atual, quantidade_minima, unidade_medida, custo_unitario)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', ins)
        conn.commit()

    # Cupons Iniciais
    cursor.execute('SELECT COUNT(*) AS total FROM cupons')
    r_cup = cursor.fetchone()
    total_cup = r_cup['total'] if isinstance(r_cup, dict) or hasattr(r_cup, 'keys') else r_cup[0]
    if total_cup == 0:
        cupons_padrao = [
            ('PRIMEIRACOMPRA10', 10.0, 50.0, 500, 0, 1),
            ('VIP15', 15.0, 100.0, 100, 0, 1)
        ]
        for cup in cupons_padrao:
            cursor.execute('''
                INSERT INTO cupons (codigo, porcentagem_desconto, valor_minimo, limite_usos, usos_atuais, ativo)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', cup)
        conn.commit()

    conn.commit()
    conn.close()


init_db()

# --- HELPER EVOLUTION API WHATSAPP ---

def send_evolution_whatsapp(numero, mensagem, custom_url=None, custom_key=None, custom_instance=None):
    if custom_url and custom_key and custom_instance:
        api_url = str(custom_url).strip().rstrip('/')
        api_key = str(custom_key).strip()
        instance = str(custom_instance).strip()
    else:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT evolution_api_url, evolution_api_key, evolution_instance, validar_whatsapp_ativo FROM configuracoes LIMIT 1')
        row = cursor.fetchone()
        conn.close()
        cfg = dict(row) if row else {}
        api_url = (cfg.get('evolution_api_url') or '').strip().rstrip('/')
        api_key = (cfg.get('evolution_api_key') or '').strip()
        instance = (cfg.get('evolution_instance') or '').strip()

    if not api_url or not api_key or not instance:
        print(f"[Evolution API Alert] ConfiguraÃ§Ãµes incompletas da Evolution API.")
        return False, "ConfiguraÃ§Ãµes da Evolution API incompletas (URL, API Key e InstÃ¢ncia sÃ£o obrigatÃ³rios)."

    # Sanitizar nÃºmero (Apenas nÃºmeros ex: 5511999998888 ou 556596772226)
    num_limpo = ''.join(c for c in str(numero) if c.isdigit())
    if not num_limpo.startswith('55') and len(num_limpo) <= 11:
        num_limpo = '55' + num_limpo

    numeros_para_tentar = [num_limpo]
    if len(num_limpo) == 13 and num_limpo.startswith('55'):
        num_sem_9 = num_limpo[:4] + num_limpo[5:]
        if num_sem_9 not in numeros_para_tentar:
            numeros_para_tentar.append(num_sem_9)

    endpoint = f"{api_url}/message/sendText/{instance}"
    headers = {
        'Content-Type': 'application/json',
        'apikey': api_key,
        'User-Agent': 'Mozilla/5.0'
    }

    ultimo_erro = "Falha ao enviar mensagem."
    for target_num in numeros_para_tentar:
        payload = json.dumps({"number": target_num, "text": mensagem}).encode('utf-8')
        try:
            req = urllib.request.Request(endpoint, data=payload, headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=12) as response:
                res_body = response.read().decode('utf-8')
                print(f"[Evolution API Success] WhatsApp enviado para {target_num}: {res_body}")
                return True, res_body
        except urllib.error.HTTPError as e:
            err_content = e.read().decode('utf-8', errors='ignore')
            print(f"[Evolution API HTTPError] Status {e.code} para {target_num}: {err_content}")
            try:
                err_json = json.loads(err_content)
                msg_detalhe = err_json.get('response', {}).get('message') or err_json.get('message') or err_content
                if isinstance(msg_detalhe, list):
                    msg_detalhe = ", ".join(msg_detalhe)
                ultimo_erro = f"HTTP {e.code}: {msg_detalhe}"
            except Exception:
                ultimo_erro = f"HTTP {e.code}: {err_content or e.reason}"
        except Exception as e:
            print(f"[Evolution API Error] Erro ao enviar para {target_num}: {e}")
            ultimo_erro = str(e)

    return False, ultimo_erro

# --- HELPER DE AUTENTICAÃ‡ÃƒO ---

def get_current_client(token):
    if not token:
        return None
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id, nome, email, telefone, endereco, status_validacao FROM clientes WHERE token_sessao = ?', (token,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_current_admin(token):
    if not token:
        return None
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id, usuario, nome FROM usuarios_admin WHERE token_sessao = ?', (token,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

# --- ROTAS FRONTEND ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# --- APIS DE AUTENTICAÃ‡ÃƒO DO CLIENTE & EVOLUTION API WHATSAPP ---

@app.route('/api/auth/cliente/cadastrar', methods=['POST'])
def auth_cliente_cadastrar():
    data = request.json
    nome = data.get('nome', '').strip()
    email = data.get('email', '').strip().lower()
    telefone = data.get('telefone', '').strip()
    senha = data.get('senha', '')

    if not nome or not email or not telefone or not senha:
        return jsonify({'error': 'Todos os campos sÃ£o obrigatÃ³rios!'}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM clientes WHERE email = ?', (email,))
    if cursor.fetchone():
        conn.close()
        return jsonify({'error': 'JÃ¡ existe uma conta cadastrada com este E-mail!'}), 400

    cursor.execute('SELECT validar_whatsapp_ativo FROM configuracoes LIMIT 1')
    cfg_row = cursor.fetchone()
    validar_ativo = cfg_row['validar_whatsapp_ativo'] if cfg_row else 1

    senha_hash = generate_password_hash(senha)
    codigo_otp = str(random.randint(100000, 999999))
    status_val = 'Pendente' if validar_ativo == 1 else 'Ativo'
    token_sessao = uuid.uuid4().hex if status_val == 'Ativo' else None

    cursor.execute('''
        INSERT INTO clientes (nome, email, telefone, senha_hash, codigo_validacao, status_validacao, token_sessao)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (nome, email, telefone, senha_hash, codigo_otp, status_val, token_sessao))

    conn.commit()
    cliente_id = cursor.lastrowid
    conn.close()

    if validar_ativo == 1:
        msg = f"ðŸ”’ *GrÃ¡fica RÃ¡pida Express*\nOlÃ¡ {nome}! Seu cÃ³digo de validaÃ§Ã£o de cadastro Ã©: *{codigo_otp}*\n\nDigite este cÃ³digo no site para ativar sua conta!"
        sucesso, msg_status = send_evolution_whatsapp(telefone, msg)
        
        res_data = {
            'requer_validacao': True,
            'cliente_id': cliente_id,
            'email': email,
            'telefone': telefone,
            'message': f"CÃ³digo de validaÃ§Ã£o enviado para o seu WhatsApp ({telefone})!"
        }
        if not sucesso:
            res_data['codigo_dev'] = codigo_otp
            
        return jsonify(res_data), 201
    else:
        return jsonify({
            'requer_validacao': False,
            'token': token_sessao,
            'cliente': {'id': cliente_id, 'nome': nome, 'email': email, 'telefone': telefone},
            'message': 'Conta criada e ativada com sucesso!'
        }), 201

@app.route('/api/auth/cliente/validar-codigo', methods=['POST'])
def auth_cliente_validar_codigo():
    data = request.json or {}
    cliente_id = data.get('cliente_id')
    email = data.get('email', '').strip().lower()
    codigo = str(data.get('codigo', '')).strip()

    if not codigo or (not cliente_id and not email):
        return jsonify({'error': 'Informe o cÃ³digo de validaÃ§Ã£o e o ID/E-mail do cliente.'}), 400

    conn = get_db()
    cursor = conn.cursor()
    if cliente_id:
        cursor.execute('SELECT * FROM clientes WHERE id = ?', (cliente_id,))
    else:
        cursor.execute('SELECT * FROM clientes WHERE email = ?', (email,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return jsonify({'error': 'Cliente nÃ£o encontrado.'}), 404

    if str(row['codigo_validacao']).strip() != codigo:
        conn.close()
        return jsonify({'error': 'CÃ³digo de validaÃ§Ã£o incorreto!'}), 400

    token_sessao = uuid.uuid4().hex
    cursor.execute('''
        UPDATE clientes SET status_validacao = 'Ativo', token_sessao = ? WHERE id = ?
    ''', (token_sessao, row['id']))
    conn.commit()
    conn.close()

    return jsonify({
        'message': 'Conta validada com sucesso! Bem-vindo(a).',
        'token': token_sessao,
        'cliente': {'id': row['id'], 'nome': row['nome'], 'email': row['email'], 'telefone': row['telefone']}
    })

@app.route('/api/auth/cliente/reenviar-codigo', methods=['POST'])
def auth_cliente_reenviar_codigo():
    data = request.json or {}
    cliente_id = data.get('cliente_id')
    email = data.get('email', '').strip().lower()

    if not cliente_id and not email:
        return jsonify({'error': 'Informe o ID ou E-mail do cliente.'}), 400

    conn = get_db()
    cursor = conn.cursor()
    if cliente_id:
        cursor.execute('SELECT * FROM clientes WHERE id = ?', (cliente_id,))
    else:
        cursor.execute('SELECT * FROM clientes WHERE email = ?', (email,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return jsonify({'error': 'Cliente nÃ£o encontrado.'}), 404

    novo_codigo = str(random.randint(100000, 999999))
    cursor.execute('UPDATE clientes SET codigo_validacao = ? WHERE id = ?', (novo_codigo, row['id']))
    conn.commit()
    conn.close()

    msg = f"ðŸ”’ *GrÃ¡fica RÃ¡pida Express*\nSeu novo cÃ³digo de validaÃ§Ã£o de cadastro Ã©: *{novo_codigo}*"
    sucesso, msg_status = send_evolution_whatsapp(row['telefone'], msg)

    res_data = {
        'message': 'Novo cÃ³digo de validaÃ§Ã£o enviado com sucesso!'
    }
    if not sucesso:
        res_data['codigo_dev'] = novo_codigo

    return jsonify(res_data)



@app.route('/api/auth/cliente/login', methods=['POST'])
def auth_cliente_login():
    data = request.json
    email = data.get('email', '').strip().lower()
    senha = data.get('senha', '')

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM clientes WHERE email = ?', (email,))
    row = cursor.fetchone()

    if not row or not check_password_hash(row['senha_hash'], senha):
        conn.close()
        return jsonify({'error': 'E-mail ou senha incorretos!'}), 401

    if row['status_validacao'] == 'Pendente':
        conn.close()
        return jsonify({
            'requer_validacao': True,
            'email': row['email'],
            'telefone': row['telefone'],
            'error': 'Sua conta ainda nÃ£o foi ativada. Digite o cÃ³digo de validaÃ§Ã£o do WhatsApp.'
        }), 403

    token_sessao = uuid.uuid4().hex
    cursor.execute('UPDATE clientes SET token_sessao = ? WHERE id = ?', (token_sessao, row['id']))
    conn.commit()
    conn.close()

    return jsonify({
        'message': 'Login realizado com sucesso!',
        'token': token_sessao,
        'cliente': {'id': row['id'], 'nome': row['nome'], 'email': row['email'], 'telefone': row['telefone'], 'endereco': row['endereco']}
    })

@app.route('/api/auth/cliente/me', methods=['GET'])
def auth_cliente_me():
    token = request.headers.get('X-Client-Token')
    cli = get_current_client(token)
    if not cli:
        return jsonify({'error': 'SessÃ£o expirada. FaÃ§a login novamente.'}), 401
    return jsonify(cli)

# --- APIS DE AUTENTICAÃ‡ÃƒO DO ADMINISTRADOR & TESTE EVOLUTION API ---

@app.route('/api/auth/admin/login', methods=['POST'])
def auth_admin_login():
    data = request.json
    usuario = data.get('usuario', '').strip()
    senha = data.get('senha', '')

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM usuarios_admin WHERE usuario = ?', (usuario,))
    row = cursor.fetchone()

    if not row or not check_password_hash(row['senha_hash'], senha):
        conn.close()
        return jsonify({'error': 'UsuÃ¡rio ou senha administrativos invÃ¡lidos!'}), 401

    token_sessao = uuid.uuid4().hex
    cursor.execute('UPDATE usuarios_admin SET token_sessao = ? WHERE id = ?', (token_sessao, row['id']))
    conn.commit()
    conn.close()

    return jsonify({
        'message': 'Login administrativo confirmado!',
        'admin_token': token_sessao,
        'admin': {'id': row['id'], 'usuario': row['usuario'], 'nome': row['nome']}
    })

@app.route('/api/auth/admin/me', methods=['GET'])
def auth_admin_me():
    token = request.headers.get('X-Admin-Token')
    adm = get_current_admin(token)
    if not adm:
        return jsonify({'error': 'Acesso negado.'}), 401
    return jsonify(adm)

@app.route('/api/admin/testar-evolution', methods=['POST'])
def testar_evolution_api():
    token = request.headers.get('X-Admin-Token')
    if not get_current_admin(token):
        return jsonify({'error': 'Acesso restrito ao administrador.'}), 403

    data = request.json or {}
    custom_url = data.get('url', '').strip()
    custom_key = data.get('key', '').strip()
    custom_instance = data.get('instance', '').strip()

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT whatsapp FROM configuracoes LIMIT 1')
    row = cursor.fetchone()
    whatsapp_grafica = row['whatsapp'] if row else '5511999998888'
    conn.close()

    msg = "ðŸš€ *GrÃ¡fica RÃ¡pida Express*\nTeste de conexÃ£o com a Evolution API realizado com sucesso!"
    
    sucesso, mensagem_retorno = send_evolution_whatsapp(
        whatsapp_grafica, 
        msg,
        custom_url=custom_url,
        custom_key=custom_key,
        custom_instance=custom_instance
    )

    if sucesso:
        return jsonify({
            'success': True, 
            'message': f"Teste de WhatsApp enviado com sucesso para {whatsapp_grafica}!",
            'resposta': mensagem_retorno
        })
    else:
        return jsonify({
            'success': False, 
            'error': f"Falha ao enviar via Evolution API: {mensagem_retorno}"
        }), 400

# --- APIS DO CLIENTE PROTEGIDAS ---

@app.route('/api/cliente/artes', methods=['GET', 'POST', 'DELETE'])
def api_cliente_artes():
    token = request.headers.get('X-Client-Token')
    cli = get_current_client(token)
    if not cli:
        return jsonify({'error': 'Acesso negado.'}), 401

    conn = get_db()
    cursor = conn.cursor()
    
    if request.method == 'GET':
        cursor.execute('SELECT * FROM cliente_artes WHERE cliente_id = ? ORDER BY id DESC', (cli['id'],))
        artes = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return jsonify(artes)

    elif request.method == 'POST':
        data = request.json
        cursor.execute('''
            INSERT INTO cliente_artes (cliente_id, nome_arquivo, url_arquivo, tamanho_bytes)
            VALUES (?, ?, ?, ?)
        ''', (cli['id'], data.get('nome_arquivo'), data.get('url_arquivo'), data.get('tamanho_bytes', 0)))
        conn.commit()
        arte_id = cursor.lastrowid
        conn.close()
        return jsonify({'message': 'Arte salva na biblioteca!', 'id': arte_id}), 201

    elif request.method == 'DELETE':
        arte_id = request.args.get('id')
        cursor.execute('DELETE FROM cliente_artes WHERE id = ? AND cliente_id = ?', (arte_id, cli['id']))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Arte removida!'})
@app.route('/api/cliente/orcamentos', methods=['GET'])
def get_cliente_meus_orcamentos():
    token = request.headers.get('X-Client-Token')
    cli = get_current_client(token)
    if not cli:
        return jsonify({'error': 'Acesso negado.'}), 401

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM orcamentos WHERE cliente_id = ? ORDER BY id DESC', (cli['id'],))
    rows = cursor.fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])
@app.route('/api/cliente/pedidos', methods=['GET'])
def get_cliente_meus_pedidos():
    token = request.headers.get('X-Client-Token')
    cli = get_current_client(token)
    if not cli:
        return jsonify({'error': 'Acesso negado.'}), 401

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM pedidos WHERE cliente_id = ? OR cliente_email = ? ORDER BY id DESC', (cli['id'], cli['email']))
    rows = cursor.fetchall()
    pedidos = []
    for r in rows:
        ped = dict(r)
        cursor.execute('SELECT * FROM itens_pedido WHERE pedido_id = ?', (ped['id'],))
        ped['itens'] = [dict(i) for i in cursor.fetchall()]
        pedidos.append(ped)
    conn.close()
    return jsonify(pedidos)

# --- PRODUTOS E CONFIGURAÃ‡Ã•ES ---

@app.route('/api/config', methods=['GET', 'PUT'])
def api_config():
    conn = get_db()
    cursor = conn.cursor()
    
    if request.method == 'GET':
        cursor.execute('SELECT * FROM configuracoes LIMIT 1')
        config = dict(cursor.fetchone())
        conn.close()
        return jsonify(config)
    
    elif request.method == 'PUT':
        token = request.headers.get('X-Admin-Token')
        if not get_current_admin(token):
            return jsonify({'error': 'Acesso restrito ao administrador.'}), 403

        data = request.json
        cursor.execute('''
            UPDATE configuracoes SET
                nome_grafica = ?, whatsapp = ?, chave_pix = ?, banner_titulo = ?,
                banner_subtitulo = ?, aviso_topo = ?, desconto_pix = ?, taxa_entrega = ?,
                evolution_api_url = ?, evolution_api_key = ?, evolution_instance = ?,
                validar_whatsapp_ativo = ?
            WHERE id = 1
        ''', (
            data.get('nome_grafica'), data.get('whatsapp'), data.get('chave_pix'),
            data.get('banner_titulo'), data.get('banner_subtitulo'), data.get('aviso_topo'),
            data.get('desconto_pix', 5.0), data.get('taxa_entrega', 15.0),
            data.get('evolution_api_url'), data.get('evolution_api_key'), data.get('evolution_instance'),
            1 if data.get('validar_whatsapp_ativo', True) else 0
        ))
        conn.commit()
        conn.close()
        return jsonify({'message': 'ConfiguraÃ§Ãµes e Evolution API salvas!'})

@app.route('/api/produtos', methods=['GET', 'POST'])
def api_produtos():
    conn = get_db()
    cursor = conn.cursor()
    
    if request.method == 'GET':
        incluir_inativos = request.args.get('admin', 'false') == 'true'
        if incluir_inativos:
            cursor.execute('SELECT * FROM produtos ORDER BY id DESC')
        else:
            cursor.execute('SELECT * FROM produtos WHERE ativo = 1 ORDER BY destaque DESC, id DESC')
        
        rows = cursor.fetchall()
        produtos = []
        for r in rows:
            p = dict(r)
            p['tamanhos'] = json.loads(p['tamanhos_json']) if p['tamanhos_json'] else []
            p['papeis'] = json.loads(p['papeis_json']) if p['papeis_json'] else []
            p['acabamentos'] = json.loads(p['acabamentos_json']) if p['acabamentos_json'] else []
            p['tiragens'] = json.loads(p['tiragens_json']) if p['tiragens_json'] else []
            produtos.append(p)
        conn.close()
        return jsonify(produtos)

    elif request.method == 'POST':
        token = request.headers.get('X-Admin-Token')
        if not get_current_admin(token):
            return jsonify({'error': 'Acesso restrito ao administrador.'}), 403

        data = request.json
        cursor.execute('''
            INSERT INTO produtos (nome, categoria, descricao, preco_base, imagem_url, tamanhos_json, papeis_json, acabamentos_json, tiragens_json, ativo, destaque)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('nome'), data.get('categoria'), data.get('descricao'),
            float(data.get('preco_base', 0)), data.get('imagem_url'),
            json.dumps(data.get('tamanhos', [])), json.dumps(data.get('papeis', [])),
            json.dumps(data.get('acabamentos', [])), json.dumps(data.get('tiragens', [])),
            1 if data.get('ativo', True) else 0, 1 if data.get('destaque', False) else 0
        ))
        conn.commit()
        prod_id = cursor.lastrowid
        conn.close()
        return jsonify({'message': 'Produto criado!', 'id': prod_id}), 201

@app.route('/api/produtos/<int:produto_id>', methods=['PUT', 'DELETE'])
def api_produto_detalhe(produto_id):
    token = request.headers.get('X-Admin-Token')
    if not get_current_admin(token):
        return jsonify({'error': 'Acesso restrito ao administrador.'}), 403

    conn = get_db()
    cursor = conn.cursor()

    if request.method == 'PUT':
        data = request.json
        cursor.execute('''
            UPDATE produtos 
            SET nome = ?, categoria = ?, descricao = ?, preco_base = ?, imagem_url = ?, 
                tamanhos_json = ?, papeis_json = ?, acabamentos_json = ?, tiragens_json = ?, ativo = ?, destaque = ?
            WHERE id = ?
        ''', (
            data.get('nome'), data.get('categoria'), data.get('descricao'),
            float(data.get('preco_base', 0)), data.get('imagem_url'),
            json.dumps(data.get('tamanhos', [])), json.dumps(data.get('papeis', [])),
            json.dumps(data.get('acabamentos', [])), json.dumps(data.get('tiragens', [])),
            1 if data.get('ativo', True) else 0, 1 if data.get('destaque', False) else 0,
            produto_id
        ))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Produto atualizado!'}), 200

    elif request.method == 'DELETE':
        cursor.execute('DELETE FROM produtos WHERE id = ?', (produto_id,))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Produto deletado!'}), 200

@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'Nenhum arquivo enviado'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Nome de arquivo invÃ¡lido'}), 400
    
    filename = f"{uuid.uuid4().hex[:8]}_{secure_filename(file.filename)}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    return jsonify({'url': f"/uploads/{filename}", 'filename': filename})

# --- PEDIDOS & CHECKOUT ---

@app.route('/api/pedidos', methods=['GET', 'POST'])
def api_pedidos():
    conn = get_db()
    cursor = conn.cursor()
    
    if request.method == 'GET':
        token = request.headers.get('X-Admin-Token')
        if not get_current_admin(token):
            return jsonify({'error': 'Acesso restrito ao administrador.'}), 403

        search = request.args.get('search', '')
        status = request.args.get('status', '')
        
        query = 'SELECT * FROM pedidos WHERE 1=1'
        params = []
        if search:
            query += ' AND (codigo_pedido LIKE ? OR cliente_nome LIKE ? OR cliente_telefone LIKE ?)'
            params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])
        if status and status != 'Todos':
            query += ' AND status_producao = ?'
            params.append(status)
            
        query += ' ORDER BY id DESC'
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        pedidos = []
        for r in rows:
            ped = dict(r)
            cursor.execute('SELECT * FROM itens_pedido WHERE pedido_id = ?', (ped['id'],))
            ped['itens'] = [dict(item) for item in cursor.fetchall()]
            pedidos.append(ped)
            
        conn.close()
        return jsonify(pedidos)

    elif request.method == 'POST':
        data = request.json
        cliente = data.get('cliente', {})
        itens = data.get('itens', [])
        cupom_codigo = data.get('cupom')
        
        if not cliente.get('nome') or not cliente.get('telefone'):
            return jsonify({'error': 'Nome e WhatsApp do cliente sÃ£o obrigatÃ³rios.'}), 400
        if not itens:
            return jsonify({'error': 'O carrinho estÃ¡ vazio.'}), 400
            
        cliente_id = None
        if cliente.get('email'):
            cursor.execute('SELECT id FROM clientes WHERE email = ?', (cliente.get('email').strip().lower(),))
            c_row = cursor.fetchone()
            if c_row:
                cliente_id = c_row['id']
                
        codigo_pedido = f"#GF-{datetime.now().strftime('%m%d')}{uuid.uuid4().hex[:4].upper()}"
        
        total = float(data.get('total', 0))
        desconto = float(data.get('desconto', 0))
        taxa_entrega = float(data.get('taxa_entrega', 0))
        metodo_pagamento = data.get('metodo_pagamento', 'PIX')
        tipo_entrega = data.get('tipo_entrega', 'Balcao')
        endereco_entrega = data.get('endereco_entrega', '')
        observacoes = data.get('observacoes', '')
        
        status_pag = 'Aprovado' if metodo_pagamento == 'Cartao' else 'Aguardando Pagamento'
        status_prod = 'Em AnÃ¡lise de Arte' if status_pag == 'Aprovado' else 'Aguardando Pagamento'

        cursor.execute('''
            INSERT INTO pedidos (
                codigo_pedido, cliente_id, cliente_nome, cliente_telefone, cliente_email,
                total, desconto, taxa_entrega, metodo_pagamento, status_pagamento, status_producao,
                tipo_entrega, endereco_entrega, observacoes, cupom_aplicado
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            codigo_pedido, cliente_id, cliente.get('nome'), cliente.get('telefone'), cliente.get('email'),
            total, desconto, taxa_entrega, metodo_pagamento, status_pag, status_prod,
            tipo_entrega, endereco_entrega, observacoes, cupom_codigo
        ))
        
        pedido_id = cursor.lastrowid
        
        for it in itens:
            cursor.execute('''
                INSERT INTO itens_pedido (
                    pedido_id, produto_id, produto_nome, tamanho, papel, acabamento,
                    quantidade, preco_unitario, preco_total, arte_url, criar_arte, detalhes_arte
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                pedido_id, it.get('produto_id'), it.get('produto_nome'), it.get('tamanho'),
                it.get('papel'), it.get('acabamento'), int(it.get('quantidade', 1)),
                float(it.get('preco_unitario', 0)), float(it.get('preco_total', 0)),
                it.get('arte_url'), 1 if it.get('criar_arte') else 0, it.get('detalhes_arte', '')
            ))

        if status_pag == 'Aprovado':
            cursor.execute('''
                INSERT INTO caixa_movimentacoes (tipo, categoria, descricao, valor, forma_pagamento, pedido_id)
                VALUES ('ENTRADA', 'Venda Pedido', ?, ?, ?, ?)
            ''', (f"Venda Pedido {codigo_pedido}", total, metodo_pagamento, pedido_id))

        if cupom_codigo:
            cursor.execute('UPDATE cupons SET usos_atuais = usos_atuais + 1 WHERE codigo = ?', (cupom_codigo,))

        conn.commit()
        conn.close()

        # Notificar novo pedido no WhatsApp do cliente via Evolution API
        msg_cliente = f"ðŸ›ï¸ *GrÃ¡fica RÃ¡pida Express*\nOlÃ¡ {cliente.get('nome')}! Seu pedido *{codigo_pedido}* foi recebido com sucesso!\nTotal: R$ {total:.2f}\nStatus: {status_prod}"
        send_evolution_whatsapp(cliente.get('telefone'), msg_cliente)

        return jsonify({
            'message': 'Pedido realizado com sucesso!',
            'pedido_id': pedido_id,
            'codigo_pedido': codigo_pedido
        }), 201

@app.route('/api/pedidos/<codigo>', methods=['GET'])
def get_pedido_by_codigo(codigo):
    if not codigo.startswith('#'):
        codigo = '#' + codigo
        
    conn = get_db()
    cursor = conn.cursor()
    if codigo.lstrip('#').isdigit():
        # Searching by ID (numeric)
        cursor.execute('SELECT * FROM pedidos WHERE id = ? OR codigo_pedido = ?', (int(codigo.lstrip('#')), codigo))
    else:
        # Searching by codigo_pedido (string)
        cursor.execute('SELECT * FROM pedidos WHERE codigo_pedido = ?', (codigo,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'Pedido nÃ£o encontrado'}), 404
        
    ped = dict(row)
    cursor.execute('SELECT * FROM itens_pedido WHERE pedido_id = ?', (ped['id'],))
    ped['itens'] = [dict(i) for i in cursor.fetchall()]
    conn.close()
    return jsonify(ped)

@app.route('/api/pedidos/<int:pedido_id>/status', methods=['PUT'])
def update_pedido_status(pedido_id):
    token = request.headers.get('X-Admin-Token')
    if not get_current_admin(token):
        return jsonify({'error': 'Acesso restrito ao administrador.'}), 403

    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    
    status_producao = data.get('status_producao')
    status_pagamento = data.get('status_pagamento')
    
    cursor.execute('SELECT * FROM pedidos WHERE id = ?', (pedido_id,))
    ped = cursor.fetchone()
    if not ped:
        conn.close()
        return jsonify({'error': 'Pedido nÃ£o encontrado'}), 404
        
    ped_dict = dict(ped)
    
    if status_pagamento == 'Aprovado' and ped_dict['status_pagamento'] != 'Aprovado':
        cursor.execute('''
            INSERT INTO caixa_movimentacoes (tipo, categoria, descricao, valor, forma_pagamento, pedido_id)
            VALUES ('ENTRADA', 'Venda Pedido', ?, ?, ?, ?)
        ''', (f"Pagamento Confirmado {ped_dict['codigo_pedido']}", ped_dict['total'], ped_dict['metodo_pagamento'], pedido_id))

    cursor.execute('''
        UPDATE pedidos SET
            status_producao = COALESCE(?, status_producao),
            status_pagamento = COALESCE(?, status_pagamento),
            data_atualizacao = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (status_producao, status_pagamento, pedido_id))
    
    conn.commit()
    conn.close()

    # Notificar alteraÃ§Ã£o de status no WhatsApp
    if status_producao:
        msg_update = f"ðŸ“¦ *GrÃ¡fica RÃ¡pida Express*\nSeu pedido *{ped_dict['codigo_pedido']}* teve o status atualizado para: *{status_producao}*!"
        send_evolution_whatsapp(ped_dict['cliente_telefone'], msg_update)

    return jsonify({'message': 'Status do pedido atualizado!'})

# --- ESTOQUE, ORÃ‡AMENTOS E CUPONS ---

@app.route('/api/estoque', methods=['GET', 'POST', 'PUT', 'DELETE'])
def api_estoque():
    token = request.headers.get('X-Admin-Token')
    if not get_current_admin(token):
        return jsonify({'error': 'Acesso restrito ao administrador.'}), 403

    conn = get_db()
    cursor = conn.cursor()
    
    if request.method == 'GET':
        cursor.execute('SELECT * FROM estoque_insumos ORDER BY quantidade_atual ASC')
        insumos = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return jsonify(insumos)

    elif request.method == 'POST':
        data = request.json
        cursor.execute('''
            INSERT INTO estoque_insumos (nome_insumo, categoria, quantidade_atual, quantidade_minima, unidade_medida, custo_unitario)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (data.get('nome_insumo'), data.get('categoria'), float(data.get('quantidade_atual', 0)), float(data.get('quantidade_minima', 0)), data.get('unidade_medida', 'Unidades'), float(data.get('custo_unitario', 0))))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Insumo cadastrado!'}), 201

    elif request.method == 'PUT':
        data = request.json
        cursor.execute('''
            UPDATE estoque_insumos SET quantidade_atual = ?, quantidade_minima = ? WHERE id = ?
        ''', (float(data.get('quantidade_atual')), float(data.get('quantidade_minima')), data.get('id')))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Estoque atualizado!'})

@app.route('/api/orcamentos', methods=['GET', 'POST', 'PUT'])
def api_orcamentos():
    conn = get_db()
    cursor = conn.cursor()
    
    if request.method == 'GET':
        token = request.headers.get('X-Admin-Token')
        if not get_current_admin(token):
            return jsonify({'error': 'Acesso restrito ao administrador.'}), 403
        cursor.execute('SELECT * FROM orcamentos ORDER BY id DESC')
        orc = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return jsonify(orc)

    elif request.method == 'POST':
        data = request.json
        codigo = f"#ORC-{datetime.now().strftime('%m%d')}{uuid.uuid4().hex[:4].upper()}"
        cursor.execute('''
            INSERT INTO orcamentos (codigo_orcamento, cliente_id, cliente_nome, cliente_telefone, descricao, valor_estimado, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (codigo, data.get('cliente_id'), data.get('cliente_nome'), data.get('cliente_telefone'), data.get('descricao'), float(data.get('valor_estimado', 0)), 'Pendente'))
        conn.commit()
        orc_id = cursor.lastrowid
        conn.close()

        # Send WhatsApp message
        telefone = data.get('cliente_telefone')
        if telefone:
            msg_cliente = f"ðŸ“‹ *GrÃ¡fica RÃ¡pida Express*\nOlÃ¡ {data.get('cliente_nome')}! Sua solicitaÃ§Ã£o de orÃ§amento *{codigo}* foi recebida com sucesso!\nDetalhes: {data.get('descricao')}\nEm breve entraremos em contato com o valor!"
            send_evolution_whatsapp(telefone, msg_cliente)

        return jsonify({'message': 'OrÃ§amento criado!', 'id': orc_id, 'codigo': codigo}), 201

@app.route('/api/orcamentos/<int:orc_id>', methods=['PUT', 'DELETE'])
def api_orcamento_edit(orc_id):
    token = request.headers.get('X-Admin-Token')
    if not get_current_admin(token):
        return jsonify({'error': 'Acesso restrito ao administrador.'}), 403

    conn = get_db()
    cursor = conn.cursor()

    if request.method == 'PUT':
        data = request.json
        cursor.execute('''
            UPDATE orcamentos 
            SET cliente_nome = ?, cliente_telefone = ?, descricao = ?, valor_estimado = ?, status = ?
            WHERE id = ?
        ''', (data.get('cliente_nome'), data.get('cliente_telefone'), data.get('descricao'), float(data.get('valor_estimado', 0)), data.get('status', 'Pendente'), orc_id))
        conn.commit()
        conn.close()
        return jsonify({'message': 'OrÃ§amento atualizado com sucesso!'})

    elif request.method == 'DELETE':
        cursor.execute('DELETE FROM orcamentos WHERE id = ?', (orc_id,))
        conn.commit()
        conn.close()
        return jsonify({'message': 'OrÃ§amento excluÃ­do com sucesso!'})

@app.route('/api/cupons', methods=['GET', 'POST', 'DELETE'])
def api_cupons():
    conn = get_db()
    cursor = conn.cursor()
    
    if request.method == 'GET':
        cursor.execute('SELECT * FROM cupons ORDER BY id DESC')
        cupons = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return jsonify(cupons)

    elif request.method == 'POST':
        token = request.headers.get('X-Admin-Token')
        if not get_current_admin(token):
            return jsonify({'error': 'Acesso restrito ao administrador.'}), 403

        data = request.json
        cursor.execute('''
            INSERT INTO cupons (codigo, porcentagem_desconto, valor_minimo, limite_usos)
            VALUES (?, ?, ?, ?)
        ''', (data.get('codigo').upper().strip(), float(data.get('porcentagem_desconto', 10)), float(data.get('valor_minimo', 0)), int(data.get('limite_usos', 100))))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Cupom criado!'}), 201

    elif request.method == 'DELETE':
        token = request.headers.get('X-Admin-Token')
        if not get_current_admin(token):
            return jsonify({'error': 'Acesso restrito ao administrador.'}), 403
        cupom_id = request.args.get('id')
        cursor.execute('DELETE FROM cupons WHERE id = ?', (cupom_id,))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Cupom removido!'})

@app.route('/api/cupons/validar', methods=['POST'])
def validar_cupom():
    data = request.json
    codigo = data.get('codigo', '').upper().strip()
    subtotal = float(data.get('subtotal', 0))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM cupons WHERE codigo = ? AND ativo = 1', (codigo,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return jsonify({'valid': False, 'message': 'Cupom invÃ¡lido ou expirado.'}), 404
        
    cupom = dict(row)
    if subtotal < cupom['valor_minimo']:
        return jsonify({'valid': False, 'message': f"Valor mÃ­nimo do cupom Ã© R$ {cupom['valor_minimo']:.2f}"}), 400

    if cupom['usos_atuais'] >= cupom['limite_usos']:
        return jsonify({'valid': False, 'message': 'Limite de uso deste cupom esgotado.'}), 400

    desconto_valor = subtotal * (cupom['porcentagem_desconto'] / 100.0)
    return jsonify({
        'valid': True,
        'codigo': cupom['codigo'],
        'porcentagem': cupom['porcentagem_desconto'],
        'desconto_valor': desconto_valor,
        'message': f"Cupom de {cupom['porcentagem_desconto']}% aplicado!"
    })

# --- CAIXA & DASHBOARD ---

@app.route('/api/caixa/resumo', methods=['GET'])
def get_caixa_resumo():
    token = request.headers.get('X-Admin-Token')
    if not get_current_admin(token):
        return jsonify({'error': 'Acesso restrito ao administrador.'}), 403

    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COALESCE(SUM(valor), 0) FROM caixa_movimentacoes WHERE tipo = 'ENTRADA'")
    r_ent = cursor.fetchone()
    total_entradas = float(r_ent[0]) if r_ent and r_ent[0] is not None else 0.0
    
    cursor.execute("SELECT COALESCE(SUM(valor), 0) FROM caixa_movimentacoes WHERE tipo = 'SAIDA'")
    r_sai = cursor.fetchone()
    total_saidas = float(r_sai[0]) if r_sai and r_sai[0] is not None else 0.0
    
    saldo_atual = total_entradas - total_saidas
    
    cursor.execute('SELECT * FROM caixa_movimentacoes ORDER BY id DESC LIMIT 50')
    movimentacoes = [dict(r) for r in cursor.fetchall()]
    
    conn.close()
    return jsonify({
        'total_entradas': total_entradas,
        'total_saidas': total_saidas,
        'saldo_atual': saldo_atual,
        'movimentacoes': movimentacoes
    })

@app.route('/api/caixa/movimento', methods=['POST'])
def add_caixa_movimento():
    token = request.headers.get('X-Admin-Token')
    if not get_current_admin(token):
        return jsonify({'error': 'Acesso restrito ao administrador.'}), 403

    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    
    valor = float(data.get('valor', 0))
    if valor <= 0:
        return jsonify({'error': 'Valor deve ser maior que zero'}), 400
        
    cursor.execute('''
        INSERT INTO caixa_movimentacoes (tipo, categoria, descricao, valor, forma_pagamento)
        VALUES (?, ?, ?, ?, ?)
    ''', (data.get('tipo'), data.get('categoria', 'Geral'), data.get('descricao', ''), valor, data.get('forma_pagamento', 'Dinheiro')))
    
    conn.commit()
    conn.close()
    return jsonify({'message': 'MovimentaÃ§Ã£o registrada!'})

@app.route('/api/clientes/<int:cliente_id>', methods=['PUT'])
def edit_cliente(cliente_id):
    token = request.headers.get('X-Admin-Token')
    if not get_current_admin(token):
        return jsonify({'error': 'Acesso restrito ao administrador.'}), 403

    data = request.json
    nome = data.get('nome')
    email = data.get('email')
    telefone = data.get('telefone')
    endereco = data.get('endereco', '')
    cpf_cnpj = data.get('cpf_cnpj', '')

    if not nome or not email or not telefone:
        return jsonify({'error': 'Nome, E-mail e Telefone sÃ£o obrigatÃ³rios'}), 400

    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT id FROM clientes WHERE email = ? AND id != ?', (email, cliente_id))
    if cursor.fetchone():
        conn.close()
        return jsonify({'error': 'E-mail jÃ¡ estÃ¡ em uso por outro cliente'}), 400

    cursor.execute('''
        UPDATE clientes 
        SET nome = ?, email = ?, telefone = ?, endereco = ?, cpf_cnpj = ?
        WHERE id = ?
    ''', (nome, email, telefone, endereco, cpf_cnpj, cliente_id))
    
    conn.commit()
    conn.close()
    return jsonify({'message': 'Cliente atualizado com sucesso!'})

@app.route('/api/clientes/<int:cliente_id>', methods=['DELETE'])
def delete_cliente(cliente_id):
    token = request.headers.get('X-Admin-Token')
    if not get_current_admin(token):
        return jsonify({'error': 'Acesso restrito ao administrador.'}), 403

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM clientes WHERE id = ?', (cliente_id,))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Cliente excluÃ­do com sucesso!'})

@app.route('/api/clientes', methods=['GET'])
def get_clientes():
    token = request.headers.get('X-Admin-Token')
    if not get_current_admin(token):
        return jsonify({'error': 'Acesso restrito ao administrador.'}), 403

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT c.*, 
               COUNT(p.id) as total_pedidos, 
               COALESCE(SUM(p.total), 0) as total_gasto
        FROM clientes c
        LEFT JOIN pedidos p ON c.id = p.cliente_id
        GROUP BY c.id
        ORDER BY total_gasto DESC
    ''')
    clientes = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify(clientes)

@app.route('/api/dashboard', methods=['GET'])
def get_dashboard_metrics():
    token = request.headers.get('X-Admin-Token')
    if not get_current_admin(token):
        return jsonify({'error': 'Acesso restrito ao administrador.'}), 403

    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM pedidos")
    r1 = cursor.fetchone()
    total_pedidos = int(r1[0]) if r1 and r1[0] is not None else 0
    
    cursor.execute("SELECT COUNT(*) FROM pedidos WHERE status_producao IN ('Aguardando Pagamento', 'Em AnÃ¡lise de Arte', 'Em ImpressÃ£o', 'Acabamento & Corte')")
    r2 = cursor.fetchone()
    pedidos_em_producao = int(r2[0]) if r2 and r2[0] is not None else 0
    
    cursor.execute("SELECT COALESCE(SUM(total), 0) FROM pedidos WHERE status_pagamento = 'Aprovado'")
    r3 = cursor.fetchone()
    faturamento_total = float(r3[0]) if r3 and r3[0] is not None else 0.0
    
    cursor.execute("SELECT COUNT(*) FROM clientes")
    r4 = cursor.fetchone()
    total_clientes = int(r4[0]) if r4 and r4[0] is not None else 0
    
    cursor.execute('''
        SELECT DATE(data_criacao) as dia, SUM(total) as total
        FROM pedidos
        WHERE status_pagamento = 'Aprovado'
        GROUP BY DATE(data_criacao)
        ORDER BY dia DESC LIMIT 7
    ''')
    rows_vendas = cursor.fetchall()
    vendas_dia = []
    for r in rows_vendas:
        vendas_dia.append({
            'dia': str(r['dia']) if r.get('dia') is not None else '',
            'total': float(r['total']) if r.get('total') is not None else 0.0
        })

    conn.close()
    return jsonify({
        'total_pedidos': total_pedidos,
        'pedidos_em_producao': pedidos_em_producao,
        'faturamento_total': faturamento_total,
        'total_clientes': total_clientes,
        'vendas_dia': vendas_dia
    })


# --- APIS DO CHAT INTERNO & WEBHOOK ---

@app.route('/api/chat/<path:codigo>', methods=['GET'])
def api_chat_get(codigo):
    token_admin = request.headers.get('X-Admin-Token')
    token_cliente = request.headers.get('X-Client-Token')
    
    if not token_admin and not token_cliente:
        return jsonify({'error': 'Acesso negado'}), 401
        
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM mensagens_chat WHERE referencia_codigo = ? ORDER BY data_envio ASC', (codigo,))
    mensagens = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify(mensagens)

@app.route('/api/chat/<path:codigo>', methods=['POST'])
def api_chat_post(codigo):
    try:
        token_admin = request.headers.get('X-Admin-Token')
        token_cliente = request.headers.get('X-Client-Token')
        
        if not token_admin and not token_cliente:
            return jsonify({'error': 'Acesso negado'}), 401
            
        data = request.json
        mensagem = data.get('mensagem', '').strip()
        telefone = data.get('telefone', '')
        
        if not mensagem:
            return jsonify({'error': 'Mensagem vazia'}), 400
            
        remetente_tipo = 'admin' if token_admin else 'cliente'
        
        if remetente_tipo == 'admin':
            admin = get_current_admin(token_admin)
            remetente_nome = admin['nome'] if admin else 'Atendimento'
        else:
            cli = get_current_client(token_cliente)
            remetente_nome = cli['nome'] if cli else 'Cliente'
            
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO mensagens_chat (referencia_codigo, remetente_tipo, remetente_nome, telefone_cliente, mensagem)
            VALUES (?, ?, ?, ?, ?)
        ''', (codigo, remetente_tipo, remetente_nome, telefone, mensagem))
        conn.commit()
        conn.close()
        
        conn = get_db()
        cursor = conn.cursor()
        
        # LÃ³gica de NotificaÃ§Ã£o de 15 Minutos
        enviar_notificacao = False
        from datetime import datetime, timedelta
        
        # 1. Busca a Ãºltima mensagem do destinatÃ¡rio (para ver se ele estÃ¡ online/ativo)
        tipo_destinatario = 'cliente' if remetente_tipo == 'admin' else 'admin'
        if cursor.is_postgres:
            cursor.execute("SELECT data_envio FROM mensagens_chat WHERE referencia_codigo = %s AND remetente_tipo = %s ORDER BY id DESC LIMIT 1", (codigo, tipo_destinatario))
        else:
            cursor.execute("SELECT data_envio FROM mensagens_chat WHERE referencia_codigo = ? AND remetente_tipo = ? ORDER BY id DESC LIMIT 1", (codigo, tipo_destinatario))
        last_destinatario = cursor.fetchone()
        
        # 2. Busca a Ãºltima mensagem do remetente (para ver se jÃ¡ notificamos hÃ¡ pouco tempo)
        if cursor.is_postgres:
            cursor.execute("SELECT data_envio FROM mensagens_chat WHERE referencia_codigo = %s AND remetente_tipo = %s ORDER BY id DESC LIMIT 1 OFFSET 1", (codigo, remetente_tipo))
        else:
            cursor.execute("SELECT data_envio FROM mensagens_chat WHERE referencia_codigo = ? AND remetente_tipo = ? ORDER BY id DESC LIMIT 1 OFFSET 1", (codigo, remetente_tipo))
        last_remetente = cursor.fetchone()
        
        conn.close()

        def foi_recente(row):
            if not row: return False
            dt_str = dict(row).get('data_envio') if hasattr(row, 'keys') else row[0]
            if not dt_str: return False
            try:
                if isinstance(dt_str, str):
                    last_time = datetime.strptime(dt_str.split('.')[0], "%Y-%m-%d %H:%M:%S")
                else:
                    last_time = dt_str
                return (datetime.now() - last_time).total_seconds() < 900 # 15 min
            except:
                return False

        if not foi_recente(last_destinatario) and not foi_recente(last_remetente):
            enviar_notificacao = True

        if enviar_notificacao:
            if remetente_tipo == 'admin' and telefone:
                # O admin nÃ£o envia link do site para ele responder se for um chat GERAL
                if codigo == 'GERAL':
                    msg_wpp = f"ðŸ’¬ *GrÃ¡fica RÃ¡pida Express*\n\n_{mensagem}_"
                else:
                    msg_wpp = f"ðŸ’¬ *GrÃ¡fica RÃ¡pida Express*\nNova mensagem sobre o {codigo}:\n\n_{mensagem}_\n\nAcesse o site para responder!"
                send_evolution_whatsapp(telefone, msg_wpp)
                
            if remetente_tipo == 'cliente':
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute('SELECT whatsapp FROM configuracoes LIMIT 1')
                cfg = cursor.fetchone()
                conn.close()
                if cfg and dict(cfg).get('whatsapp'):
                    msg_wpp_admin = f"ðŸ”” *Alerta de Mensagem*\nO cliente {remetente_nome} enviou uma mensagem sobre o {codigo}:\n\n_{mensagem}_\n\nAcesse o painel para responder!"
                    send_evolution_whatsapp(dict(cfg)['whatsapp'], msg_wpp_admin)
                    
        return jsonify({'message': 'Mensagem enviada'})
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500

@app.route('/api/webhook/evolution', methods=['POST'])
def webhook_evolution():
    # Recebe mensagens do cliente pelo WhatsApp e joga no chat do pedido
    # OBS: O Evolution API manda payloads diferentes dependendo da versÃ£o, 
    # estamos usando um genÃ©rico que tenta encontrar o remoteJid e text.
    try:
        data = request.json
        if not data:
            return jsonify({'status': 'ignorado'}), 200
            
        messages = data.get('data', {}).get('message', {})
        if not messages:
            return jsonify({'status': 'ignorado'}), 200
            
        remote_jid = data.get('data', {}).get('key', {}).get('remoteJid', '')
        text = messages.get('conversation') or messages.get('extendedTextMessage', {}).get('text')
        
        if not remote_jid or not text:
            return jsonify({'status': 'ignorado'}), 200
            
        # Pega o telefone (tira o @s.whatsapp.net)
        telefone = remote_jid.split('@')[0]
        
        # Ignora mensagens de nÃ³s mesmos (se o remetente for fromMe = true, embora dependa do payload)
        if data.get('data', {}).get('key', {}).get('fromMe'):
            return jsonify({'status': 'ignorado, fromMe'}), 200

        import re
        from datetime import datetime, timedelta
        
        match = re.search(r'(#[A-Z]+-[A-Z0-9]+)', text.upper())
        codigo = match.group(1) if match else f"GERAL"
        
        conn = get_db()
        cursor = conn.cursor()
        
        # 1. Salva a mensagem recebida
        cursor.execute('''
            INSERT INTO mensagens_chat (referencia_codigo, remetente_tipo, remetente_nome, telefone_cliente, mensagem)
            VALUES (?, 'cliente', 'Cliente (Via WhatsApp)', ?, ?)
        ''', (codigo, telefone, text))
        conn.commit()

        # 2. AutomaÃ§Ã£o do Bot
        if codigo != "GERAL":
            # Tentar achar o status do pedido/orÃ§amento
            prefix = codigo.split('-')[0]
            status_msg = ""
            if prefix == "#PED":
                cursor.execute('SELECT status_producao, total FROM pedidos WHERE codigo_pedido = ?', (codigo,))
                row = cursor.fetchone()
                if row:
                    row_dict = dict(row) if hasattr(row, 'keys') else {'status_producao': row[0], 'total': row[1]}
                    status_msg = f"Seu pedido {codigo} estÃ¡ atualmente: *{row_dict['status_producao']}*.\nValor total: R$ {row_dict['total']:.2f}".replace('.', ',')
            elif prefix == "#ORC":
                cursor.execute('SELECT status, valor_estimado FROM orcamentos WHERE codigo_orcamento = ?', (codigo,))
                row = cursor.fetchone()
                if row:
                    row_dict = dict(row) if hasattr(row, 'keys') else {'status': row[0], 'valor_estimado': row[1]}
                    status_msg = f"Seu orÃ§amento {codigo} estÃ¡: *{row_dict['status']}*.\nValor estimado: R$ {row_dict['valor_estimado']:.2f}".replace('.', ',')
            
            if status_msg:
                bot_reply = f"ðŸ¤– *Assistente AutomÃ¡tico*\nOlÃ¡! Encontrei as informaÃ§Ãµes solicitadas:\n\n{status_msg}\n\nSe precisar falar com um humano, mande outra mensagem."
                send_evolution_whatsapp(telefone, bot_reply)
                # Opcional: salvar a resposta do bot no chat
                cursor.execute("INSERT INTO mensagens_chat (referencia_codigo, remetente_tipo, remetente_nome, telefone_cliente, mensagem) VALUES (?, 'admin', 'Assistente Virtual', ?, ?)", (codigo, telefone, bot_reply))
                conn.commit()
        else:
            # Fluxo sem cÃ³digo especÃ­fico (Fallback)
            # Verifica a Ãºltima mensagem que nÃ³s (admin/bot) enviamos para esse telefone nos Ãºltimos 30 min
            if cursor.is_postgres:
                cursor.execute("SELECT data_envio FROM mensagens_chat WHERE telefone_cliente = %s AND remetente_tipo = 'admin' ORDER BY id DESC LIMIT 1", (telefone,))
            else:
                cursor.execute("SELECT data_envio FROM mensagens_chat WHERE telefone_cliente = ? AND remetente_tipo = 'admin' ORDER BY id DESC LIMIT 1", (telefone,))
            
            last_admin = cursor.fetchone()
            enviar_saudacao = True
            
            if last_admin:
                dt_str = dict(last_admin).get('data_envio') if hasattr(last_admin, 'keys') else last_admin[0]
                if dt_str:
                    try:
                        if isinstance(dt_str, str):
                            last_time = datetime.strptime(dt_str.split('.')[0], "%Y-%m-%d %H:%M:%S")
                        else:
                            last_time = dt_str # it's already a datetime object in psycopg2
                        if (datetime.now() - last_time).total_seconds() < 1800: # 30 min
                            enviar_saudacao = False
                    except:
                        pass
            
            if enviar_saudacao:
                fallback_msg = "ðŸ¤– *Assistente AutomÃ¡tico*\nOlÃ¡! Recebemos sua mensagem. Se deseja saber sobre um pedido, digite o cÃ³digo (ex: #PED-123).\n\nCaso contrÃ¡rio, aguarde um instante que um atendente humano jÃ¡ falarÃ¡ com vocÃª!"
                send_evolution_whatsapp(telefone, fallback_msg)
                cursor.execute("INSERT INTO mensagens_chat (referencia_codigo, remetente_tipo, remetente_nome, telefone_cliente, mensagem) VALUES (?, 'admin', 'Assistente Virtual', ?, ?)", (codigo, telefone, fallback_msg))
                conn.commit()

        conn.close()
        return jsonify({'status': 'sucesso'})
    except Exception as e:
        import traceback
        print("Erro Webhook:", traceback.format_exc())
        return jsonify({'error': str(e)}), 500


@app.route("/api/chat/inbox", methods=["GET"])
def api_chat_inbox():
    token_admin = request.headers.get('X-Admin-Token')
    if not get_current_admin(token_admin):
        return jsonify({'error': 'Acesso restrito ao administrador.'}), 403
    # Retorna as conversas mais recentes agrupadas por referencia_codigo ou telefone
    conn = get_db()
    cursor = conn.cursor()
    if cursor.is_postgres:
        cursor.execute("""
            SELECT DISTINCT ON (referencia_codigo, telefone_cliente) 
                referencia_codigo, telefone_cliente, remetente_nome, mensagem, data_envio, lida, remetente_tipo
            FROM mensagens_chat 
            ORDER BY referencia_codigo, telefone_cliente, id DESC
        """)
    else:
        cursor.execute("""
            SELECT referencia_codigo, telefone_cliente, remetente_nome, mensagem, data_envio, lida, remetente_tipo
            FROM mensagens_chat 
            GROUP BY referencia_codigo, telefone_cliente
            ORDER BY max(id) DESC
        """)
    
    rows = cursor.fetchall()
    
    # Ordenar por data_envio decrescente no Postgres tambem
    def get_data(r):
        return dict(r).get("data_envio") if hasattr(r, "keys") else r[4]
    
    try:
        rows = sorted(rows, key=lambda x: str(get_data(x)), reverse=True)
    except:
        pass
        
    inbox = []
    for r in rows:
        d = dict(r) if hasattr(r, "keys") else {
            "referencia_codigo": r[0], "telefone_cliente": r[1], 
            "remetente_nome": r[2], "mensagem": r[3], 
            "data_envio": r[4], "lida": r[5], "remetente_tipo": r[6]
        }
        
        # Pega a contagem de nao lidas para este chat
        if cursor.is_postgres:
            cursor.execute("SELECT COUNT(*) FROM mensagens_chat WHERE referencia_codigo = %s AND telefone_cliente = %s AND remetente_tipo = %s AND lida = 0", (d["referencia_codigo"], d["telefone_cliente"], "cliente"))
        else:
            cursor.execute("SELECT COUNT(*) FROM mensagens_chat WHERE referencia_codigo = ? AND telefone_cliente = ? AND remetente_tipo = ? AND lida = 0", (d["referencia_codigo"], d["telefone_cliente"], "cliente"))
        
        c_row = cursor.fetchone()
        d["nao_lidas"] = c_row[0] if c_row else 0
        inbox.append(d)
        
    conn.close()
    return jsonify(inbox)

@app.route("/api/chat/unread/admin", methods=["GET"])
def api_chat_unread_admin():
    token_admin = request.headers.get('X-Admin-Token')
    if not get_current_admin(token_admin):
        return jsonify({'error': 'Acesso restrito ao administrador.'}), 403
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM mensagens_chat WHERE remetente_tipo = %s AND lida = 0" if cursor.is_postgres else "SELECT COUNT(*) FROM mensagens_chat WHERE remetente_tipo = ? AND lida = 0", ("cliente",))
    count = cursor.fetchone()[0]
    conn.close()
    return jsonify({"unread": count})

@app.route("/api/chat/unread/cliente", methods=["GET"])
def api_chat_unread_cliente():
    cli = get_current_client(request.headers.get("X-Client-Token"))
    if not cli:
        return jsonify({'error': 'Acesso negado.'}), 403
    conn = get_db()
    cursor = conn.cursor()
    telefone = cli["telefone"]
    if cursor.is_postgres:
        cursor.execute("SELECT COUNT(*) FROM mensagens_chat WHERE remetente_tipo = %s AND lida = 0 AND telefone_cliente = %s", ("admin", telefone))
    else:
        cursor.execute("SELECT COUNT(*) FROM mensagens_chat WHERE remetente_tipo = ? AND lida = 0 AND telefone_cliente = ?", ("admin", telefone))
    count = cursor.fetchone()[0]
    conn.close()
    return jsonify({"unread": count})

@app.route("/api/chat/<path:codigo>/read", methods=["POST"])
def api_chat_read(codigo):
    token_admin = request.headers.get("X-Admin-Token")
    token_cliente = request.headers.get("X-Client-Token")
    if not token_admin and not token_cliente:
        return jsonify({"error": "Acesso negado"}), 401
        
    remetente_esperado = "cliente" if token_admin else "admin"
    telefone = request.json.get("telefone", "")
    
    conn = get_db()
    cursor = conn.cursor()
    if cursor.is_postgres:
        query = "UPDATE mensagens_chat SET lida = 1 WHERE referencia_codigo = %s AND remetente_tipo = %s"
        params = [codigo, remetente_esperado]
        if telefone:
            query += " AND telefone_cliente = %s"
            params.append(telefone)
        cursor.execute(query, tuple(params))
    else:
        query = "UPDATE mensagens_chat SET lida = 1 WHERE referencia_codigo = ? AND remetente_tipo = ?"
        params = [codigo, remetente_esperado]
        if telefone:
            query += " AND telefone_cliente = ?"
            params.append(telefone)
        cursor.execute(query, tuple(params))
    conn.commit()
    conn.close()
    return jsonify({"status": "lidas"})

if __name__ == '__main__':
    print("=" * 60)
    print(" GRAFICA RAPIDA EXPRESS - SERVIDOR INICIALIZADO ")
    print(" Acesse a aplicacao em: http://127.0.0.1:8050")
    print("=" * 60)
    app.run(host='0.0.0.0', port=8050, debug=False)

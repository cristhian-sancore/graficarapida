# -*- coding: utf-8 -*-
from flask import Blueprint, request, jsonify, g, has_request_context
import time, json, urllib.request, ssl, os, uuid
from datetime import datetime

whatsapp_bp = Blueprint('whatsapp', __name__)
ctx_unverified = ssl._create_unverified_context()


def get_current_client(*args, **kwargs):
    from app import get_current_client as _get
    return _get(*args, **kwargs)

def send_evolution_whatsapp(*args, **kwargs):
    from app import send_evolution_whatsapp as _send
    return _send(*args, **kwargs)

def get_db():
    from app import get_db as _get_db
    return _get_db()

def upload_file_to_r2(*args, **kwargs):
    from app import upload_file_to_r2 as _up
    return _up(*args, **kwargs)

def get_current_admin(*args, **kwargs):
    from app import get_current_admin as _get
    return _get(*args, **kwargs)

def send_whatsapp_message(*args, **kwargs):
    from app import send_whatsapp_message as _send
    return _send(*args, **kwargs)

# --- APIS DO CHAT INTERNO & WEBHOOK ---

@whatsapp_bp.route('/api/chat/<path:codigo>', methods=['GET'])
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

@whatsapp_bp.route('/api/chat/<path:codigo>', methods=['POST'])
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
        
        # Lógica de Notificação de 15 Minutos
        enviar_notificacao = False
        from datetime import datetime, timedelta
        
        # 1. Busca a última mensagem do destinatário (para ver se ele está online/ativo)
        tipo_destinatario = 'cliente' if remetente_tipo == 'admin' else 'admin'
        if cursor.is_postgres:
            cursor.execute("SELECT data_envio FROM mensagens_chat WHERE referencia_codigo = %s AND remetente_tipo = %s ORDER BY id DESC LIMIT 1", (codigo, tipo_destinatario))
        else:
            cursor.execute("SELECT data_envio FROM mensagens_chat WHERE referencia_codigo = ? AND remetente_tipo = ? ORDER BY id DESC LIMIT 1", (codigo, tipo_destinatario))
        last_destinatario = cursor.fetchone()
        
        # 2. Busca a última mensagem do remetente (para ver se já notificamos há pouco tempo)
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
                # O admin não envia link do site para ele responder se for um chat GERAL
                if codigo == 'GERAL':
                    msg_wpp = f"💬 *Gráfica Rápida Express*\n\n_{mensagem}_"
                else:
                    msg_wpp = f"💬 *Gráfica Rápida Express*\nNova mensagem sobre o {codigo}:\n\n_{mensagem}_\n\nAcesse o site para responder!"
                send_evolution_whatsapp(telefone, msg_wpp)
                
            if remetente_tipo == 'cliente':
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute('SELECT whatsapp FROM configuracoes LIMIT 1')
                cfg = cursor.fetchone()
                conn.close()
                if cfg and dict(cfg).get('whatsapp'):
                    msg_wpp_admin = f"🔔 *Alerta de Mensagem*\nO cliente {remetente_nome} enviou uma mensagem sobre o {codigo}:\n\n_{mensagem}_\n\nAcesse o painel para responder!"
                    send_evolution_whatsapp(dict(cfg)['whatsapp'], msg_wpp_admin)
                    
        return jsonify({'message': 'Mensagem enviada'})
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500


def buscar_status_por_telefone(cursor, telefone):
    num_digits = ''.join(c for c in str(telefone) if c.isdigit())
    sufixo = num_digits[-8:] if len(num_digits) >= 8 else num_digits
    pattern = f"%{sufixo}%"
    
    if getattr(cursor, 'is_postgres', False):
        cursor.execute("SELECT codigo_pedido, status_producao, total FROM pedidos WHERE cliente_telefone LIKE %s ORDER BY id DESC LIMIT 5", (pattern,))
    else:
        cursor.execute("SELECT codigo_pedido, status_producao, total FROM pedidos WHERE cliente_telefone LIKE ? ORDER BY id DESC LIMIT 5", (pattern,))
    rows_pedidos = cursor.fetchall()
    
    if getattr(cursor, 'is_postgres', False):
        cursor.execute("SELECT codigo_orcamento, status, valor_estimado FROM orcamentos WHERE cliente_telefone LIKE %s ORDER BY id DESC LIMIT 5", (pattern,))
    else:
        cursor.execute("SELECT codigo_orcamento, status, valor_estimado FROM orcamentos WHERE cliente_telefone LIKE ? ORDER BY id DESC LIMIT 5", (pattern,))
    rows_orcamentos = cursor.fetchall()
    
    if not rows_pedidos and not rows_orcamentos:
        return "🤖 Não encontrei pedidos ou orçamentos associados ao seu número em nosso sistema.\n\nSe preferir, digite o código do seu pedido com a hashtag na frente (ex: *#GF-1234* ou *#ORC-1234*) ou digite *3* para falar com um atendente."
        
    res = "🤖 *Assistente Automático*\nLocalizei os seguintes registros vinculados ao seu telefone:\n"
    
    if rows_pedidos:
        res += "\n📦 *Seus Pedidos:*\n"
        for r in rows_pedidos:
            d = dict(r) if hasattr(r, 'keys') else {'codigo_pedido': r[0], 'status_producao': r[1], 'total': r[2]}
            cod = d.get('codigo_pedido') or ''
            st = d.get('status_producao') or ''
            tot = d.get('total') or 0.0
            res += f"• *{cod}*: {st} (R$ {tot:.2f})\n".replace('.', ',')
            
    if rows_orcamentos:
        res += "\n📋 *Seus Orçamentos:*\n"
        for r in rows_orcamentos:
            d = dict(r) if hasattr(r, 'keys') else {'codigo_orcamento': r[0], 'status': r[1], 'valor_estimado': r[2]}
            cod = d.get('codigo_orcamento') or ''
            st = d.get('status') or ''
            val = d.get('valor_estimado') or 0.0
            res += f"• *{cod}*: {st} (R$ {val:.2f})\n".replace('.', ',')
            
    res += "\nPara ver mais detalhes de algum item, basta enviar o código desejado (ex: *#GF-1234*)."
    return res


CLIENT_PRESENCE = {}

@whatsapp_bp.route('/api/chat/presenca/<path:telefone>', methods=['GET'])
def api_chat_presenca(telefone):
    import time
    num_limpo = ''.join(c for c in str(telefone) if c.isdigit())
    sufixo = num_limpo[-8:] if len(num_limpo) >= 8 else num_limpo
    
    is_active = False
    pres_tipo = 'composing'
    info_match = {}
    for k, info in list(CLIENT_PRESENCE.items()):
        if sufixo in k:
            pres = str(info.get('presence', '')).lower()
            t_last = info.get('time', 0)
            info_match = info
            if pres in ['composing', 'recording', 'typing'] and (time.time() - t_last) < 15:
                is_active = True
                pres_tipo = 'recording' if pres == 'recording' else 'composing'
                break
    return jsonify({'digitando': is_active, 'tipo': pres_tipo, 'info': info_match, 'sufixo': sufixo})


@whatsapp_bp.route('/api/webhook/evolution', methods=['POST'])
def webhook_evolution():
    # Recebe mensagens do cliente pelo WhatsApp e joga no chat do pedido
    # OBS: O Evolution API manda payloads diferentes dependendo da versão, 
    # estamos usando um genérico que tenta encontrar o remoteJid e text.
    try:
        data = request.json
        if not data or not isinstance(data, dict):
            return jsonify({'status': 'ignorado'}), 200
            
        event_raw = str(data.get('event') or data.get('type') or '').strip().lower()
        if event_raw and not any(k in event_raw for k in ['message', 'upsert', 'send', 'presence', 'update']):
            return jsonify({'status': 'ignorado, evento nao suportado'}), 200

        # 1. Tratar presença (cliente digitando no WhatsApp)
        if 'presence' in event_raw:
            print(f"[RAW PRESENCE] {data}")
            data_payload = data.get('data', {})
            if isinstance(data_payload, list) and len(data_payload) > 0:
                data_payload = data_payload[0]
                
            remote_jid = (data_payload.get('participant') or 
                          data_payload.get('id') or 
                          data_payload.get('remoteJid') or 
                          data_payload.get('key', {}).get('remoteJid') or 
                          data.get('remoteJid') or '')
            
            pres_state = ''
            presences = data_payload.get('presences')
            if isinstance(presences, dict):
                for p_key, p_val in presences.items():
                    if not remote_jid or '@lid' in remote_jid:
                        remote_jid = p_key
                    if isinstance(p_val, dict):
                        pres_state = p_val.get('lastKnownPresence') or p_val.get('presence') or ''
                    elif isinstance(p_val, str):
                        pres_state = p_val
                    if pres_state:
                        break
            
            if not pres_state and isinstance(data_payload, dict):
                pres_state = data_payload.get('presence') or data_payload.get('lastKnownPresence') or ''

            telefone = remote_jid.split('@')[0] if remote_jid else ''
            
            if telefone:
                num_limpo = ''.join(c for c in str(telefone) if c.isdigit())
                sufixo = num_limpo[-8:] if len(num_limpo) >= 8 else num_limpo
                import time
                if sufixo:
                    CLIENT_PRESENCE[sufixo] = {
                        'presence': str(pres_state).lower(),
                        'time': time.time(),
                        'jid': remote_jid
                    }
                    print(f"[Presence Event] Sufixo {sufixo} -> presence: {pres_state}")
            return jsonify({'status': 'sucesso, presenca'}), 200

        # 2. Tratar atualização de leitura de mensagem (lida = 1 no DB via keyId)
        if 'update' in event_raw and 'upsert' not in event_raw:
            data_payload = data.get('data', {})
            if isinstance(data_payload, list) and len(data_payload) > 0:
                data_payload = data_payload[0]
                
            key_id = (data_payload.get('keyId') or 
                      data_payload.get('key', {}).get('id') or 
                      data_payload.get('id') or '')
            status_ack = str(data_payload.get('status') or '').upper()
            
            if key_id and any(st in status_ack for st in ['READ', '4', 'DELIVERY_ACK', '3']):
                conn = get_db()
                cursor = conn.cursor()
                
                # Sempre usa o key_id para achar o telefone real do cliente
                telefone_real = None
                if cursor.is_postgres:
                    cursor.execute("SELECT telefone_cliente FROM mensagens_chat WHERE wpp_id = %s OR wpp_id LIKE %s LIMIT 1", (key_id, f"%{key_id}%"))
                else:
                    cursor.execute("SELECT telefone_cliente FROM mensagens_chat WHERE wpp_id = ? OR wpp_id LIKE ? LIMIT 1", (key_id, f"%{key_id}%"))
                row = cursor.fetchone()
                if row:
                    telefone_real = row[0]
                        
                if telefone_real:
                    if cursor.is_postgres:
                        cursor.execute("UPDATE mensagens_chat SET lida = 1 WHERE telefone_cliente = %s AND remetente_tipo = 'admin'", (telefone_real,))
                    else:
                        cursor.execute("UPDATE mensagens_chat SET lida = 1 WHERE telefone_cliente = ? AND remetente_tipo = 'admin'", (telefone_real,))
                else:
                    if cursor.is_postgres:
                        cursor.execute("UPDATE mensagens_chat SET lida = 1 WHERE wpp_id = %s OR wpp_id LIKE %s", (key_id, f"%{key_id}%"))
                    else:
                        cursor.execute("UPDATE mensagens_chat SET lida = 1 WHERE wpp_id = ? OR wpp_id LIKE ?", (key_id, f"%{key_id}%"))
                
                conn.commit()
                conn.close()
                print(f"[Read Update Success] Mensagens de {telefone_real or key_id} marcadas como lidas")
                return jsonify({'status': 'sucesso, status lida atualizado'}), 200
            
        data_payload = data.get('data', {})
        if isinstance(data_payload, list):
            data_payload = data_payload[0] if len(data_payload) > 0 else {}
            
        messages = data_payload.get('message') if isinstance(data_payload, dict) else {}
        if not messages and isinstance(data_payload, dict):
            messages = data_payload
            
        remote_jid = (data_payload.get('key', {}).get('remoteJid') or 
                      data_payload.get('remoteJid') or 
                      data.get('remoteJid') or '')
        
        text = None
        if isinstance(messages, dict):
            text = (messages.get('conversation') or 
                    messages.get('extendedTextMessage', {}).get('text') or 
                    messages.get('text') or 
                    messages.get('caption'))

        if not text and isinstance(data_payload, dict):
            text = (data_payload.get('conversation') or 
                    data_payload.get('text') or 
                    data_payload.get('caption') or 
                    data_payload.get('body'))
                    
        messageType = data_payload.get('messageType')
        if not messageType and isinstance(messages, dict) and messages:
            messageType = list(messages.keys())[0] if list(messages.keys())[0] != 'messageContextInfo' else (list(messages.keys())[1] if len(messages)>1 else 'text')
            messageType = list(messages.keys())[0] if list(messages.keys())[0] != 'messageContextInfo' else (list(messages.keys())[1] if len(messages)>1 else 'text')

        # Se for mídia, vamos tentar pegar o base64
        media_types = ['imageMessage', 'audioMessage', 'videoMessage', 'documentMessage', 'stickerMessage']
        if messageType in media_types:
            import urllib.request, json, time, os, uuid
            # Buscar configs
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('SELECT evolution_api_url, evolution_api_key, evolution_instance FROM configuracoes LIMIT 1')
            cfg = cursor.fetchone()
            if not has_request_context():
                conn.close()
            
            if cfg and dict(cfg).get('evolution_api_url'):
                try:
                    url_base64 = f"{dict(cfg)['evolution_api_url']}/chat/getBase64FromMediaMessage/{dict(cfg)['evolution_instance']}"
                    req_b64 = urllib.request.Request(url_base64, method='POST')
                    req_b64.add_header('Content-Type', 'application/json')
                    req_b64.add_header('apikey', dict(cfg)['evolution_api_key'])
                    payload_b64 = json.dumps({"message": data_payload}).encode('utf-8')
                    with urllib.request.urlopen(req_b64, data=payload_b64, timeout=10, context=ctx_unverified) as res_b64:
                        b64_res = json.loads(res_b64.read().decode('utf-8'))
                        b64_data = b64_res.get('base64')
                        if b64_data:
                            # b64_data is usually "data:image/jpeg;base64,/9j/..."
                            ext = 'bin'
                            if 'image/jpeg' in b64_data: ext = 'jpg'
                            elif 'image/png' in b64_data: ext = 'png'
                            elif 'image/webp' in b64_data: ext = 'webp'
                            elif 'audio/ogg' in b64_data or 'audio/mp4' in b64_data or 'audio/' in b64_data: ext = 'ogg'
                            elif 'video/mp4' in b64_data: ext = 'mp4'
                            elif 'application/pdf' in b64_data: ext = 'pdf'
                            
                            b64_content = b64_data.split(',')[-1] if ',' in b64_data else b64_data
                            import base64
                            file_bytes = base64.b64decode(b64_content)
                            filename = f"whatsapp_{uuid.uuid4().hex[:8]}.{ext}"
                            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                            with open(filepath, 'wb') as f:
                                f.write(file_bytes)
                            text = f"[MEDIA]:/static/uploads/{filename}"
                except Exception as err:
                    print("Erro ao baixar base64 da evolution:", err)
            
            # Garante que text não seja None se for mídia
            if not text: 
                text = f"[Mídia Recebida: {messageType}]"

        
        if not remote_jid or not text:
            return jsonify({'status': 'ignorado'}), 200
            
        # Pega o telefone (tira o @s.whatsapp.net)
        telefone = remote_jid.split('@')[0]
        push_name = data.get('data', {}).get('pushName') or f'Cliente {telefone}'
        
        is_from_me = data.get('data', {}).get('key', {}).get('fromMe')

        import re
        from datetime import datetime, timedelta
        
        match = re.search(r'(#?(?:GF|ORC)-[A-Z0-9]{4,12})', text.upper())
        
        conn = get_db()
        cursor = conn.cursor()
        
        if match:
            raw_code = match.group(1)
            codigo = f"#{raw_code.lstrip('#')}"
        else:
            if cursor.is_postgres:
                cursor.execute("SELECT referencia_codigo FROM mensagens_chat WHERE telefone_cliente = %s ORDER BY id DESC LIMIT 1", (telefone,))
            else:
                cursor.execute("SELECT referencia_codigo FROM mensagens_chat WHERE telefone_cliente = ? ORDER BY id DESC LIMIT 1", (telefone,))
            last_ref = cursor.fetchone()
            codigo = last_ref[0] if last_ref and last_ref[0] else "GERAL"
        
        
        if is_from_me:
            # Se a mensagem foi enviada pelo celular do admin ou pela API, salva se nao for duplicada
            if cursor.is_postgres:
                cursor.execute("SELECT id FROM mensagens_chat WHERE telefone_cliente = %s AND mensagem = %s AND remetente_tipo = 'admin' ORDER BY id DESC LIMIT 1", (telefone, text))
            else:
                cursor.execute("SELECT id FROM mensagens_chat WHERE telefone_cliente = ? AND mensagem = ? AND remetente_tipo = 'admin' ORDER BY id DESC LIMIT 1", (telefone, text))
            if not cursor.fetchone():
                cursor.execute('''
                    INSERT INTO mensagens_chat (referencia_codigo, remetente_tipo, remetente_nome, telefone_cliente, mensagem)
                    VALUES (?, 'admin', 'Atendente (Celular)', ?, ?)
                ''', (codigo, telefone, text))
                conn.commit()
            conn.close()
            return jsonify({'status': 'sucesso, fromMe processado'}), 200

        # Extrai foto e wpp_id do webhook se enviada no payload
        data_inner = data.get('data', {})
        wpp_id = data_inner.get('key', {}).get('id') or data_inner.get('id') or ''
        foto_webhook = (data_inner.get('profilePictureUrl') or 
                        data_inner.get('pictureUrl') or 
                        data_inner.get('sender', {}).get('profilePictureUrl') or 
                        data_inner.get('sender', {}).get('pictureUrl'))

        # 1. Salva a mensagem recebida do cliente
        cursor.execute('''
            INSERT INTO mensagens_chat (referencia_codigo, remetente_tipo, remetente_nome, telefone_cliente, mensagem, foto_url, wpp_id)
            VALUES (?, 'cliente', ?, ?, ?, ?, ?)
        ''', (codigo, push_name, telefone, text, foto_webhook, wpp_id))
        if foto_webhook:
            try:
                if cursor.is_postgres:
                    cursor.execute("UPDATE mensagens_chat SET foto_url = %s WHERE telefone_cliente = %s", (foto_webhook, telefone))
                else:
                    cursor.execute("UPDATE mensagens_chat SET foto_url = ? WHERE telefone_cliente = ?", (foto_webhook, telefone))
            except:
                pass
        conn.commit()

        # 2. Automação do Bot
        if cursor.is_postgres:
            cursor.execute("SELECT remetente_tipo, remetente_nome, mensagem, data_envio FROM mensagens_chat WHERE telefone_cliente = %s AND remetente_tipo IN ('admin', 'system') ORDER BY id DESC LIMIT 1", (telefone,))
        else:
            cursor.execute("SELECT remetente_tipo, remetente_nome, mensagem, data_envio FROM mensagens_chat WHERE telefone_cliente = ? AND remetente_tipo IN ('admin', 'system') ORDER BY id DESC LIMIT 1", (telefone,))
        
        last_admin = cursor.fetchone()
        
        # Checar tempo e remetente
        diff = 9999
        remetente_tipo = ""
        remetente = ""
        last_msg = ""
        
        if last_admin:
            remetente_tipo = dict(last_admin).get('remetente_tipo') if hasattr(last_admin, 'keys') else last_admin[0]
            remetente = dict(last_admin).get('remetente_nome') if hasattr(last_admin, 'keys') else last_admin[1]
            last_msg = dict(last_admin).get('mensagem') if hasattr(last_admin, 'keys') else last_admin[2]
            dt_str = dict(last_admin).get('data_envio') if hasattr(last_admin, 'keys') else last_admin[3]
            if dt_str:
                try:
                    if isinstance(dt_str, str):
                        last_time = datetime.strptime(dt_str.split('.')[0].split('+')[0], "%Y-%m-%d %H:%M:%S")
                    else:
                        last_time = dt_str.replace(tzinfo=None)
                    diff = (datetime.utcnow() - last_time).total_seconds()
                except:
                    pass
        
        if remetente_tipo == 'system':
            # Atendimento foi encerrado manualmente pelo admin.
            diff = 9999
            
        bot_reply = None
        
        if match:
            # Cliente digitou um código específico com a hashtag
            prefix = codigo.split('-')[0]
            if prefix == "#GF":
                codigo_limpo = codigo.lstrip('#')
                if cursor.is_postgres:
                    cursor.execute('SELECT status_producao, total FROM pedidos WHERE codigo_pedido = %s OR codigo_pedido = %s OR codigo_pedido LIKE %s', (codigo, codigo_limpo, f"%{codigo_limpo}%"))
                else:
                    cursor.execute('SELECT status_producao, total FROM pedidos WHERE codigo_pedido = ? OR codigo_pedido = ? OR codigo_pedido LIKE ?', (codigo, codigo_limpo, f"%{codigo_limpo}%"))
                row = cursor.fetchone()
                if row:
                    row_dict = dict(row) if hasattr(row, 'keys') else {'status_producao': row[0], 'total': row[1]}
                    status_str = f"Seu pedido *{codigo}* está atualmente: *{row_dict['status_producao']}*.\nValor total: R$ {row_dict['total']:.2f}".replace('.', ',')
                    bot_reply = f"🤖 *Assistente Automático*\nOlá! Encontrei as informações do seu pedido:\n\n{status_str}\n\nSe precisar falar com um humano, mande outra mensagem."
                else:
                    bot_reply = f"🤖 *Assistente Automático*\nNão encontrei nenhum pedido com o código *{codigo}* em nosso sistema.\n\nPor favor, verifique se digitou o código corretamente ou digite *3* para falar com um atendente."
            elif prefix == "#ORC":
                codigo_limpo = codigo.lstrip('#')
                if cursor.is_postgres:
                    cursor.execute('SELECT status, valor_estimado FROM orcamentos WHERE codigo_orcamento = %s OR codigo_orcamento = %s OR codigo_orcamento LIKE %s', (codigo, codigo_limpo, f"%{codigo_limpo}%"))
                else:
                    cursor.execute('SELECT status, valor_estimado FROM orcamentos WHERE codigo_orcamento = ? OR codigo_orcamento = ? OR codigo_orcamento LIKE ?', (codigo, codigo_limpo, f"%{codigo_limpo}%"))
                row = cursor.fetchone()
                if row:
                    row_dict = dict(row) if hasattr(row, 'keys') else {'status': row[0], 'valor_estimado': row[1]}
                    status_str = f"Seu orçamento *{codigo}* está: *{row_dict['status']}*.\nValor estimado: R$ {row_dict['valor_estimado']:.2f}".replace('.', ',')
                    bot_reply = f"🤖 *Assistente Automático*\nOlá! Encontrei as informações do seu orçamento:\n\n{status_str}\n\nSe precisar falar com um humano, mande outra mensagem."
                else:
                    bot_reply = f"🤖 *Assistente Automático*\nNão encontrei nenhum orçamento com o código *{codigo}* em nosso sistema.\n\nPor favor, verifique se digitou o código corretamente ou digite *3* para falar com um atendente."
            else:
                bot_reply = f"🤖 *Assistente Automático*\nRecebi o código *{codigo}*, mas não localizei registros associados a ele em nosso sistema.\n\nSe preferir, digite *3* para falar com um atendente."
        elif remetente and remetente != 'Assistente Virtual' and diff < 1200:
            # Se um humano (Atendente ou Painel) respondeu há menos de 20 minutos, PAUSA o bot.
            conn.close()
            return jsonify({'status': 'sucesso, bot pausado devido a interacao humana'})
        else:
            # Fluxo normal do menu
            if diff > 1200:
                # Passou 20 min desde a ultima interacao do admin. Resetar para menu inicial
                bot_reply = "🤖 *Assistente Automático - Gráfica Rápida Express*\nOlá! Seja bem-vindo(a)! Como posso ajudar você hoje?\n\nDigite o *NÚMERO* da opção desejada:\n1️⃣ - Abrir um novo Pedido/Orçamento\n2️⃣ - Verificar o status do meu pedido\n3️⃣ - Falar com atendente humano"
            elif remetente == 'Assistente Virtual':
                # Bot estava falando, processar estado
                user_text = text.strip()
                if "Digite o *NÚMERO* da opção" in last_msg:
                    if user_text == '1':
                        bot_reply = "🤖 Certo! Para começarmos, qual o seu nome completo?"
                    elif user_text == '2':
                        bot_reply = buscar_status_por_telefone(cursor, telefone)
                    elif user_text == '3':
                        bot_reply = "🤖 Ok! Transferindo para um atendente. Por favor, aguarde um instante!"
                    else:
                        bot_reply = "🤖 Opção inválida. Digite 1, 2 ou 3."
                
                elif "qual o seu nome completo?" in last_msg:
                    bot_reply = f"🤖 Prazer! Descreva o que você precisa fazer (ex: 1000 cartões de visita frente e verso):"
                
                elif "Descreva o que você precisa fazer" in last_msg:
                    # Encontrar o nome do cliente!
                    if cursor.is_postgres:
                        cursor.execute("SELECT mensagem FROM mensagens_chat WHERE telefone_cliente = %s AND remetente_tipo = 'cliente' ORDER BY id DESC LIMIT 1 OFFSET 1", (telefone,))
                    else:
                        cursor.execute("SELECT mensagem FROM mensagens_chat WHERE telefone_cliente = ? AND remetente_tipo = 'cliente' ORDER BY id DESC LIMIT 1 OFFSET 1", (telefone,))
                    
                    row = cursor.fetchone()
                    nome_cliente = row[0] if row else push_name
                    descricao = user_text
                    
                    import uuid
                    orc_codigo = f"#ORC-{datetime.now().strftime('%m%d')}{uuid.uuid4().hex[:4].upper()}"
                    
                    cursor.execute('''
                        INSERT INTO orcamentos (codigo_orcamento, cliente_nome, cliente_telefone, descricao, valor_estimado, status)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (orc_codigo, nome_cliente, telefone, descricao, 0, 'Pendente'))
                    
                    bot_reply = f"✅ Tudo pronto! Registramos sua solicitação sob o código *{orc_codigo}*.\nEm breve nossa equipe enviará os valores!"
            
        if bot_reply:
            send_evolution_whatsapp(telefone, bot_reply)
            if cursor.is_postgres:
                cursor.execute("INSERT INTO mensagens_chat (referencia_codigo, remetente_tipo, remetente_nome, telefone_cliente, mensagem) VALUES (%s, 'admin', 'Assistente Virtual', %s, %s)", (codigo, telefone, bot_reply))
            else:
                cursor.execute("INSERT INTO mensagens_chat (referencia_codigo, remetente_tipo, remetente_nome, telefone_cliente, mensagem) VALUES (?, 'admin', 'Assistente Virtual', ?, ?)", (codigo, telefone, bot_reply))
            conn.commit()

        conn.close()
        return jsonify({'status': 'sucesso'})
    except Exception as e:
        import traceback
        print("Erro Webhook:", traceback.format_exc())
        return jsonify({'error': str(e)}), 500


@whatsapp_bp.route('/api/chat/contato/<path:telefone>', methods=['GET'])
def api_chat_contato(telefone):
    token_admin = request.headers.get('X-Admin-Token')
    if not get_current_admin(token_admin):
        return jsonify({'error': 'Acesso negado'}), 401
    
    conn = get_db()
    cursor = conn.cursor()
    
    # 1. Buscar nome e foto salvos no banco
    nome_banco = None
    foto_banco = None
    try:
        if cursor.is_postgres:
            cursor.execute("SELECT remetente_nome, foto_url FROM mensagens_chat WHERE telefone_cliente = %s AND remetente_tipo = 'cliente' ORDER BY id DESC LIMIT 1", (telefone,))
        else:
            cursor.execute("SELECT remetente_nome, foto_url FROM mensagens_chat WHERE telefone_cliente = ? AND remetente_tipo = ? ORDER BY id DESC LIMIT 1", (telefone, 'cliente'))
        row = cursor.fetchone()
        if row:
            r_dict = dict(row) if hasattr(row, 'keys') else {'remetente_nome': row[0], 'foto_url': row[1] if len(row) > 1 else None}
            nome_banco = r_dict.get('remetente_nome')
            foto_banco = r_dict.get('foto_url')
    except Exception as e:
        pass
    
    nome_evolution = None
    foto_url = foto_banco
    
    # 2. Tentar buscar da Evolution API (v1 / v2)
    try:
        cursor2 = conn.cursor()
        cursor2.execute('SELECT evolution_api_url, evolution_api_key, evolution_instance FROM configuracoes LIMIT 1')
        cfg_row = cursor2.fetchone()
        if cfg_row:
            cfg = dict(cfg_row) if hasattr(cfg_row, 'keys') else {'evolution_api_url': cfg_row[0], 'evolution_api_key': cfg_row[1], 'evolution_instance': cfg_row[2]}
            api_url = (cfg.get('evolution_api_url') or '').strip().rstrip('/')
            api_key = (cfg.get('evolution_api_key') or '').strip()
            instance = (cfg.get('evolution_instance') or '').strip()
            
            if api_url and api_key and instance:
                headers = {'Content-Type': 'application/json', 'apikey': api_key}
                num_limpo = ''.join(c for c in str(telefone) if c.isdigit())
                
                # A. Testar POST endpoints de foto de perfil
                foto_endpoints = [
                    f"{api_url}/chat/fetchProfilePictureUrl/{instance}",
                    f"{api_url}/profile/fetchProfilePictureUrl/{instance}"
                ]
                payloads_foto = [
                    json.dumps({"number": num_limpo}).encode('utf-8'),
                    json.dumps({"number": f"{num_limpo}@s.whatsapp.net"}).encode('utf-8')
                ]
                
                for f_url in foto_endpoints:
                    if foto_url: break
                    for p_data in payloads_foto:
                        if foto_url: break
                        try:
                            req_foto = urllib.request.Request(f_url, data=p_data, headers=headers, method='POST')
                            with urllib.request.urlopen(req_foto, timeout=4, context=ctx_unverified) as resp:
                                foto_data = json.loads(resp.read().decode('utf-8'))
                                if isinstance(foto_data, dict):
                                    foto_url = (foto_data.get('profilePictureUrl') or 
                                                foto_data.get('pictureUrl') or 
                                                foto_data.get('picture') or 
                                                foto_data.get('url') or 
                                                foto_data.get('imgUrl') or 
                                                foto_data.get('profilePicUrl') or
                                                foto_data.get('displayPictureUrl'))
                        except Exception as e:
                            pass
                
                # B. Testar GET endpoint de foto
                if not foto_url:
                    try:
                        get_ep = f"{api_url}/chat/fetchProfilePictureUrl/{instance}?number={num_limpo}"
                        req_get = urllib.request.Request(get_ep, headers=headers, method='GET')
                        with urllib.request.urlopen(req_get, timeout=4, context=ctx_unverified) as resp:
                            foto_data = json.loads(resp.read().decode('utf-8'))
                            if isinstance(foto_data, dict):
                                foto_url = (foto_data.get('profilePictureUrl') or foto_data.get('pictureUrl') or foto_data.get('picture') or foto_data.get('url'))
                    except Exception as e:
                        pass
                
                # C. Testar busca de contatos (findContacts / contact find) - extrai tanto Nome quanto Foto
                contact_endpoints = [
                    (f"{api_url}/chat/findContacts/{instance}", json.dumps({"where": {"id": f"{num_limpo}@s.whatsapp.net"}}).encode('utf-8')),
                    (f"{api_url}/chat/findContacts/{instance}", json.dumps({"where": {"id": num_limpo}}).encode('utf-8')),
                    (f"{api_url}/contact/find/{instance}", json.dumps({"where": {"id": f"{num_limpo}@s.whatsapp.net"}}).encode('utf-8')),
                ]
                for c_ep, c_payload in contact_endpoints:
                    try:
                        req_contact = urllib.request.Request(c_ep, data=c_payload, headers=headers, method='POST')
                        with urllib.request.urlopen(req_contact, timeout=4, context=ctx_unverified) as resp:
                            contact_data = json.loads(resp.read().decode('utf-8'))
                            obj = None
                            if isinstance(contact_data, list) and len(contact_data) > 0:
                                obj = contact_data[0]
                            elif isinstance(contact_data, dict):
                                obj = contact_data
                            
                            if obj:
                                if not nome_evolution:
                                    nome_evolution = obj.get('pushName') or obj.get('name') or obj.get('verifiedName')
                                if not foto_url:
                                    foto_url = (obj.get('profilePictureUrl') or 
                                                obj.get('pictureUrl') or 
                                                obj.get('picture') or 
                                                obj.get('profilePicUrl') or 
                                                obj.get('url'))
                    except Exception as e:
                        pass
    except Exception as e:
        print("Erro api_chat_contato:", e)
    
    # 3. Atualizar foto_url no banco de dados para a conversa do cliente
    if foto_url and foto_url != foto_banco:
        try:
            if cursor.is_postgres:
                cursor.execute("UPDATE mensagens_chat SET foto_url = %s WHERE telefone_cliente = %s", (foto_url, telefone))
            else:
                cursor.execute("UPDATE mensagens_chat SET foto_url = ? WHERE telefone_cliente = ?", (foto_url, telefone))
            conn.commit()
        except Exception as e:
            pass
            
    conn.close()
    
    nome_final = nome_evolution or nome_banco or f'Cliente {telefone}'
    
    return jsonify({
        'nome': nome_final,
        'telefone': telefone,
        'foto_url': foto_url
    })


@whatsapp_bp.route('/api/chat/telefone/<path:telefone>/resolve', methods=['POST'])
def api_chat_telefone_resolve(telefone):
    token_admin = request.headers.get('X-Admin-Token')
    if not get_current_admin(token_admin):
        return jsonify({'error': 'Acesso negado'}), 401
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO mensagens_chat (referencia_codigo, remetente_tipo, remetente_nome, telefone_cliente, mensagem)
        VALUES (?, 'system', 'Sistema', ?, ?)
    ''', ('GERAL', telefone, 'Atendimento Encerrado. O bot está ativo novamente.'))
    conn.commit()
    conn.close()
    
    return jsonify({'status': 'sucesso', 'message': 'Atendimento encerrado.'})

@whatsapp_bp.route('/api/chat/telefone/<path:telefone>', methods=['GET'])
def api_chat_telefone_get(telefone):
    token_admin = request.headers.get('X-Admin-Token')
    if not get_current_admin(token_admin):
        return jsonify({'error': 'Acesso negado'}), 401
        
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM mensagens_chat WHERE telefone_cliente = ? ORDER BY data_envio ASC', (telefone,))
    mensagens = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify(mensagens)

@whatsapp_bp.route('/api/chat/telefone/<path:telefone>', methods=['POST'])
def api_chat_telefone_post(telefone):
    token_admin = request.headers.get('X-Admin-Token')
    if not get_current_admin(token_admin):
        return jsonify({'error': 'Acesso negado'}), 401
        
    data = request.get_json(silent=True) or {}
    mensagem = data.get('mensagem', '').strip()
    file_b64 = data.get('file_base64')
    file_name = data.get('file_name', 'arquivo')
    file_type = data.get('file_type', 'image')
    file_mime = data.get('file_mime', 'application/octet-stream')

    if not mensagem and not file_b64:
        return jsonify({'error': 'Mensagem vazia'}), 400

    media_path_db = None
    media_full_url = None
    if file_b64:
        import base64, uuid, os
        try:
            b64_content = file_b64.split(',')[-1] if ',' in file_b64 else file_b64
            file_bytes = base64.b64decode(b64_content)
            ext = file_name.split('.')[-1] if '.' in file_name else 'bin'
            saved_name = f"admin_{uuid.uuid4().hex[:8]}.{ext}"
            from flask import current_app
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], saved_name)
            with open(filepath, 'wb') as f:
                f.write(file_bytes)
            media_path_db = f"/static/uploads/{saved_name}"
            
            # URL pública para envio na Evolution API
            app_host = os.environ.get('APP_URL', 'https://grafica.cristhiansancore.com.br').rstrip('/')
            media_full_url = f"{app_host}{media_path_db}"
            
            if not mensagem or mensagem == 'none':
                mensagem = f"[MEDIA]:{media_path_db}"
            else:
                mensagem = f"{mensagem}\n[MEDIA]:{media_path_db}"
        except Exception as e:
            print("Erro ao salvar mídia do admin:", e)
            
    msg_envio = data.get('mensagem', '')
    if file_b64:
        success, err = send_evolution_whatsapp(
            telefone, 
            msg_envio, 
            media_base64=file_b64, 
            media_url=media_full_url, 
            media_type=file_type, 
            media_mime=file_mime, 
            media_name=file_name
        )
    else:
        success, err = send_evolution_whatsapp(telefone, msg_envio)
        
    if not success:
        return jsonify({'error': err}), 500

    wpp_id = None
    try:
        import json
        res_json = json.loads(err) if isinstance(err, str) else err
        if isinstance(res_json, dict):
            wpp_id = res_json.get('key', {}).get('id') or res_json.get('id')
    except Exception:
        pass

    conn = get_db()
    cursor = conn.cursor()
    if cursor.is_postgres:
        cursor.execute('''
            INSERT INTO mensagens_chat (referencia_codigo, remetente_tipo, remetente_nome, telefone_cliente, mensagem, wpp_id)
            VALUES ('GERAL', 'admin', 'Admin', %s, %s, %s)
        ''', (telefone, mensagem, wpp_id))
    else:
        cursor.execute('''
            INSERT INTO mensagens_chat (referencia_codigo, remetente_tipo, remetente_nome, telefone_cliente, mensagem, wpp_id)
            VALUES ('GERAL', 'admin', 'Admin', ?, ?, ?)
        ''', (telefone, mensagem, wpp_id))
    conn.commit()
    conn.close()
    return jsonify({'status': 'sucesso'})

@whatsapp_bp.route('/api/chat/telefone/<path:telefone>/read', methods=['POST'])
def api_chat_telefone_read(telefone):
    token_admin = request.headers.get('X-Admin-Token')
    if not get_current_admin(token_admin):
        return jsonify({'error': 'Acesso negado'}), 401
        
    conn = get_db()
    cursor = conn.cursor()
    if cursor.is_postgres:
        cursor.execute("UPDATE mensagens_chat SET lida = 1 WHERE telefone_cliente = %s AND remetente_tipo = 'cliente'", (telefone,))
    else:
        cursor.execute("UPDATE mensagens_chat SET lida = 1 WHERE telefone_cliente = ? AND remetente_tipo = 'cliente'", (telefone,))
    conn.commit()

    # Mandar sinal de leitura para o WhatsApp via Evolution API (2 tiques azuis)
    try:
        cursor.execute('SELECT evolution_api_url, evolution_api_key, evolution_instance FROM configuracoes LIMIT 1')
        row_cfg = cursor.fetchone()
        if row_cfg and dict(row_cfg).get('evolution_api_url'):
            cfg = dict(row_cfg)
            api_url = (cfg.get('evolution_api_url') or '').strip().rstrip('/')
            api_key = (cfg.get('evolution_api_key') or '').strip()
            instance = (cfg.get('evolution_instance') or '').strip()
            
            # Buscar último wpp_id do cliente para informar à Evolution API
            if cursor.is_postgres:
                cursor.execute("SELECT wpp_id FROM mensagens_chat WHERE telefone_cliente = %s AND remetente_tipo = 'cliente' AND wpp_id IS NOT NULL AND wpp_id != '' ORDER BY id DESC LIMIT 1", (telefone,))
            else:
                cursor.execute("SELECT wpp_id FROM mensagens_chat WHERE telefone_cliente = ? AND remetente_tipo = 'cliente' AND wpp_id IS NOT NULL AND wpp_id != '' ORDER BY id DESC LIMIT 1", (telefone,))
            row_wpp = cursor.fetchone()
            target_wpp_id = row_wpp[0] if row_wpp and row_wpp[0] else "read_all"
            
            if api_url and api_key and instance:
                url_read = f"{api_url}/chat/markMessageAsRead/{instance}"
                req_read = urllib.request.Request(url_read, method='POST')
                req_read.add_header('Content-Type', 'application/json')
                req_read.add_header('apikey', api_key)
                req_read.add_header('User-Agent', 'Mozilla/5.0')
                payload_read = json.dumps({"readMessages": [{"remoteJid": f"{telefone}@s.whatsapp.net", "fromMe": False, "id": target_wpp_id}]}).encode('utf-8')
                with urllib.request.urlopen(req_read, data=payload_read, timeout=5, context=ctx_unverified) as res_read:
                    pass
    except Exception as err:
        print("Erro ao enviar markMessageAsRead para Evolution API:", err)

    conn.close()
    return jsonify({'status': 'lidas'})

@whatsapp_bp.route('/api/chat/telefone/<path:telefone>', methods=['DELETE'])
def api_chat_telefone_delete(telefone):
    token_admin = request.headers.get('X-Admin-Token')
    if not get_current_admin(token_admin):
        return jsonify({'error': 'Acesso restrito ao administrador.'}), 403
        
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM mensagens_chat WHERE telefone_cliente = ?', (telefone,))
    conn.commit()
    conn.close()
    return jsonify({'status': 'sucesso'})

@whatsapp_bp.route("/api/chat/inbox", methods=["GET"])
def api_chat_inbox():
    token_admin = request.headers.get('X-Admin-Token')
    if not get_current_admin(token_admin):
        return jsonify({'error': 'Acesso restrito ao administrador.'}), 403
    # Retorna as conversas mais recentes agrupadas por referencia_codigo ou telefone
    conn = get_db()
    cursor = conn.cursor()
    if cursor.is_postgres:
        cursor.execute("""
            SELECT DISTINCT ON (telefone_cliente) 
                referencia_codigo, 
                telefone_cliente, 
                COALESCE((SELECT remetente_nome FROM mensagens_chat mc2 WHERE mc2.telefone_cliente = mensagens_chat.telefone_cliente AND mc2.remetente_tipo = 'cliente' AND mc2.remetente_nome IS NOT NULL AND mc2.remetente_nome != '' ORDER BY id DESC LIMIT 1), 'Cliente') as remetente_nome,
                mensagem, data_envio, lida, remetente_tipo,
                COALESCE((SELECT foto_url FROM mensagens_chat mc3 WHERE mc3.telefone_cliente = mensagens_chat.telefone_cliente AND mc3.foto_url IS NOT NULL AND mc3.foto_url != '' ORDER BY id DESC LIMIT 1), '') as foto_url
            FROM mensagens_chat 
            ORDER BY telefone_cliente, id DESC
        """)
    else:
        cursor.execute("""
            SELECT 
                referencia_codigo, 
                telefone_cliente, 
                COALESCE((SELECT remetente_nome FROM mensagens_chat mc2 WHERE mc2.telefone_cliente = mensagens_chat.telefone_cliente AND mc2.remetente_tipo = 'cliente' AND mc2.remetente_nome IS NOT NULL AND mc2.remetente_nome != '' ORDER BY id DESC LIMIT 1), 'Cliente') as remetente_nome,
                mensagem, data_envio, lida, remetente_tipo,
                COALESCE((SELECT foto_url FROM mensagens_chat mc3 WHERE mc3.telefone_cliente = mensagens_chat.telefone_cliente AND mc3.foto_url IS NOT NULL AND mc3.foto_url != '' ORDER BY id DESC LIMIT 1), '') as foto_url
            FROM mensagens_chat 
            GROUP BY telefone_cliente
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
            "data_envio": r[4], "lida": r[5], "remetente_tipo": r[6],
            "foto_url": r[7] if len(r) > 7 else ""
        }
        
        # Pega a contagem de no lidas para este chat
        if cursor.is_postgres:
            cursor.execute("SELECT COUNT(*) FROM mensagens_chat WHERE referencia_codigo = %s AND telefone_cliente = %s AND remetente_tipo = %s AND lida = 0", (d["referencia_codigo"], d["telefone_cliente"], "cliente"))
        else:
            cursor.execute("SELECT COUNT(*) FROM mensagens_chat WHERE referencia_codigo = ? AND telefone_cliente = ? AND remetente_tipo = ? AND lida = 0", (d["referencia_codigo"], d["telefone_cliente"], "cliente"))
        
        c_row = cursor.fetchone()
        d["nao_lidas"] = c_row[0] if c_row else 0
        inbox.append(d)
        
    conn.close()
    return jsonify(inbox)

@whatsapp_bp.route("/api/chat/unread/admin", methods=["GET"])
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

@whatsapp_bp.route("/api/chat/unread/cliente", methods=["GET"])
def api_chat_unread_cliente():
    cli = get_current_client(request.headers.get('X-Client-Token'))
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

@whatsapp_bp.route("/api/chat/<path:codigo>", methods=["DELETE"])
def api_chat_delete(codigo):
    token_admin = request.headers.get("X-Admin-Token")
    if not get_current_admin(token_admin):
        return jsonify({"error": "Acesso restrito ao administrador."}), 403
        
    telefone = request.args.get("telefone", "")
    if not telefone:
        return jsonify({"error": "Telefone obrigatório"}), 400
        
    conn = get_db()
    cursor = conn.cursor()
    if cursor.is_postgres:
        cursor.execute("DELETE FROM mensagens_chat WHERE referencia_codigo = %s AND telefone_cliente = %s", (codigo, telefone))
    else:
        cursor.execute("DELETE FROM mensagens_chat WHERE referencia_codigo = ? AND telefone_cliente = ?", (codigo, telefone))
    conn.commit()
    conn.close()
    return jsonify({"status": "apagado"})

@whatsapp_bp.route("/api/chat/save_contact", methods=["POST"])
def api_chat_save_contact():
    token_admin = request.headers.get("X-Admin-Token")
    if not get_current_admin(token_admin):
        return jsonify({"error": "Acesso restrito ao administrador."}), 403
        
    data = request.json
    telefone = data.get("telefone")
    nome = data.get("nome", "Cliente")
    
    if not telefone:
        return jsonify({"error": "Telefone obrigatório"}), 400
        
    conn = get_db()
    cursor = conn.cursor()
    # Check if client exists by phone
    if cursor.is_postgres:
        cursor.execute("SELECT id FROM clientes WHERE telefone = %s", (telefone,))
    else:
        cursor.execute("SELECT id FROM clientes WHERE telefone = ?", (telefone,))
    
    row = cursor.fetchone()
    if row:
        conn.close()
        return jsonify({"status": "existe", "message": "Cliente já existe."})
        
    # Generate new password
    import random
    import string
    senha = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    senha_hash = generate_password_hash(senha)
    
    if cursor.is_postgres:
        cursor.execute("INSERT INTO clientes (nome, email, telefone, senha_hash, status_validacao) VALUES (%s, %s, %s, %s, 'Ativo')", (nome, f"{telefone}@wa.me", telefone, senha_hash))
    else:
        cursor.execute("INSERT INTO clientes (nome, email, telefone, senha_hash, status_validacao) VALUES (?, ?, ?, ?, 'Ativo')", (nome, f"{telefone}@wa.me", telefone, senha_hash))
    
    conn.commit()
    conn.close()
    return jsonify({"status": "sucesso", "senha": senha, "message": f"Cliente salvo com sucesso!"})

@whatsapp_bp.route("/api/chat/<path:codigo>/read", methods=["POST"])
def api_chat_read(codigo):
    token_admin = request.headers.get("X-Admin-Token")
    token_cliente = request.headers.get("X-Client-Token")
    if not token_admin and not token_cliente:
        return jsonify({"error": "Acesso negado"}), 401
        
    remetente_esperado = "cliente" if token_admin else "admin"
    data = request.get_json(silent=True) or {}
    telefone = data.get("telefone", "")
    
    # Se o path recebido for "telefone/..." redireciona
    if codigo and codigo.startswith("telefone/"):
        telefone = codigo.replace("telefone/", "").strip()
        codigo = None

    conn = get_db()
    cursor = conn.cursor()
    if cursor.is_postgres:
        if codigo:
            query = "UPDATE mensagens_chat SET lida = 1 WHERE referencia_codigo = %s AND remetente_tipo = %s"
            params = [codigo, remetente_esperado]
            if telefone:
                query += " AND telefone_cliente = %s"
                params.append(telefone)
            cursor.execute(query, tuple(params))
        elif telefone:
            cursor.execute("UPDATE mensagens_chat SET lida = 1 WHERE telefone_cliente = %s AND remetente_tipo = %s", (telefone, remetente_esperado))
    else:
        if codigo:
            query = "UPDATE mensagens_chat SET lida = 1 WHERE referencia_codigo = ? AND remetente_tipo = ?"
            params = [codigo, remetente_esperado]
            if telefone:
                query += " AND telefone_cliente = ?"
                params.append(telefone)
            cursor.execute(query, tuple(params))
        elif telefone:
            cursor.execute("UPDATE mensagens_chat SET lida = 1 WHERE telefone_cliente = ? AND remetente_tipo = ?", (telefone, remetente_esperado))
            
    conn.commit()
    conn.close()
    return jsonify({"status": "lidas"})

if __name__ == '__main__':
    print("=" * 60)
    print(" GRAFICA RAPIDA EXPRESS - SERVIDOR INICIALIZADO ")
    print(" Acesse a aplicacao em: http://127.0.0.1:8050")
    print("=" * 60)
    app.run(host='0.0.0.0', port=8050, debug=False)

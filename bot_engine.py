import json

def process_bot_flow(fluxo_json, current_node_id, user_text):
    """
    Retorna (novo_node_id, mensagem_resposta)
    Se o json for invalido ou vazio, retorna (None, None) para fallback.
    """
    try:
        if not fluxo_json or fluxo_json == '{}' or fluxo_json == 'null':
            return None, None
            
        data = json.loads(fluxo_json)
        nodes = data.get('drawflow', {}).get('Home', {}).get('data', {})
        if not nodes:
            return None, None
            
        # Encontrar inicio
        inicio_id = None
        for n_id, n_data in nodes.items():
            if n_data.get('name') == 'inicio':
                inicio_id = n_id
                break
                
        if not inicio_id:
            return None, None

        next_node_id = None
        
        if not current_node_id:
            # Comecar do inicio
            inicio_node = nodes.get(str(inicio_id))
            conns = inicio_node.get('outputs', {}).get('output_1', {}).get('connections', [])
            if conns:
                next_node_id = conns[0]['node']
            else:
                return None, "Fluxo visual incompleto. Conecte o Início a algum bloco."
        else:
            # Avaliar transicao do no atual baseado no user_text
            current_node = nodes.get(str(current_node_id))
            if not current_node: 
                # Estado perdido, recomeca
                return None, None
                
            node_name = current_node.get('name')
            
            if node_name == 'mensagem':
                # Mensagem solta (sem condicao), aceita qualquer input para continuar
                conns = current_node.get('outputs', {}).get('output_1', {}).get('connections', [])
                if conns:
                    next_node_id = conns[0]['node']
                else:
                    next_node_id = None # Fim do fluxo
                    
            elif node_name == 'menu':
                user_text = user_text.strip()
                if user_text == '1':
                    conns = current_node.get('outputs', {}).get('output_1', {}).get('connections', [])
                    if conns: next_node_id = conns[0]['node']
                elif user_text == '2':
                    conns = current_node.get('outputs', {}).get('output_2', {}).get('connections', [])
                    if conns: next_node_id = conns[0]['node']
                elif user_text == '3':
                    conns = current_node.get('outputs', {}).get('output_3', {}).get('connections', [])
                    if conns: next_node_id = conns[0]['node']
                    
            elif node_name == 'rastreio':
                # Rastreio especial
                return current_node_id, "__DO_RASTREIO__:" + user_text.strip()
                
            if not next_node_id:
                # Nao conseguiu transitar.
                if node_name == 'menu':
                    return current_node_id, "🤖 Opção inválida. Escolha uma opção válida."
                else:
                    return current_node_id, "O fluxo terminou. Se precisar, chame novamente."
                    
        # Percorrer a cadeia a partir do next_node_id
        bot_responses = []
        curr_id = next_node_id
        while curr_id:
            node = nodes.get(str(curr_id))
            if not node: break
            n_type = node.get('name')
            
            if n_type == 'mensagem':
                text_val = node.get('data', {}).get('text', '')
                if text_val: bot_responses.append(text_val)
                conns = node.get('outputs', {}).get('output_1', {}).get('connections', [])
                if conns:
                    curr_id = conns[0]['node']
                else:
                    break
            elif n_type == 'menu':
                msg = node.get('data', {}).get('text', 'Escolha uma opção:')
                opt1 = node.get('data', {}).get('opt1', '')
                opt2 = node.get('data', {}).get('opt2', '')
                opt3 = node.get('data', {}).get('opt3', '')
                menu_text = msg
                if opt1: menu_text += f"\n1️⃣ - {opt1}"
                if opt2: menu_text += f"\n2️⃣ - {opt2}"
                if opt3: menu_text += f"\n3️⃣ - {opt3}"
                bot_responses.append(menu_text)
                break # Para, espera input
            elif n_type == 'rastreio':
                bot_responses.append("__RASTREIO__")
                break # Para, espera input (codigo)
            elif n_type == 'humano':
                msg_val = node.get('data', {}).get('text', 'Ok! Transferindo...')
                bot_responses.append("__HUMANO__:" + msg_val)
                break
            else:
                break
                
        if not bot_responses:
            return None, "Configuração do bloco vazia."
            
        return curr_id, "\n\n".join(bot_responses)
        
    except Exception as e:
        print("Erro bot_engine:", e)
        return None, None

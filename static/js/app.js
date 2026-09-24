/* ==========================================================================
   APP JAVASCRIPT - GRÁFICA RÁPIDA EXPRESS (COM AUTENTICAÇÃO SEGURA)
   ========================================================================== */

// --- SWEETALERT2 OVERRIDE ---
window.originalAlert = window.alert;
window.alert = function(msg) {
  if (typeof Swal === 'undefined') return window.originalAlert(msg);
  
  let icon = 'info';
  let title = 'Atenção';
  
  if (msg.includes('🎉') || msg.includes('✅') || msg.toLowerCase().includes('sucesso')) {
    icon = 'success';
    title = 'Sucesso!';
  } else if (msg.includes('❌') || msg.includes('Erro') || msg.includes('inválid') || msg.includes('Falha') || msg.includes('não encontrad')) {
    icon = 'error';
    title = 'Oops...';
  } else if (msg.includes('Por favor')) {
    icon = 'warning';
  }
  
  const isDark = document.body.classList.contains('dark-mode');
  
  Swal.fire({
    title: title,
    text: msg,
    icon: icon,
    confirmButtonColor: '#4f46e5',
    confirmButtonText: 'OK',
    background: isDark ? '#1e1e2d' : '#ffffff',
    color: isDark ? '#f3f4f6' : '#1f2937',
    customClass: {
      popup: 'swal2-modern-popup'
    }
  });
};


window.originalConfirm = window.confirm;
window.confirmAsync = async function(msg) {
  if (typeof Swal === 'undefined') return window.originalConfirm(msg);
  const isDark = document.body.classList.contains('dark-mode');
  const res = await Swal.fire({
    title: 'Confirmação',
    text: msg,
    icon: 'warning',
    showCancelButton: true,
    confirmButtonColor: '#d33',
    cancelButtonColor: '#6c757d',
    confirmButtonText: 'Sim',
    cancelButtonText: 'Cancelar',
    background: isDark ? '#1e1e2d' : '#ffffff',
    color: isDark ? '#f3f4f6' : '#1f2937',
    customClass: { popup: 'swal2-modern-popup' }
  });
  return res.isConfirmed;
};

window.originalPrompt = window.prompt;
window.promptAsync = async function(msg, defaultVal) {
  if (typeof Swal === 'undefined') return window.originalPrompt(msg, defaultVal);
  const isDark = document.body.classList.contains('dark-mode');
  const res = await Swal.fire({
    title: 'Atenção',
    text: msg,
    input: 'text',
    inputValue: defaultVal || '',
    showCancelButton: true,
    confirmButtonColor: '#4f46e5',
    cancelButtonColor: '#6c757d',
    confirmButtonText: 'OK',
    cancelButtonText: 'Cancelar',
    background: isDark ? '#1e1e2d' : '#ffffff',
    color: isDark ? '#f3f4f6' : '#1f2937',
    customClass: { popup: 'swal2-modern-popup' }
  });
  return res.isConfirmed ? res.value : null;
};


const state = {
  produtos: [],
  config: {},
  carrinho: JSON.parse(localStorage.getItem('grafica_carrinho') || '[]'),
  produtoSelecionado: null,
  opcoesSelecionadas: {
    tamanho: '',
    papel: '',
    acabamento: '',
    tiragem: null,
    arteUrl: '',
    criarArte: false,
    detalhesArte: '',
    precoTotal: 0
  },
  ultimoPedidoCodigo: '',
  activeCategory: 'Todos',
  currentView: 'cliente',
  adminTab: 'dashboard',
  portalTab: 'historico',
  clientToken: localStorage.getItem('grafica_cli_token') || '',
  adminToken: localStorage.getItem('grafica_adm_token') || '',
  clienteLogado: null,
  adminLogado: null,
  cupomAplicado: null
};

// Initialize Application
document.addEventListener('DOMContentLoaded', () => {
  loadConfig();
  loadProdutos();
  updateCartBadge();
  verificarSessaoCliente();
  
  if (localStorage.getItem('grafica_theme') === 'dark') {
    document.documentElement.setAttribute('data-theme', 'dark');
    const icon = document.getElementById('theme-icon');
    if (icon) icon.className = 'fa-solid fa-sun';
  }
});

// --- THEME & VIEW SWITCHING ---

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme');
  const next = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('grafica_theme', next);
  
  const icon = document.getElementById('theme-icon');
  if (icon) {
    icon.className = next === 'dark' ? 'fa-solid fa-sun' : 'fa-solid fa-moon';
  }
}

function switchView(view) {
  state.currentView = view;
  const vCliente = document.getElementById('view-cliente');
  const vPortalCliente = document.getElementById('view-portal-cliente');
  const vAdmin = document.getElementById('view-admin');
  const btnAdmin = document.getElementById('btn-admin-toggle');
  
  vCliente.style.display = 'none';
  vPortalCliente.style.display = 'none';
  vAdmin.style.display = 'none';

  if (view === 'admin') {
    vAdmin.style.display = 'flex';
    btnAdmin.innerHTML = '<i class="fa-solid fa-store"></i> Voltar ao Site';
    btnAdmin.className = 'btn btn-primary btn-sm';
    btnAdmin.onclick = () => switchView('cliente');
    loadDashboardMetrics();
  } else if (view === 'portal-cliente') {
    vPortalCliente.style.display = 'block';
    btnAdmin.innerHTML = '<i class="fa-solid fa-user-shield"></i> Painel Admin';
    btnAdmin.className = 'btn btn-secondary btn-sm';
    btnAdmin.onclick = () => abrirLoginAdminModal();
    carregarDadosPortalCliente();
  } else {
    vCliente.style.display = 'block';
    btnAdmin.innerHTML = '<i class="fa-solid fa-user-shield"></i> Painel Admin';
    btnAdmin.className = 'btn btn-secondary btn-sm';
    btnAdmin.onclick = () => abrirLoginAdminModal();
  }
}


// --- AUTENTICAÇÃO DO CLIENTE ---

async function verificarSessaoCliente() {
  if (!state.clientToken) return;
  try {
    const res = await fetch('/api/auth/cliente/me', {
      headers: { 'X-Client-Token': state.clientToken }
    });
    if (res.ok) {
      state.clienteLogado = await res.json();
      atualizarUIClienteLogado();
    } else {
      logoutCliente();
    }
  } catch (err) {
    console.error('Erro checando sessão cliente:', err);
  }
}

function switchAuthCliTab(tab) {
  const btnLog = document.getElementById('tab-btn-cli-login');
  const btnCad = document.getElementById('tab-btn-cli-cad');
  const formLog = document.getElementById('form-auth-cli-login');
  const formCad = document.getElementById('form-auth-cli-cad');
  const formVal = document.getElementById('form-auth-cli-validar');

  if (formVal) formVal.style.display = 'none';

  if (tab === 'cad') {
    btnLog.classList.remove('active');
    btnCad.classList.add('active');
    formLog.style.display = 'none';
    formCad.style.display = 'block';
  } else {
    btnCad.classList.remove('active');
    btnLog.classList.add('active');
    formCad.style.display = 'none';
    formLog.style.display = 'block';
  }
}

async function loginCliente(e) {
  e.preventDefault();
  const email = document.getElementById('auth-cli-email').value.trim();
  const senha = document.getElementById('auth-cli-senha').value;

  try {
    const res = await fetch('/api/auth/cliente/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, senha })
    });
    const data = await res.json();

    if (res.ok) {
      state.clientToken = data.token;
      state.clienteLogado = data.cliente;
      localStorage.setItem('grafica_cli_token', data.token);
      
      // Auto-preencher dados de checkout
      document.getElementById('checkout-nome').value = data.cliente.nome;
      document.getElementById('checkout-telefone').value = data.cliente.telefone;
      if (data.cliente.endereco) document.getElementById('checkout-endereco').value = data.cliente.endereco;

      closeModal('modal-auth-cliente');
      atualizarUIClienteLogado();
      if (state.currentView === 'portal-cliente') carregarDadosPortalCliente();
      alert(`👋 Bem-vindo(a) de volta, ${data.cliente.nome}!`);
    } else {
      alert(data.error || 'Falha no login.');
    }
  } catch (err) {
    console.error('Erro login cliente:', err);
  }
}

async function cadastrarCliente(e) {
  e.preventDefault();
  const nome = document.getElementById('cad-cli-nome').value.trim();
  const email = document.getElementById('cad-cli-email').value.trim();
  const telefone = document.getElementById('cad-cli-telefone').value.trim();
  const senha = document.getElementById('cad-cli-senha').value;

  try {
    const res = await fetch('/api/auth/cliente/cadastrar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nome, email, telefone, senha })
    });
    const data = await res.json();

    if (res.ok) {
      if (data.requer_validacao) {
        document.getElementById('form-auth-cli-login').style.display = 'none';
        document.getElementById('form-auth-cli-cad').style.display = 'none';
        document.getElementById('form-auth-cli-validar').style.display = 'block';
        document.getElementById('validar-cli-id').value = data.cliente_id;
        document.getElementById('validar-cli-codigo').value = '';

        let msg = '📱 Código de validação enviado para o seu WhatsApp!';
        alert(msg);
      } else {
        state.clientToken = data.token;
        state.clienteLogado = data.cliente;
        localStorage.setItem('grafica_cli_token', data.token);

        closeModal('modal-auth-cliente');
        atualizarUIClienteLogado();
        if (state.currentView === 'portal-cliente') carregarDadosPortalCliente();
        alert(`🎉 Conta criada com sucesso! Bem-vindo(a), ${data.cliente.nome}!`);
      }
    } else {
      alert(data.error || 'Erro no cadastro.');
    }
  } catch (err) {
    console.error('Erro cadastro cliente:', err);
  }
}

async function validarCodigoCliente(e) {
  e.preventDefault();
  const cliente_id = parseInt(document.getElementById('validar-cli-id').value);
  const codigo = document.getElementById('validar-cli-codigo').value.trim();

  if (!codigo || codigo.length < 6) {
    alert('Por favor, informe o código de 6 dígitos enviado por WhatsApp.');
    return;
  }

  try {
    const res = await fetch('/api/auth/cliente/validar-codigo', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cliente_id, codigo })
    });
    const data = await res.json();

    if (res.ok) {
      state.clientToken = data.token;
      state.clienteLogado = data.cliente;
      localStorage.setItem('grafica_cli_token', data.token);

      closeModal('modal-auth-cliente');
      atualizarUIClienteLogado();
      if (state.currentView === 'portal-cliente') carregarDadosPortalCliente();
      alert(`🎉 Conta ativada com sucesso! Bem-vindo(a), ${data.cliente.nome}!`);
    } else {
      alert(data.error || 'Código inválido.');
    }
  } catch (err) {
    console.error('Erro validação código:', err);
  }
}

async function reenviarCodigoWhatsApp(e) {
  if (e) e.preventDefault();
  const cliente_id = parseInt(document.getElementById('validar-cli-id').value);
  if (!cliente_id) return;

  try {
    const res = await fetch('/api/auth/cliente/reenviar-codigo', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cliente_id })
    });
    const data = await res.json();

    if (res.ok) {
      let msg = '📱 Novo código enviado via WhatsApp!';
      alert(msg);
    } else {
      alert(data.error || 'Erro ao reenviar código.');
    }
  } catch (err) {
    console.error('Erro reenviar código:', err);
  }
}

function logoutCliente() {
  state.clientToken = '';
  state.clienteLogado = null;
  localStorage.removeItem('grafica_cli_token');
  atualizarUIClienteLogado();
  if (state.currentView === 'portal-cliente') switchView('cliente');
}

function atualizarUIClienteLogado() {
  const pDeslogado = document.getElementById('portal-deslogado');
  const pLogado = document.getElementById('portal-logado');
  const nNome = document.getElementById('cli-perfil-nome');
  const nEmail = document.getElementById('cli-perfil-email');

  if (state.clienteLogado) {
    if (pDeslogado) pDeslogado.style.display = 'none';
    if (pLogado) pLogado.style.display = 'block';
    if (nNome) nNome.innerText = state.clienteLogado.nome;
    if (nEmail) nEmail.innerText = `${state.clienteLogado.email} | WhatsApp: ${state.clienteLogado.telefone}`;
    
    // Auto-fill checkout fields
    const chkNome = document.getElementById('checkout-nome');
    const chkTel = document.getElementById('checkout-telefone');
    if (chkNome && !chkNome.value) chkNome.value = state.clienteLogado.nome;
    if (chkTel && !chkTel.value) chkTel.value = state.clienteLogado.telefone;
  } else {
    if (pDeslogado) pDeslogado.style.display = 'block';
    if (pLogado) pLogado.style.display = 'none';
  }
}

// --- AUTENTICAÇÃO DO ADMINISTRADOR ---

async function abrirLoginAdminModal() {
  if (state.adminToken) {
    try {
      const res = await fetch('/api/auth/admin/me', {
        headers: { 'X-Admin-Token': state.adminToken }
      });
      if (res.ok) {
        state.adminLogado = await res.json();
        switchView('admin');
        return;
      }
    } catch (err) {}
  }
  openModal('modal-auth-admin');
}

async function loginAdmin(e) {
  e.preventDefault();
  const usuario = document.getElementById('auth-adm-user').value.trim();
  const senha = document.getElementById('auth-adm-pass').value;

  try {
    const res = await fetch('/api/auth/admin/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ usuario, senha })
    });
    const data = await res.json();

    if (res.ok) {
      state.adminToken = data.admin_token;
      state.adminLogado = data.admin;
      localStorage.setItem('grafica_adm_token', data.admin_token);
      closeModal('modal-auth-admin');
      switchView('admin');
    } else {
      alert(data.error || 'Credenciais inválidas!');
    }
  } catch (err) {
    console.error('Erro login admin:', err);
  }
}

function logoutAdmin() {
  state.adminToken = '';
  state.adminLogado = null;
  localStorage.removeItem('grafica_adm_token');
  switchView('cliente');
}

// --- DATA FETCHING GENERAL ---

async function loadConfig() {
  try {
    const res = await fetch('/api/config');
    state.config = await res.json();
    
    const setTxt = (id, text) => {
      const el = document.getElementById(id);
      if (el) el.innerText = text;
    };
    const setVal = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.value = val;
    };

    setTxt('brand-name', state.config.nome_grafica || 'Gráfica Rápida Express');
    setTxt('top-bar-aviso', state.config.aviso_topo || '');
    setTxt('banner-titulo', state.config.banner_titulo || '');
    setTxt('banner-subtitulo', state.config.banner_subtitulo || '');
    
    setVal('cfg-nome-grafica', state.config.nome_grafica || '');
    setVal('cfg-whatsapp', state.config.whatsapp || '');
    setVal('cfg-chave-pix', state.config.chave_pix || '');
    setVal('cfg-banner-titulo', state.config.banner_titulo || '');
    setVal('cfg-banner-subtitulo', state.config.banner_subtitulo || '');
    setVal('cfg-aviso-topo', state.config.aviso_topo || '');
    
    const whInput = document.getElementById('cfg-webhook-url');
    if (whInput && !whInput.value) {
      whInput.value = window.location.origin + "/api/webhook/evolution";
    }
    
    setVal('cfg-desconto-pix', state.config.desconto_pix || 5.0);
    setVal('cfg-taxa-entrega', state.config.taxa_entrega || 15.0);
    setVal('pix-key-input', state.config.chave_pix || 'pix@graficarapidaexpress.com.br');

    setVal('cfg-evolution-url', state.config.evolution_api_url || '');
    setVal('cfg-evolution-key', state.config.evolution_api_key || '');
    setVal('cfg-evolution-instance', state.config.evolution_instance || '');
    setVal('cfg-evolution-active', state.config.validar_whatsapp_ativo ? '1' : '0');
  } catch (err) {
    console.error('Erro ao carregar configurações:', err);
  }
}

async function loadProdutos() {
  try {
    const res = await fetch('/api/produtos');
    state.produtos = await res.json();
    renderCatalog();
  } catch (err) {
    console.error('Erro ao carregar produtos:', err);
  }
}

// --- PORTAL DO CLIENTE DADOS ---

function switchPortalTab(tab, btn) {
  state.portalTab = tab;
  document.querySelectorAll('.portal-tab').forEach(t => t.classList.remove('active'));
  if (btn) btn.classList.add('active');

  ['historico', 'artes', 'orcamento'].forEach(t => {
    const el = document.getElementById(`portal-tab-${t}`);
    if (el) el.style.display = t === tab ? 'block' : 'none';
  });

  if (tab === 'artes') carregarArtesCliente();
}

async function carregarDadosPortalCliente() {
  if (!state.clienteLogado) return;

  try {
    const resPeds = await fetch('/api/cliente/pedidos', {
      headers: { 'X-Client-Token': state.clientToken }
    });
    const peds = await resPeds.json();
    
    const resOrcs = await fetch('/api/cliente/orcamentos', {
      headers: { 'X-Client-Token': state.clientToken }
    });
    const orcs = await resOrcs.json();

    const container = document.getElementById('portal-pedidos-lista');

    if (peds.length === 0 && orcs.length === 0) {
      container.innerHTML = '<div style="text-align: center; color: var(--text-muted); padding: 40px;">Você ainda não possui pedidos ou orçamentos cadastrados. Faça sua primeira compra na loja!</div>';
      return;
    }

    let html = '';

    if (peds.length > 0) {
      html += '<h3 style="margin-top: 0; margin-bottom: 15px; color: var(--primary);">Meus Pedidos</h3>';
      html += peds.map(p => `
        <div class="table-wrap" style="padding: 20px; margin-bottom: 20px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
            <div>
              <strong style="font-size: 1.1rem;">${p.codigo_pedido}</strong>
              <span style="color: var(--text-muted); font-size: 0.85rem; margin-left: 10px;">${new Date(p.data_criacao).toLocaleDateString('pt-BR')}</span>
            </div>
            <div>
              <span class="badge ${p.status_pagamento === 'Aprovado' ? 'badge-success' : 'badge-warning'}">${p.status_pagamento}</span>
              <span class="badge badge-info">${p.status_producao}</span>
            </div>
          </div>

          <ul style="padding-left: 20px; margin-bottom: 14px; font-size: 0.9rem;">
            ${p.itens.map(i => `<li>${i.quantidade}x ${i.produto_nome} (${i.tamanho}, ${i.papel}) - R$ ${i.preco_total.toFixed(2).replace('.', ',')}</li>`).join('')}
          </ul>

          <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--border-color); padding-top: 12px;">
            <div>Total: <strong style="font-size: 1.2rem; color: var(--primary);">R$ ${p.total.toFixed(2).replace('.', ',')}</strong></div>
            <div style="display: flex; gap: 10px;">
              <button class="btn btn-secondary btn-sm" onclick="repetirPedidoCliente(${p.id})">
                <i class="fa-solid fa-rotate-right"></i> Pedir Novamente
              </button>
              <button class="btn btn-secondary btn-sm" style="color: #25d366;" onclick="abrirChatWidget('${p.codigo_pedido}')">
                <i class="fa-solid fa-comments"></i> Chat
              </button>
              <button class="btn btn-primary btn-sm" onclick="consultarPedidoCodigo('${p.codigo_pedido}')">
                <i class="fa-solid fa-truck-fast"></i> Rastrear
              </button>
            </div>
          </div>
        </div>
      `).join('');
    }

    if (orcs.length > 0) {
      html += '<h3 style="margin-top: 20px; margin-bottom: 15px; color: var(--primary);">Meus Orçamentos</h3>';
      html += orcs.map(o => `
        <div class="table-wrap" style="padding: 20px; margin-bottom: 20px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
            <div>
              <strong style="font-size: 1.1rem;">${o.codigo_orcamento}</strong>
              <span style="color: var(--text-muted); font-size: 0.85rem; margin-left: 10px;">${new Date(o.data_criacao).toLocaleDateString('pt-BR')}</span>
            </div>
            <div>
              <span class="badge ${o.status === 'Aprovado' ? 'badge-success' : o.status === 'Rejeitado' ? 'badge-danger' : o.status === 'Concluído' ? 'badge-info' : 'badge-warning'}">${o.status}</span>
            </div>
          </div>
          <p style="font-size: 0.95rem; margin-bottom: 10px; color: var(--text-color);">${o.descricao}</p>
          <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--border-color); padding-top: 12px;">
            <div>Valor Estimado: <strong style="font-size: 1.1rem; color: var(--primary);">R$ ${o.valor_estimado.toFixed(2).replace('.', ',')}</strong></div>
            <button onclick="abrirChatWidget('${o.codigo_orcamento}')" class="btn btn-secondary btn-sm" style="color: #25d366;">
              <i class="fa-brands fa-whatsapp"></i> Chat do Orçamento
            </button>
          </div>
        </div>
      `).join('');
    }

    container.innerHTML = html;
  } catch (err) {
    console.error('Erro portal cliente:', err);
  }
}

async function carregarArtesCliente() {
  if (!state.clienteLogado) return;
  try {
    const res = await fetch('/api/cliente/artes', {
      headers: { 'X-Client-Token': state.clientToken }
    });
    const artes = await res.json();
    const container = document.getElementById('portal-artes-grid');

    if (artes.length === 0) {
      container.innerHTML = '<div style="grid-column: 1/-1; text-align: center; color: var(--text-muted); padding: 30px;">Sua biblioteca de artes está vazia. Faça o upload dos seus logotipos acima.</div>';
      return;
    }

    container.innerHTML = artes.map(a => `
      <div class="product-card" style="padding: 14px;">
        <div style="font-weight: 700; font-size: 0.9rem; margin-bottom: 8px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${a.nome_arquivo}</div>
        <a href="${a.url_arquivo}" target="_blank" class="btn btn-secondary btn-sm" style="width: 100%; margin-bottom: 6px;">
          <i class="fa-solid fa-eye"></i> Visualizar Arte
        </a>
        <button class="btn btn-secondary btn-sm" style="width: 100%; color: var(--danger);" onclick="deletarArteCliente(${a.id})">
          <i class="fa-solid fa-trash"></i> Excluir
        </button>
      </div>
    `).join('');
  } catch (err) {
    console.error('Erro artes:', err);
  }
}

async function uploadPortalArteFile(input) {
  if (!input.files || !input.files[0] || !state.clienteLogado) return;
  const file = input.files[0];
  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await fetch('/api/upload', { method: 'POST', body: formData });
    const data = await res.json();
    if (res.ok) {
      await fetch('/api/cliente/artes', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'X-Client-Token': state.clientToken 
        },
        body: JSON.stringify({
          nome_arquivo: file.name,
          url_arquivo: data.url,
          tamanho_bytes: file.size
        })
      });
      carregarArtesCliente();
    }
  } catch (err) {
    console.error('Erro upload arte portal:', err);
  }
}

async function deletarArteCliente(id) {
  if (!(await window.confirmAsync('Deseja remover esta arte da sua biblioteca?'))) return;
  try {
    await fetch(`/api/cliente/artes?id=${id}`, {
      method: 'DELETE',
      headers: { 'X-Client-Token': state.clientToken }
    });
    carregarArtesCliente();
  } catch (err) {
    console.error('Erro delete arte:', err);
  }
}

async function repetirPedidoCliente(pedidoId) {
  try {
    const res = await fetch(`/api/pedidos/${pedidoId}`);
    const ped = await res.json();
    
    ped.itens.forEach(i => {
      state.carrinho.push({
        produto_id: i.produto_id,
        produto_nome: i.produto_nome,
        tamanho: i.tamanho,
        papel: i.papel,
        acabamento: i.acabamento,
        quantidade: i.quantidade,
        preco_unitario: i.preco_unitario,
        preco_total: i.preco_total,
        arte_url: i.arte_url,
        criar_arte: i.criar_arte === 1,
        detalhes_arte: i.detalhes_arte
      });
    });

    saveCart();
    toggleCartDrawer(true);
  } catch (err) {
    console.error('Erro repetir pedido:', err);
  }
}

async function solicitarOrcamentoCliente(e) {
  e.preventDefault();
  const desc = document.getElementById('orc-cli-desc').value;

  try {
    const res = await fetch('/api/orcamentos', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        cliente_id: state.clienteLogado ? state.clienteLogado.id : null,
        cliente_nome: state.clienteLogado ? state.clienteLogado.nome : 'Cliente Site',
        cliente_telefone: state.clienteLogado ? state.clienteLogado.telefone : '',
        descricao: desc,
        valor_estimado: 0.0
      })
    });
    const data = await res.json();
    if (res.ok) {
      alert(`🎉 Solicitação de Orçamento enviada com sucesso (${data.codigo})! Em breve entraremos em contato via WhatsApp.`);
      e.target.reset();
    }
  } catch (err) {
    console.error('Erro orcamento cliente:', err);
  }
}

// --- CATALOG & CALCULATOR ---

function filterCategory(cat, btn) {
  state.activeCategory = cat;
  document.querySelectorAll('.category-tabs .tab-btn').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
  renderCatalog();
}

function parseIfString(val) {
  if (!val) return [];
  if (Array.isArray(val)) return val;
  if (typeof val === 'string') {
    try {
      const parsed = JSON.parse(val);
      return Array.isArray(parsed) ? parsed : [val];
    } catch (e) {
      return [val];
    }
  }
  return [];
}

function renderCatalog() {
  const container = document.getElementById('catalog-grid');
  if (!container) return;
  
  const prods = state.activeCategory === 'Todos' 
    ? state.produtos 
    : state.produtos.filter(p => p.categoria === state.activeCategory);

  if (prods.length === 0) {
    container.innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 40px; color: var(--text-muted);">Nenhum produto encontrado nesta categoria.</div>';
    return;
  }


  container.innerHTML = prods.map(p => `
    <div class="product-card" onclick="openProdutoModal(${p.id})" style="cursor: pointer;">
      <div class="card-image-wrap">
        <img src="${p.imagem_url}" alt="${p.nome}" class="product-img">
        ${p.destaque ? '<span class="card-badge"><i class="fa-solid fa-fire"></i> Mais Vendido</span>' : ''}
      </div>
      <div class="card-body">
        <h3 class="product-title">${p.nome}</h3>
        <p class="product-desc">${p.descricao || ''}</p>
        <div class="price-row">
          <div>
            <div class="price-label">A partir de</div>
            <div class="price-val">R$ ${(p.preco_base || 0).toFixed(2).replace('.', ',')}</div>
          </div>
          <button class="btn btn-primary btn-sm" onclick="event.stopPropagation(); openProdutoModal(${p.id})">
            <i class="fa-solid fa-calculator"></i> Personalizar
          </button>
        </div>
      </div>
    </div>
  `).join('');
}

function openProdutoModal(prodId) {
  if (!state.produtos || state.produtos.length === 0) return;
  const prod = state.produtos.find(p => String(p.id) === String(prodId));
  if (!prod) return;

  prod.tamanhos = parseIfString(prod.tamanhos);
  prod.papeis = parseIfString(prod.papeis);
  prod.acabamentos = parseIfString(prod.acabamentos);
  prod.tiragens = parseIfString(prod.tiragens);

  state.produtoSelecionado = prod;
  state.opcoesSelecionadas = {
    tamanho: prod.tamanhos[0] || 'Padrão',
    papel: prod.papeis[0] || 'Standard',
    acabamento: prod.acabamentos[0] || 'Sem acabamento',
    tiragem: prod.tiragens[0] || { qtd: 1, preco: prod.preco_base || 0 },
    arteUrl: '',
    criarArte: false,
    detalhesArte: '',
    precoTotal: 0
  };

  const elId = document.getElementById('modal-prod-id');
  if (elId) elId.value = prod.id;
  const elTitle = document.getElementById('modal-prod-title');
  if (elTitle) elTitle.innerText = prod.nome || 'Personalizar Produto';
  const elDesc = document.getElementById('modal-prod-desc');
  if (elDesc) elDesc.innerText = prod.descricao || '';

  renderChips('opt-tamanhos', prod.tamanhos, state.opcoesSelecionadas.tamanho);
  renderChips('opt-papeis', prod.papeis, state.opcoesSelecionadas.papel);
  renderChips('opt-acabamentos', prod.acabamentos, state.opcoesSelecionadas.acabamento);

  const containerTir = document.getElementById('opt-tiragens');
  if (containerTir && prod.tiragens) {
    containerTir.innerHTML = prod.tiragens.map((t, idx) => `
      <div class="chip-option ${idx === 0 ? 'selected' : ''}" onclick="selectTiragem(${idx}, this)">
        <div style="font-weight: 800; font-size: 1.05rem;">${t.qtd || 1} un</div>
        <div style="font-size: 0.8rem; color: var(--primary);">R$ ${(t.preco || 0).toFixed(2).replace('.', ',')}</div>
      </div>
    `).join('');
  }

  const elFile = document.getElementById('filename-uploaded');
  if (elFile) elFile.innerText = 'Nenhum arquivo selecionado (PDF/PNG/JPG)';
  calcularTotalModal();
  openModal('modal-produto');
}

function renderChips(containerId, list, initialVal) {
  const c = document.getElementById(containerId);
  if (!c) return;
  const items = Array.isArray(list) ? list : [];
  c.innerHTML = items.map(item => `
    <div class="chip-option ${item === initialVal ? 'selected' : ''}" onclick="selectChip(this, '${containerId}')">
      ${item}
    </div>
  `).join('');

  // c.dataset.onSelect = onSelect;
}

function selectChip(el, containerId) {
  const parent = document.getElementById(containerId);
  parent.querySelectorAll('.chip-option').forEach(child => child.classList.remove('selected'));
  el.classList.add('selected');
  const val = el.innerText.trim();
  
  if (containerId === 'opt-tamanhos') state.opcoesSelecionadas.tamanho = val;
  if (containerId === 'opt-papeis') state.opcoesSelecionadas.papel = val;
  if (containerId === 'opt-acabamentos') state.opcoesSelecionadas.acabamento = val;
  
  calcularTotalModal();
}

function selectTiragem(index, el) {
  document.querySelectorAll('#opt-tiragens .chip-option').forEach(c => c.classList.remove('selected'));
  el.classList.add('selected');
  state.opcoesSelecionadas.tiragem = state.produtoSelecionado.tiragens[index];
  calcularTotalModal();
}

function toggleArteOpcoes() {
  const val = document.querySelector('input[name="opcao-arte"]:checked').value;
  const wrapUpload = document.getElementById('wrap-upload-arte');
  const wrapDetalhes = document.getElementById('wrap-detalhes-arte');
  
  if (val === 'criar') {
    wrapUpload.style.display = 'none';
    wrapDetalhes.style.display = 'block';
    state.opcoesSelecionadas.criarArte = true;
  } else {
    wrapUpload.style.display = 'block';
    wrapDetalhes.style.display = 'none';
    state.opcoesSelecionadas.criarArte = false;
  }
  calcularTotalModal();
}

function calcularTotalModal() {
  let subtotal = state.opcoesSelecionadas.tiragem ? state.opcoesSelecionadas.tiragem.preco : state.produtoSelecionado.preco_base;
  if (state.opcoesSelecionadas.criarArte) {
    subtotal += 35.00;
  }
  state.opcoesSelecionadas.precoTotal = subtotal;
  document.getElementById('modal-calc-total').innerText = `R$ ${subtotal.toFixed(2).replace('.', ',')}`;
}

async function uploadArteFile(input) {
  if (!input.files || !input.files[0]) return;
  const file = input.files[0];
  document.getElementById('filename-uploaded').innerText = `Enviando ${file.name}...`;

  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await fetch('/api/upload', { method: 'POST', body: formData });
    const data = await res.json();
    if (res.ok) {
      state.opcoesSelecionadas.arteUrl = data.url;
      document.getElementById('filename-uploaded').innerText = `✅ Arquivo enviado: ${data.filename}`;
    } else {
      alert(data.error || 'Erro no envio do arquivo.');
    }
  } catch (err) {
    console.error('Erro no upload:', err);
  }
}

// --- CARRINHO & CHECKOUT ---

function adicionarAoCarrinho() {
  if (state.opcoesSelecionadas.criarArte) {
    state.opcoesSelecionadas.detalhesArte = document.getElementById('detalhes-arte-txt').value;
  }

  const cartItem = {
    produto_id: state.produtoSelecionado.id,
    produto_nome: state.produtoSelecionado.nome,
    tamanho: state.opcoesSelecionadas.tamanho,
    papel: state.opcoesSelecionadas.papel,
    acabamento: state.opcoesSelecionadas.acabamento,
    quantidade: state.opcoesSelecionadas.tiragem ? state.opcoesSelecionadas.tiragem.qtd : 1,
    preco_unitario: state.opcoesSelecionadas.precoTotal / (state.opcoesSelecionadas.tiragem ? state.opcoesSelecionadas.tiragem.qtd : 1),
    preco_total: state.opcoesSelecionadas.precoTotal,
    arte_url: state.opcoesSelecionadas.arteUrl,
    criar_arte: state.opcoesSelecionadas.criarArte,
    detalhes_arte: state.opcoesSelecionadas.detalhesArte
  };

  state.carrinho.push(cartItem);
  saveCart();
  closeModal('modal-produto');
  toggleCartDrawer(true);
}

function saveCart() {
  localStorage.setItem('grafica_carrinho', JSON.stringify(state.carrinho));
  updateCartBadge();
}

function updateCartBadge() {
  const count = state.carrinho.length;
  document.getElementById('cart-count').innerText = count;
}

function toggleCartDrawer(openForce) {
  const drawer = document.getElementById('cart-drawer');
  if (openForce || !drawer.classList.contains('open')) {
    drawer.classList.add('open');
    renderCart();
  } else {
    drawer.classList.remove('open');
  }
}

function renderCart() {
  const container = document.getElementById('cart-body');
  if (state.carrinho.length === 0) {
    container.innerHTML = '<div style="text-align: center; color: var(--text-muted); padding: 40px 0;">Seu carrinho está vazio.</div>';
    atualizarTotalCheckout();
    return;
  }

  container.innerHTML = state.carrinho.map((item, idx) => `
    <div class="cart-item">
      <div style="flex-grow: 1;">
        <div style="font-weight: 700; font-size: 0.95rem;">${item.produto_nome}</div>
        <div style="font-size: 0.8rem; color: var(--text-muted);">
          ${item.tamanho} | ${item.papel}<br>
          Acabamento: ${item.acabamento}<br>
          Qtd: ${item.quantidade} un ${item.criar_arte ? '<br><span style="color: var(--cyan); font-weight:700;">+ Criação de Arte</span>' : ''}
        </div>
        <div style="font-weight: 800; color: var(--primary); margin-top: 6px;">
          R$ ${item.preco_total.toFixed(2).replace('.', ',')}
        </div>
      </div>
      <button class="modal-close" style="font-size: 1.2rem; align-self: flex-start;" onclick="removerDoCarrinho(${idx})">&times;</button>
    </div>
  `).join('');

  atualizarTotalCheckout();
}

function removerDoCarrinho(index) {
  state.carrinho.splice(index, 1);
  saveCart();
  renderCart();
}

async function aplicarCupomCheckout() {
  const cod = document.getElementById('checkout-cupom-input').value.trim();
  const feedback = document.getElementById('cupom-msg-feedback');
  if (!cod) return;

  const subtotal = state.carrinho.reduce((acc, item) => acc + item.preco_total, 0);

  try {
    const res = await fetch('/api/cupons/validar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ codigo: cod, subtotal: subtotal })
    });
    const data = await res.json();
    if (res.ok && data.valid) {
      state.cupomAplicado = data;
      feedback.style.color = 'var(--success)';
      feedback.innerText = `✅ ${data.message}`;
      atualizarTotalCheckout();
    } else {
      state.cupomAplicado = null;
      feedback.style.color = 'var(--danger)';
      feedback.innerText = `❌ ${data.message || 'Cupom inválido'}`;
      atualizarTotalCheckout();
    }
  } catch (err) {
    console.error('Erro cupom:', err);
  }
}

function atualizarTotalCheckout() {
  const subtotal = state.carrinho.reduce((acc, item) => acc + item.preco_total, 0);
  const pag = document.getElementById('checkout-pagamento').value;
  const entrega = document.getElementById('checkout-entrega').value;
  
  const wrapEnd = document.getElementById('wrap-endereco-entrega');
  wrapEnd.style.display = entrega === 'Entrega' ? 'block' : 'none';

  let taxaEntrega = entrega === 'Entrega' ? (state.config.taxa_entrega || 15.0) : 0.0;
  let descontoPix = pag === 'PIX' ? subtotal * ((state.config.desconto_pix || 5.0) / 100.0) : 0.0;
  let descontoCupom = state.cupomAplicado ? state.cupomAplicado.desconto_valor : 0.0;

  const total = Math.max(0, subtotal + taxaEntrega - descontoPix - descontoCupom);
  document.getElementById('checkout-total-val').innerText = `R$ ${total.toFixed(2).replace('.', ',')}`;
}

async function finalizarPedidoCheckout() {
  let nome = document.getElementById('checkout-nome').value.trim();
  let telefone = document.getElementById('checkout-telefone').value.trim();
  const pagamento = document.getElementById('checkout-pagamento').value;
  const entrega = document.getElementById('checkout-entrega').value;
  const endereco = document.getElementById('checkout-endereco').value.trim();

  if (state.clienteLogado) {
    if (!nome) nome = state.clienteLogado.nome;
    if (!telefone) telefone = state.clienteLogado.telefone;
  }

  if (!nome || !telefone) {
    Swal.fire({
      icon: 'warning',
      title: 'Atenção',
      text: 'Por favor, informe seu Nome Completo e WhatsApp!',
      background: document.body.classList.contains('dark-mode') ? '#1e1e2d' : '#ffffff',
      color: document.body.classList.contains('dark-mode') ? '#f3f4f6' : '#1f2937'
    });
    return;
  }
  if (state.carrinho.length === 0) {
    alert('Seu carrinho está vazio!');
    return;
  }

  const subtotal = state.carrinho.reduce((acc, item) => acc + item.preco_total, 0);
  const taxaEntrega = entrega === 'Entrega' ? (state.config.taxa_entrega || 15.0) : 0.0;
  const descontoPix = pagamento === 'PIX' ? subtotal * ((state.config.desconto_pix || 5.0) / 100.0) : 0.0;
  const descontoCupom = state.cupomAplicado ? state.cupomAplicado.desconto_valor : 0.0;
  const total = Math.max(0, subtotal + taxaEntrega - descontoPix - descontoCupom);

  const payload = {
    cliente: { 
      nome, 
      telefone, 
      email: state.clienteLogado ? state.clienteLogado.email : '',
      endereco 
    },
    itens: state.carrinho,
    total: total,
    desconto: descontoPix + descontoCupom,
    taxa_entrega: taxaEntrega,
    metodo_pagamento: pagamento,
    tipo_entrega: entrega,
    endereco_entrega: endereco,
    cupom: state.cupomAplicado ? state.cupomAplicado.codigo : null
  };

  try {
    const res = await fetch('/api/pedidos', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();

    if (res.ok) {
      state.ultimoPedidoCodigo = data.codigo_pedido;
      state.carrinho = [];
      state.cupomAplicado = null;
      saveCart();
      toggleCartDrawer(false);

      if (pagamento === 'PIX') {
        openModal('modal-pix');
      } else {
        alert(`🎉 Pedido ${data.codigo_pedido} realizado com sucesso! Acompanhe seu status.`);
        consultarPedidoCodigo(data.codigo_pedido);
      }
    } else {
      alert(data.error || 'Erro ao processar pedido.');
    }
  } catch (err) {
    console.error('Erro checkout:', err);
    alert('Falha ao conectar com o servidor.');
  }
}

function copiarChavePix() {
  const input = document.getElementById('pix-key-input');
  input.select();
  document.execCommand('copy');
  alert('Chave PIX copiada para a área de transferência!');
}

function confirmarEVerPedido() {
  closeModal('modal-pix');
  if (state.ultimoPedidoCodigo) {
    consultarPedidoCodigo(state.ultimoPedidoCodigo);
  }
}

// --- RASTREAMENTO DE PEDIDO ---

function openMeusPedidosModal() {
  document.getElementById('search-codigo-pedido').value = '';
  const detalhes = document.getElementById('detalhes-pedido-rastreio');
  if (detalhes) detalhes.style.display = 'none';
  openModal('modal-meus-pedidos');
}

async function consultarPedidoCliente() {
  const cod = document.getElementById('search-codigo-pedido').value.trim();
  if (!cod) return;
  consultarPedidoCodigo(cod);
}

async function consultarPedidoCodigo(codigo) {
  try {
    // Remove the # to avoid proxy/WAF issues with URL fragments, the backend will put it back
    const safeCodigo = codigo.replace('#', '');
    const res = await fetch(`/api/pedidos/${encodeURIComponent(safeCodigo)}`);
    const ped = await res.json();

    if (!res.ok) {
      alert(ped.error || 'Pedido não encontrado.');
      return;
    }

    document.getElementById('detalhes-pedido-rastreio').style.display = 'block';
    document.getElementById('tr-codigo').innerText = ped.codigo_pedido;
    document.getElementById('tr-status-pag').innerText = `${ped.status_pagamento} (${ped.metodo_pagamento})`;
    document.getElementById('tr-cliente-info').innerText = `Cliente: ${ped.cliente_nome} | Tel: ${ped.cliente_telefone} | Entrega: ${ped.tipo_entrega}`;
    document.getElementById('tr-total').innerText = `R$ ${ped.total.toFixed(2).replace('.', ',')}`;

    document.getElementById('tr-itens-ul').innerHTML = ped.itens.map(i => `
      <li>${i.quantidade}x ${i.produto_nome} (${i.tamanho}, ${i.papel}) - <strong>R$ ${i.preco_total.toFixed(2).replace('.', ',')}</strong></li>
    `).join('');

    updateTimelineVisual(ped.status_producao, ped.status_pagamento);
    openModal('modal-meus-pedidos');
  } catch (err) {
    console.error('Erro rastreio:', err);
  }
}

function updateTimelineVisual(statusProd, statusPag) {
  const steps = ['step-pagamento', 'step-analise', 'step-impressao', 'step-acabamento', 'step-pronto', 'step-entregue'];
  steps.forEach(s => {
    const el = document.getElementById(s);
    if (el) el.className = 'timeline-step';
  });

  let activeIdx = 0;
  if (statusPag === 'Aprovado') activeIdx = 1;
  if (statusProd === 'Em Análise de Arte') activeIdx = 1;
  if (statusProd === 'Em Impressão') activeIdx = 2;
  if (statusProd === 'Acabamento & Corte') activeIdx = 3;
  if (statusProd === 'Pronto para Retirada') activeIdx = 4;
  if (statusProd === 'Entregue') activeIdx = 5;

  for (let i = 0; i <= activeIdx; i++) {
    const el = document.getElementById(steps[i]);
    if (el) {
      if (i === activeIdx) el.classList.add('active');
      else el.classList.add('completed');
    }
  }
}

function falarWhatsApp() {
  const w = state.config.whatsapp || '5511999998888';
  window.open(`https://wa.me/${w}?text=Olá! Gostaria de tirar uma dúvida sobre serviços de impressão.`, '_blank');
}

function falarWhatsAppPedido() {
  const cod = document.getElementById('tr-codigo').innerText;
  const w = state.config.whatsapp || '5511999998888';
  window.open(`https://wa.me/${w}?text=Olá! Gostaria de falar sobre o meu pedido ${cod}.`, '_blank');
}

// ==========================================================================
// PAINEL ADMINISTRATIVO (COM AUTENTICAÇÃO RESTREITA)
// ==========================================================================

function switchAdminTab(tab, btn) {
  state.adminTab = tab;
  document.querySelectorAll('.sidebar-item').forEach(i => i.classList.remove('active'));
  if (btn) btn.classList.add('active');

  const tabs = ['dashboard', 'kanban', 'pedidos', 'produtos', 'estoque', 'caixa', 'orcamentos', 'cupons', 'clientes', 'config', 'whatsapp'];
  tabs.forEach(t => {
    const el = document.getElementById(`admin-tab-${t}`);
    if (el) el.style.display = t === tab ? (t === 'whatsapp' ? 'flex' : 'block') : 'none';
  });

  if (tab === 'dashboard') loadDashboardMetrics();
  if (tab === 'kanban') loadKanbanBoard();
  if (tab === 'pedidos') loadAdminPedidos();
  if (tab === 'produtos') loadAdminProdutos();
  if (tab === 'estoque') loadAdminEstoque();
  if (tab === 'caixa') loadAdminCaixa();
  if (tab === 'orcamentos') loadAdminOrcamentos();
  if (tab === 'cupons') loadAdminCupons();
  if (tab === 'clientes') loadAdminClientes();
  if (tab === 'whatsapp') loadWhatsAppInbox();
}

async function loadDashboardMetrics() {
  try {
    const res = await fetch('/api/dashboard', {
      headers: { 'X-Admin-Token': state.adminToken }
    });
    if (!res.ok) {
      logoutAdmin();
      return;
    }
    const data = await res.json();

    document.getElementById('dash-faturamento').innerText = `R$ ${data.faturamento_total.toFixed(2).replace('.', ',')}`;
    document.getElementById('dash-pedidos-total').innerText = data.total_pedidos;
    document.getElementById('dash-pedidos-producao').innerText = data.pedidos_em_producao;
    document.getElementById('dash-clientes').innerText = data.total_clientes;

    const resP = await fetch('/api/pedidos', {
      headers: { 'X-Admin-Token': state.adminToken }
    });
    const peds = await resP.json();
    const recent = peds.slice(0, 5);

    document.getElementById('dash-pedidos-tbody').innerHTML = recent.map(p => `
      <tr>
        <td><strong>${p.codigo_pedido}</strong></td>
        <td>${p.cliente_nome}</td>
        <td>R$ ${p.total.toFixed(2).replace('.', ',')}</td>
        <td><span class="badge ${p.status_pagamento === 'Aprovado' ? 'badge-success' : 'badge-warning'}">${p.status_pagamento}</span></td>
        <td><span class="badge badge-info">${p.status_producao}</span></td>
        <td>
          <button class="btn btn-secondary btn-sm" onclick="imprimirOS(${p.id})"><i class="fa-solid fa-print"></i> OS</button>
        </td>
      </tr>
    `).join('');
  } catch (err) {
    console.error('Erro dashboard:', err);
  }
}

// --- KANBAN DE PRODUÇÃO ---

async function loadKanbanBoard() {
  try {
    const res = await fetch('/api/pedidos', {
      headers: { 'X-Admin-Token': state.adminToken }
    });
    const peds = await res.json(); state.pedidosCache = peds;

    const analise = peds.filter(p => p.status_producao === 'Em Análise de Arte');
    const impressao = peds.filter(p => p.status_producao === 'Em Impressão');
    const acabamento = peds.filter(p => p.status_producao === 'Acabamento & Corte');
    const pronto = peds.filter(p => p.status_producao === 'Pronto para Retirada' || p.status_producao === 'Entregue');

    document.getElementById('kanban-count-analise').innerText = analise.length;
    document.getElementById('kanban-count-impressao').innerText = impressao.length;
    document.getElementById('kanban-count-acabamento').innerText = acabamento.length;
    document.getElementById('kanban-count-pronto').innerText = pronto.length;

    renderKanbanCol('kanban-cards-analise', analise, 'Em Impressão');
    renderKanbanCol('kanban-cards-impressao', impressao, 'Acabamento & Corte');
    renderKanbanCol('kanban-cards-acabamento', acabamento, 'Pronto para Retirada');
    renderKanbanCol('kanban-cards-pronto', pronto, 'Entregue');
  } catch (err) {
    console.error('Erro kanban:', err);
  }
}

function renderKanbanCol(elementId, items, proximoStatus) {
  const c = document.getElementById(elementId);
  if (!c) return;
  if (items.length === 0) {
    c.innerHTML = '<div style="text-align: center; color: var(--text-muted); font-size: 0.8rem; padding: 20px 0;">Vazio</div>';
    return;
  }

  c.innerHTML = items.map(p => `
    <div class="kanban-card">
      <div style="font-weight: 800; font-size: 0.95rem; margin-bottom: 4px;">${p.codigo_pedido}</div>
      <div style="font-size: 0.85rem; color: var(--text-muted);">${p.cliente_nome} (${p.cliente_telefone})</div>
      <div style="font-size: 0.8rem; font-weight: 700; margin: 8px 0; color: var(--primary);">
        R$ ${p.total.toFixed(2).replace('.', ',')} | ${p.metodo_pagamento}
      </div>
      <div style="display: flex; gap: 6px; margin-top: 8px;">
        <button class="btn btn-secondary btn-sm" style="flex: 1; font-size: 0.75rem;" onclick="imprimirOS(${p.id})">
          <i class="fa-solid fa-print"></i> OS
        </button>
        <button class="btn btn-primary btn-sm" style="flex: 1; font-size: 0.75rem;" onclick="alterarStatusPedido(${p.id}, '${proximoStatus}', null)">
          Avançar <i class="fa-solid fa-arrow-right"></i>
        </button>
      </div>
    </div>
  `).join('');
}

// --- PEDIDOS (ADMIN LISTA) ---

async function loadAdminPedidos() {
  const search = document.getElementById('admin-pedidos-search').value;
  const status = document.getElementById('admin-pedidos-filter').value;

  try {
    const res = await fetch(`/api/pedidos?search=${encodeURIComponent(search)}&status=${encodeURIComponent(status)}`, {
      headers: { 'X-Admin-Token': state.adminToken }
    });
    const peds = await res.json(); state.pedidosCache = peds;

    document.getElementById('admin-pedidos-tbody').innerHTML = peds.map(p => `
      <tr>
        <td>${new Date(p.data_criacao).toLocaleDateString('pt-BR')} ${new Date(p.data_criacao).toLocaleTimeString('pt-BR', {hour: '2-digit', minute:'2-digit'})}</td>
        <td><strong>${p.codigo_pedido}</strong></td>
        <td>
          ${p.cliente_nome}<br>
          <small style="color: var(--text-muted);">${p.cliente_telefone}</small>
        </td>
        <td>R$ ${p.total.toFixed(2).replace('.', ',')}</td>
        <td>
          <select class="form-control" style="padding: 4px 8px; font-size: 0.8rem;" onchange="alterarStatusPedido(${p.id}, null, this.value)">
            <option value="Aguardando Pagamento" ${p.status_pagamento === 'Aguardando Pagamento' ? 'selected' : ''}>Aguardando</option>
            <option value="Aprovado" ${p.status_pagamento === 'Aprovado' ? 'selected' : ''}>Aprovado</option>
          </select>
        </td>
        <td>
          <select class="form-control" style="padding: 4px 8px; font-size: 0.8rem;" onchange="alterarStatusPedido(${p.id}, this.value, null)">
            <option value="Aguardando Pagamento" ${p.status_producao === 'Aguardando Pagamento' ? 'selected' : ''}>Aguardando Pagto</option>
            <option value="Em Análise de Arte" ${p.status_producao === 'Em Análise de Arte' ? 'selected' : ''}>Em Análise Arte</option>
            <option value="Em Impressão" ${p.status_producao === 'Em Impressão' ? 'selected' : ''}>Em Impressão</option>
            <option value="Acabamento & Corte" ${p.status_producao === 'Acabamento & Corte' ? 'selected' : ''}>Acabamento/Corte</option>
            <option value="Pronto para Retirada" ${p.status_producao === 'Pronto para Retirada' ? 'selected' : ''}>Pronto p/ Retirar</option>
            <option value="Entregue" ${p.status_producao === 'Entregue' ? 'selected' : ''}>Entregue</option>
          </select>
        </td>
        <td>
          <div style="display: flex; gap: 5px; flex-wrap: wrap;">
            <button class="btn btn-secondary btn-sm" onclick="verArquivosPedido(${p.id})" title="Ver Arquivos da Arte"><i class="fa-solid fa-folder-open"></i></button>
            <button class="btn btn-secondary btn-sm" onclick="imprimirOS(${p.id})" title="Imprimir Ordem de Serviço"><i class="fa-solid fa-print"></i></button>
            <button class="btn btn-danger btn-sm" onclick="excluirPedidoAdmin(${p.id})" title="Excluir Pedido"><i class="fa-solid fa-trash"></i></button>
            <button onclick="abrirChatWidget('${p.codigo_pedido}', '${p.cliente_telefone}', '${p.cliente_nome}')" class="btn btn-secondary btn-sm" style="color: #25d366;" title="Chat Interno">
              <i class="fa-solid fa-comments"></i>
            </button>
            <button onclick="abrirConversaInterna('${p.cliente_telefone}', '${p.cliente_nome}')" class="btn btn-secondary btn-sm" style="color: #25d366;" title="WhatsApp Interno">
              <i class="fa-brands fa-whatsapp"></i>
            </button>
          </div>
        </td>
      </tr>
    `).join('');
  } catch (err) {
    console.error('Erro admin pedidos:', err);
  }
}

function verArquivosPedido(id) {
  const p = (state.pedidosCache || []).find(x => x.id === id);
  if (!p) return;

  const arquivos = (p.itens || []).filter(i => i.arte_url).map(i => `
    <div style="margin-bottom: 10px; text-align: left; background: var(--bg-color, #f3f4f6); padding: 10px; border-radius: 8px;">
      <strong style="font-size: 0.9rem;">${i.produto_nome}</strong><br>
      <span style="font-size: 0.8rem; color: #666;">Tamanho: ${i.tamanho} | ${i.papel}</span><br>
      <a href="${i.arte_url}" target="_blank" class="btn btn-primary btn-sm" style="margin-top: 5px; display: inline-block;">
        <i class="fa-solid fa-download"></i> Baixar Arquivo
      </a>
    </div>
  `).join('');
  
  if (!arquivos) {
    Swal.fire({
      icon: 'info',
      title: 'Nenhum arquivo',
      text: 'O cliente não anexou nenhuma arte neste pedido.',
      background: document.body.classList.contains('dark-mode') ? '#1e1e2d' : '#ffffff',
      color: document.body.classList.contains('dark-mode') ? '#f3f4f6' : '#1f2937'
    });
    return;
  }

  Swal.fire({
    title: 'Arquivos do Pedido',
    html: `<div style="max-height: 400px; overflow-y: auto; padding: 10px;">${arquivos}</div>`,
    showCloseButton: true,
    showConfirmButton: false,
    background: document.body.classList.contains('dark-mode') ? '#1e1e2d' : '#ffffff',
    color: document.body.classList.contains('dark-mode') ? '#f3f4f6' : '#1f2937',
    customClass: { popup: 'swal2-modern-popup' }
  });
}

async function alterarStatusPedido(id, statusProd, statusPag) {
  try {
    const res = await fetch(`/api/pedidos/${id}/status`, {
      method: 'PUT',
      headers: { 
        'Content-Type': 'application/json',
        'X-Admin-Token': state.adminToken 
      },
      body: JSON.stringify({ status_producao: statusProd, status_pagamento: statusPag })
    });
    if (res.ok) {
      if (state.adminTab === 'kanban') loadKanbanBoard();
      else loadAdminPedidos();
    }
  } catch (err) {
    console.error('Erro update status:', err);
  }
}

async function imprimirOS(pedidoId) {
  try {
    const res = await fetch(`/api/pedidos/${pedidoId}`);
    const p = await res.json();

    document.getElementById('os-grafica-nome').innerText = state.config.nome_grafica || 'GRÁFICA RÁPIDA EXPRESS';
    document.getElementById('os-codigo').innerText = p.codigo_pedido;
    document.getElementById('os-cliente').innerText = p.cliente_nome;
    document.getElementById('os-telefone').innerText = p.cliente_telefone;
    document.getElementById('os-data').innerText = new Date(p.data_criacao).toLocaleDateString('pt-BR');
    document.getElementById('os-pagamento').innerText = `${p.status_pagamento} (${p.metodo_pagamento})`;
    document.getElementById('os-entrega').innerText = p.tipo_entrega;

    document.getElementById('os-itens-tbody').innerHTML = p.itens.map(i => `
      <tr>
        <td style="border: 1px solid black; padding: 8px; text-align: center;">${i.quantidade}</td>
        <td style="border: 1px solid black; padding: 8px;">${i.produto_nome}</td>
        <td style="border: 1px solid black; padding: 8px;">
          Tamanho: ${i.tamanho} | Papel: ${i.papel} | Acabamento: ${i.acabamento}
          ${i.arte_url ? `<br>Arte: <a href="${i.arte_url}" target="_blank">Abrir Arquivo</a>` : ''}
          ${i.criar_arte ? `<br>Criação: ${i.detalhes_arte}` : ''}
        </td>
        <td style="border: 1px solid black; padding: 8px; text-align: right;">R$ ${i.preco_total.toFixed(2).replace('.', ',')}</td>
      </tr>
    `).join('');

    document.getElementById('os-total').innerText = `R$ ${p.total.toFixed(2).replace('.', ',')}`;

    const el = document.getElementById('printable-os');
    el.style.display = 'block';
    window.print();
    setTimeout(() => { el.style.display = 'none'; }, 1000);
  } catch (err) {
    console.error('Erro OS:', err);
  }
}

// --- ESTOQUE DE INSUMOS ---

async function loadAdminEstoque() {
  try {
    const res = await fetch('/api/estoque', {
      headers: { 'X-Admin-Token': state.adminToken }
    });
    const insumos = await res.json();

    document.getElementById('admin-estoque-tbody').innerHTML = insumos.map(i => `
      <tr>
        <td><strong>${i.nome_insumo}</strong></td>
        <td><span class="badge badge-info">${i.categoria}</span></td>
        <td style="font-weight: 800;">${i.quantidade_atual} ${i.unidade_medida}</td>
        <td>${i.quantidade_minima} ${i.unidade_medida}</td>
        <td>
          <span class="badge ${i.quantidade_atual <= i.quantidade_minima ? 'badge-danger' : 'badge-success'}">
            ${i.quantidade_atual <= i.quantidade_minima ? '⚠️ Baixo Estoque' : 'OK'}
          </span>
        </td>
        <td>
          <button class="btn btn-secondary btn-sm" onclick="ajustarEstoqueInsumo(${i.id}, ${i.quantidade_atual})" title="Ajustar Quantidade"><i class="fa-solid fa-boxes-stacked"></i></button>
          <button class="btn btn-primary btn-sm" onclick="editarInsumoAdmin(${i.id})" title="Editar Insumo"><i class="fa-solid fa-pen"></i></button>
          <button class="btn btn-danger btn-sm" onclick="excluirInsumoAdmin(${i.id})" title="Excluir Insumo"><i class="fa-solid fa-trash"></i></button>
        </td>
      </tr>
    `).join('');
  } catch (err) {
    console.error('Erro estoque:', err);
  }
}

function openInsumoModal() {
  openModal('modal-admin-insumo');
}

async function salvarInsumoAdmin(e) {
  e.preventDefault();
  const form = document.getElementById('form-admin-insumo');
  const id = form.dataset.id;
  const payload = {
    nome_insumo: document.getElementById('insumo-nome').value,
    categoria: document.getElementById('insumo-categoria').value,
    quantidade_atual: parseFloat(document.getElementById('insumo-qtd').value),
    quantidade_minima: parseFloat(document.getElementById('insumo-qtd-min').value),
    unidade_medida: document.getElementById('insumo-unidade').value
  };
  if (id) payload.id = id;

  try {
    const res = await fetch('/api/estoque', {
      method: id ? 'PUT' : 'POST',
      headers: { 
        'Content-Type': 'application/json',
        'X-Admin-Token': state.adminToken 
      },
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      closeModal('modal-admin-insumo');
      loadAdminEstoque();
    }
  } catch (err) {
    console.error('Erro insumo:', err);
  }
}

async function ajustarEstoqueInsumo(id, qtdAtual) {
  const novaQtd = await window.promptAsync('Digite a nova quantidade em estoque:', qtdAtual);
  if (novaQtd === null) return;

  try {
    await fetch('/api/estoque', {
      method: 'PUT',
      headers: { 
        'Content-Type': 'application/json',
        'X-Admin-Token': state.adminToken 
      },
      body: JSON.stringify({ id, quantidade_atual: parseFloat(novaQtd), quantidade_minima: 10 })
    });
    loadAdminEstoque();
  } catch (err) {
    console.error('Erro ajustar estoque:', err);
  }
}

// --- ORÇAMENTISTA ---

window.allOrcamentos = [];

async function loadAdminOrcamentos() {
  try {
    const res = await fetch('/api/orcamentos', {
      headers: { 'X-Admin-Token': state.adminToken }
    });
    window.allOrcamentos = await res.json();

    document.getElementById('admin-orcamentos-tbody').innerHTML = window.allOrcamentos.map(o => `
      <tr>
        <td><strong>${o.codigo_orcamento}</strong></td>
        <td>${o.cliente_nome}<br><small style="color: var(--text-muted);">${o.cliente_telefone}</small></td>
        <td>${o.descricao}</td>
        <td style="font-weight: 800; color: var(--primary);">R$ ${o.valor_estimado.toFixed(2).replace('.', ',')}</td>
        <td><span class="badge ${o.status === 'Aprovado' ? 'badge-success' : o.status === 'Rejeitado' ? 'badge-danger' : o.status === 'Concluído' ? 'badge-info' : 'badge-warning'}">${o.status}</span></td>
        <td style="display: flex; gap: 5px; flex-wrap: wrap;">
          <button onclick="abrirChatWidget('${o.codigo_orcamento}', '${o.cliente_telefone}', '${o.cliente_nome}')" class="btn btn-secondary btn-sm" style="color: #25d366;" title="Chat Interno">
            <i class="fa-solid fa-comments"></i>
          </button>
          <button onclick="abrirConversaInterna('${o.cliente_telefone}', '${o.cliente_nome}')" class="btn btn-secondary btn-sm" style="color: #25d366;" title="WhatsApp Interno">
            <i class="fa-brands fa-whatsapp"></i>
          </button>
          <button class="btn btn-primary btn-sm" onclick="abrirModalEditarOrcamento(${o.id})" title="Editar">
            <i class="fa-solid fa-pen"></i>
          </button>
          <button class="btn btn-danger btn-sm" onclick="excluirOrcamentoAdmin(${o.id})" title="Excluir">
            <i class="fa-solid fa-trash"></i>
          </button>
        </td>
      </tr>
    `).join('');
  } catch (err) {
    console.error('Erro orcamentos admin:', err);
  }
}

function openOrcamentoModal() {
  document.getElementById('form-admin-orcamento').reset();
  document.getElementById('orc-id').value = '';
  document.getElementById('orc-status').value = 'Pendente';
  openModal('modal-admin-orcamento');
}

function abrirModalEditarOrcamento(id) {
  const o = window.allOrcamentos.find(x => x.id === id);
  if (!o) return;
  document.getElementById('orc-id').value = o.id;
  document.getElementById('orc-nome').value = o.cliente_nome;
  document.getElementById('orc-telefone').value = o.cliente_telefone;
  document.getElementById('orc-desc').value = o.descricao;
  document.getElementById('orc-valor').value = o.valor_estimado;
  document.getElementById('orc-status').value = o.status;
  openModal('modal-admin-orcamento');
}

async function excluirOrcamentoAdmin(id) {
  if (!(await window.confirmAsync("Tem certeza que deseja excluir este orçamento?"))) return;
  try {
    const res = await fetch('/api/orcamentos/' + id, {
      method: 'DELETE',
      headers: { 'X-Admin-Token': state.adminToken }
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.error || 'Erro ao excluir');
    alert(json.message);
    loadAdminOrcamentos();
  } catch (err) {
    alert(err.message);
  }
}

async function salvarOrcamentoAdmin(e) {
  e.preventDefault();
  const id = document.getElementById('orc-id').value;
  const payload = {
    cliente_nome: document.getElementById('orc-nome').value,
    cliente_telefone: document.getElementById('orc-telefone').value,
    descricao: document.getElementById('orc-desc').value,
    valor_estimado: parseFloat(document.getElementById('orc-valor').value),
    status: document.getElementById('orc-status').value
  };

  try {
    const url = id ? '/api/orcamentos/' + id : '/api/orcamentos';
    const method = id ? 'PUT' : 'POST';
    const res = await fetch(url, {
      method: method,
      headers: { 
        'Content-Type': 'application/json',
        'X-Admin-Token': state.adminToken
      },
      body: JSON.stringify(payload)
    });
    const json = await res.json();
    if (res.ok) {
      alert(json.message);
      closeModal('modal-admin-orcamento');
      loadAdminOrcamentos();
    } else {
      alert(json.error || 'Erro ao salvar orçamento');
    }
  } catch (err) {
    alert(err.message);
  }
}

// --- CUPONS ---

async function loadAdminCupons() {
  try {
    const res = await fetch('/api/cupons');
    const cupons = await res.json();

    document.getElementById('admin-cupons-tbody').innerHTML = cupons.map(c => `
      <tr>
        <td><strong>${c.codigo}</strong></td>
        <td><span class="badge badge-success">${c.porcentagem_desconto}% OFF</span></td>
        <td>R$ ${c.valor_minimo.toFixed(2).replace('.', ',')}</td>
        <td>${c.usos_atuais} / ${c.limite_usos}</td>
        <td><span class="badge ${c.ativo ? 'badge-success' : 'badge-danger'}">${c.ativo ? 'Ativo' : 'Inativo'}</span></td>
        <td style="white-space: nowrap;">
          <button class="btn btn-secondary btn-sm" onclick='editarCupomAdmin(${JSON.stringify(c)})'><i class="fa-solid fa-pen"></i></button>
          <button class="btn btn-secondary btn-sm" style="color: var(--danger);" onclick="deletarCupomAdmin(${c.id})"><i class="fa-solid fa-trash"></i></button>
        </td>
      </tr>
    `).join('');
  } catch (err) {
    console.error('Erro cupons:', err);
  }
}

function openCupomModal() {
  document.getElementById('cupom-id').value = '';
  document.getElementById('cupom-codigo').value = '';
  document.getElementById('cupom-pct').value = '';
  document.getElementById('cupom-min').value = '';
  document.getElementById('cupom-limite').value = '';
  document.getElementById('cupom-ativo').checked = true;
  openModal('modal-admin-cupom');
}

function editarCupomAdmin(cupom) {
  document.getElementById('cupom-id').value = cupom.id;
  document.getElementById('cupom-codigo').value = cupom.codigo;
  document.getElementById('cupom-pct').value = cupom.porcentagem_desconto;
  document.getElementById('cupom-min').value = cupom.valor_minimo;
  document.getElementById('cupom-limite').value = cupom.limite_usos;
  document.getElementById('cupom-ativo').checked = cupom.ativo === 1;
  openModal('modal-admin-cupom');
}

async function salvarCupomAdmin(e) {
  e.preventDefault();
  const payload = {
    id: document.getElementById('cupom-id').value || null,
    codigo: document.getElementById('cupom-codigo').value,
    porcentagem_desconto: parseFloat(document.getElementById('cupom-pct').value),
    valor_minimo: parseFloat(document.getElementById('cupom-min').value),
    limite_usos: parseInt(document.getElementById('cupom-limite').value),
    ativo: document.getElementById('cupom-ativo').checked
  };

  try {
    const res = await fetch('/api/cupons', {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json',
        'X-Admin-Token': state.adminToken 
      },
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      closeModal('modal-admin-cupom');
      loadAdminCupons();
    }
  } catch (err) {
    console.error('Erro criar cupom:', err);
  }
}

async function deletarCupomAdmin(id) {
  if (!(await window.confirmAsync('Deseja deletar este cupom?'))) return;
  try {
    await fetch(`/api/cupons?id=${id}`, { 
      method: 'DELETE',
      headers: { 'X-Admin-Token': state.adminToken }
    });
    loadAdminCupons();
  } catch (err) {
    console.error('Erro deletar cupom:', err);
  }
}

// --- PRODUTOS CRUD (ADMIN) ---

async function loadAdminProdutos() {
  try {
    const res = await fetch('/api/produtos?admin=true');
    const prods = await res.json();

    document.getElementById('admin-produtos-tbody').innerHTML = prods.map(p => `
      <tr>
        <td><img src="${p.imagem_url}" width="40" height="40" style="border-radius: 6px; object-fit: cover;"></td>
        <td><strong>${p.nome}</strong></td>
        <td><span class="badge badge-info">${p.categoria}</span></td>
        <td>R$ ${p.preco_base.toFixed(2).replace('.', ',')}</td>
        <td><span class="badge ${p.ativo ? 'badge-success' : 'badge-danger'}">${p.ativo ? 'Ativo' : 'Inativo'}</span></td>
        <td>
          <button class="btn btn-secondary btn-sm" onclick="editProdutoAdmin(${p.id})"><i class="fa-solid fa-pen"></i></button>
          <button class="btn btn-secondary btn-sm" onclick="deleteProdutoAdmin(${p.id})" style="color: var(--danger);"><i class="fa-solid fa-trash"></i></button>
        </td>
      </tr>
    `).join('');
  } catch (err) {
    console.error('Erro produtos admin:', err);
  }
}

function openAdminProdutoModal() {
  document.getElementById('admin-prod-id').value = '';
  document.getElementById('form-admin-produto').reset();
  document.getElementById('modal-admin-prod-title').innerText = 'Novo Produto';
  openModal('modal-admin-produto');
}

function editProdutoAdmin(id) {
  const p = state.produtos.find(prod => prod.id === id);
  if (!p) return;

  document.getElementById('admin-prod-id').value = p.id;
  document.getElementById('admin-prod-nome').value = p.nome;
  document.getElementById('admin-prod-categoria').value = p.categoria;
  document.getElementById('admin-prod-preco').value = p.preco_base;
  document.getElementById('admin-prod-imagem').value = p.imagem_url;
  document.getElementById('admin-prod-descricao').value = p.descricao || '';
  document.getElementById('admin-prod-tamanhos').value = (p.tamanhos || []).join(', ');
  document.getElementById('admin-prod-papeis').value = (p.papeis || []).join(', ');
  document.getElementById('admin-prod-acabamentos').value = (p.acabamentos || []).join(', ');
  document.getElementById('admin-prod-ativo').checked = p.ativo === 1;
  document.getElementById('admin-prod-destaque').checked = p.destaque === 1;

  document.getElementById('modal-admin-prod-title').innerText = 'Editar Produto';
  openModal('modal-admin-produto');
}

async function salvarProdutoAdmin(e) {
  e.preventDefault();
  const id = document.getElementById('admin-prod-id').value;

  const tamanhosStr = document.getElementById('admin-prod-tamanhos').value;
  const papeisStr = document.getElementById('admin-prod-papeis').value;
  const acabamentosStr = document.getElementById('admin-prod-acabamentos').value;
  const precoBase = parseFloat(document.getElementById('admin-prod-preco').value);

  const payload = {
    nome: document.getElementById('admin-prod-nome').value,
    categoria: document.getElementById('admin-prod-categoria').value,
    preco_base: precoBase,
    imagem_url: document.getElementById('admin-prod-imagem').value,
    descricao: document.getElementById('admin-prod-descricao').value,
    tamanhos: tamanhosStr ? tamanhosStr.split(',').map(s => s.trim()) : [],
    papeis: papeisStr ? papeisStr.split(',').map(s => s.trim()) : [],
    acabamentos: acabamentosStr ? acabamentosStr.split(',').map(s => s.trim()) : [],
    tiragens: [
      { qtd: 100, preco: precoBase },
      { qtd: 500, preco: precoBase * 2.2 },
      { qtd: 1000, preco: precoBase * 3.5 }
    ],
    ativo: document.getElementById('admin-prod-ativo').checked,
    destaque: document.getElementById('admin-prod-destaque').checked
  };

  const method = id ? 'PUT' : 'POST';
  const url = id ? `/api/produtos/${id}` : '/api/produtos';

  try {
    const res = await fetch(url, {
      method: method,
      headers: { 
        'Content-Type': 'application/json',
        'X-Admin-Token': state.adminToken 
      },
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      closeModal('modal-admin-produto');
      loadProdutos();
      loadAdminProdutos();
    }
  } catch (err) {
    console.error('Erro salvando produto:', err);
  }
}

async function deleteProdutoAdmin(id) {
  if (!(await window.confirmAsync('Deseja realmente excluir este produto?'))) return;
  try {
    const res = await fetch(`/api/produtos/${id}`, { 
      method: 'DELETE',
      headers: { 'X-Admin-Token': state.adminToken }
    });
    if (res.ok) {
      loadProdutos();
      loadAdminProdutos();
    }
  } catch (err) {
    console.error('Erro deletando produto:', err);
  }
}

// --- CONTROLE DE CAIXA (ADMIN) ---

async function loadAdminCaixa() {
  try {
    const res = await fetch('/api/caixa/resumo', {
      headers: { 'X-Admin-Token': state.adminToken }
    });
    const data = await res.json();

    document.getElementById('caixa-entradas').innerText = `R$ ${data.total_entradas.toFixed(2).replace('.', ',')}`;
    document.getElementById('caixa-saidas').innerText = `R$ ${data.total_saidas.toFixed(2).replace('.', ',')}`;
    document.getElementById('caixa-saldo').innerText = `R$ ${data.saldo_atual.toFixed(2).replace('.', ',')}`;

    document.getElementById('caixa-movimentacoes-tbody').innerHTML = data.movimentacoes.map(m => `
      <tr>
        <td>${new Date(m.data_movimento).toLocaleDateString('pt-BR')} ${new Date(m.data_movimento).toLocaleTimeString('pt-BR', {hour: '2-digit', minute:'2-digit'})}</td>
        <td><span class="badge ${m.tipo === 'ENTRADA' ? 'badge-success' : 'badge-danger'}">${m.tipo}</span></td>
        <td>${m.categoria}</td>
        <td>${m.descricao}</td>
        <td>${m.forma_pagamento}</td>
        <td style="font-weight: 800; color: ${m.tipo === 'ENTRADA' ? 'var(--success)' : 'var(--danger)'};">
          ${m.tipo === 'ENTRADA' ? '+' : '-'} R$ ${m.valor.toFixed(2).replace('.', ',')}
        </td>
        <td>
          <button class="btn btn-danger btn-sm" onclick="excluirMovimentoCaixa(${m.id})" title="Excluir"><i class="fa-solid fa-trash"></i></button>
        </td>
      </tr>
    `).join('');
  } catch (err) {
    console.error('Erro caixa:', err);
  }
}

function openCaixaMovimentoModal() {
  document.getElementById('form-caixa-movimento').reset();
  openModal('modal-caixa-movimento');
}

async function salvarCaixaMovimento(e) {
  e.preventDefault();
  const payload = {
    tipo: document.getElementById('caixa-mov-tipo').value,
    categoria: document.getElementById('caixa-mov-categoria').value,
    descricao: document.getElementById('caixa-mov-descricao').value,
    valor: parseFloat(document.getElementById('caixa-mov-valor').value),
    forma_pagamento: document.getElementById('caixa-mov-forma').value
  };

  try {
    const res = await fetch('/api/caixa/movimento', {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json',
        'X-Admin-Token': state.adminToken 
      },
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      closeModal('modal-caixa-movimento');
      loadAdminCaixa();
    }
  } catch (err) {
    console.error('Erro salvando caixa:', err);
  }
}

// --- CLIENTES (ADMIN) ---

window.allClientes = [];

async function loadAdminClientes() {
  try {
    const res = await fetch('/api/clientes', {
      headers: { 'X-Admin-Token': state.adminToken }
    });
    window.allClientes = await res.json();

    document.getElementById('admin-clientes-tbody').innerHTML = window.allClientes.map(c => `
      <tr>
        <td><strong>${c.nome}</strong></td>
        <td>${c.telefone}</td>
        <td>${c.email || '-'}</td>
        <td><span class="badge badge-info">${c.total_pedidos} pedidos</span></td>
        <td style="font-weight: 800; color: var(--primary);">R$ ${(c.total_gasto || 0).toFixed(2).replace('.', ',')}</td>
        <td style="display: flex; gap: 5px; flex-wrap: wrap;">
          <button onclick="abrirConversaInterna('GERAL', '${(c.telefone||'').replace(/\D/g, '')}')" class="btn btn-secondary btn-sm" style="color: #25d366;" title="Conversar">
            <i class="fa-brands fa-whatsapp"></i>
          </button>
          <button class="btn btn-primary btn-sm" onclick="abrirModalEditarCliente(${c.id})" title="Editar">
            <i class="fa-solid fa-pen"></i>
          </button>
          <button class="btn btn-danger btn-sm" onclick="excluirClienteAdmin(${c.id})" title="Excluir">
            <i class="fa-solid fa-trash"></i>
          </button>
        </td>
      </tr>
    `).join('');
  } catch (err) {
    console.error('Erro clientes:', err);
  }
}

function abrirModalEditarCliente(id) {
  const cliente = window.allClientes.find(c => c.id === id);
  if (!cliente) return;
  document.getElementById('admin-cli-id').value = cliente.id;
  document.getElementById('admin-cli-nome').value = cliente.nome;
  document.getElementById('admin-cli-email').value = cliente.email;
  document.getElementById('admin-cli-telefone').value = cliente.telefone;
  document.getElementById('admin-cli-cpf').value = cliente.cpf_cnpj || '';
  document.getElementById('admin-cli-endereco').value = cliente.endereco || '';
  openModal('modal-admin-cliente');
}

async function salvarClienteAdmin(e) {
  e.preventDefault();
  const id = document.getElementById('admin-cli-id').value;
  const data = {
    nome: document.getElementById('admin-cli-nome').value,
    email: document.getElementById('admin-cli-email').value,
    telefone: document.getElementById('admin-cli-telefone').value,
    cpf_cnpj: document.getElementById('admin-cli-cpf').value,
    endereco: document.getElementById('admin-cli-endereco').value,
  };

  try {
    const res = await fetch('/api/clientes/' + id, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'X-Admin-Token': state.adminToken
      },
      body: JSON.stringify(data)
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.error || 'Erro ao atualizar');
    alert(json.message);
    closeModal('modal-admin-cliente');
    loadAdminClientes();
  } catch (err) {
    alert(err.message);
  }
}

async function redefinirSenhaCliente() {
  const id = document.getElementById('admin-cli-id').value;
  if (!id) return;
  if (!(await window.confirmAsync("Tem certeza que deseja redefinir a senha deste cliente? Ele receberá a nova senha no WhatsApp."))) return;
  
  try {
    const res = await fetch('/api/clientes/redefinir-senha', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Admin-Token': state.adminToken
      },
      body: JSON.stringify({ id: id })
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.error || 'Erro ao redefinir senha');
    alert(json.message);
    closeModal('modal-admin-cliente');
  } catch (err) {
    alert(err.message);
  }
}

async function excluirClienteAdmin(id) {
  if (!(await window.confirmAsync("Tem certeza que deseja excluir este cliente? Essa ação não pode ser desfeita!"))) return;
  
  try {
    const res = await fetch('/api/clientes/' + id, {
      method: 'DELETE',
      headers: { 'X-Admin-Token': state.adminToken }
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.error || 'Erro ao excluir');
    alert(json.message);
    loadAdminClientes();
  } catch (err) {
    alert(err.message);
  }
}

// --- CONFIGURAÇÕES CMS (ADMIN) ---

async function salvarConfiguracoes(e) {
  e.preventDefault();
  const payload = {
    nome_grafica: document.getElementById('cfg-nome-grafica').value,
    whatsapp: document.getElementById('cfg-whatsapp').value,
    chave_pix: document.getElementById('cfg-chave-pix').value,
    banner_titulo: document.getElementById('cfg-banner-titulo').value,
    banner_subtitulo: document.getElementById('cfg-banner-subtitulo').value,
    aviso_topo: document.getElementById('cfg-aviso-topo').value,
    desconto_pix: parseFloat(document.getElementById('cfg-desconto-pix').value),
    taxa_entrega: parseFloat(document.getElementById('cfg-taxa-entrega').value),
    evolution_api_url: document.getElementById('cfg-evolution-url') ? document.getElementById('cfg-evolution-url').value.trim() : '',
    evolution_api_key: document.getElementById('cfg-evolution-key') ? document.getElementById('cfg-evolution-key').value.trim() : '',
    evolution_instance: document.getElementById('cfg-evolution-instance') ? document.getElementById('cfg-evolution-instance').value.trim() : '',
    validar_whatsapp_ativo: document.getElementById('cfg-evolution-active') ? (document.getElementById('cfg-evolution-active').value === '1' ? 1 : 0) : 0
  };

  try {
    const res = await fetch('/api/config', {
      method: 'PUT',
      headers: { 
        'Content-Type': 'application/json',
        'X-Admin-Token': state.adminToken 
      },
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      alert('Configurações salvas com sucesso!');
      loadConfig();
    }
  } catch (err) {
    console.error('Erro salvando config:', err);
  }
}

async function testarEvolutionAPI() {
  const url = document.getElementById('cfg-evolution-url').value.trim();
  const key = document.getElementById('cfg-evolution-key').value.trim();
  const instance = document.getElementById('cfg-evolution-instance').value.trim();

  if (!url || !key || !instance) {
    alert('Por favor, preencha a URL da Evolution API, a API Key e o Nome da Instância para testar.');
    return;
  }

  try {
    const res = await fetch('/api/admin/testar-evolution', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Admin-Token': state.adminToken
      },
      body: JSON.stringify({ url, key, instance })
    });
    const data = await res.json();

    if (res.ok && data.success) {
      alert(`✅ Conexão com Evolution API estabelecida com sucesso!\n\n${data.message}`);
    } else {
      alert(`❌ Erro ao conectar com Evolution API:\n${data.error || 'Instância não conectada ou chave inválida.'}`);
    }
  } catch (err) {
    console.error('Erro testar Evolution API:', err);
    alert('Erro ao se comunicar com o servidor. Verifique a URL informada.');
  }
}

// --- UTILS MODAL ---

function openModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.add('active');
}

function closeModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.remove('active');
}

// ==========================================================================
// CHAT FLUTUANTE (SISTEMA INTERNO)
// ==========================================================================

let chatWidgetRef = null;
let chatWidgetTel = null;
let chatWidgetInterval = null;

function abrirChatWidget(codigo, telefone = null, clienteNome = null) {
  chatWidgetRef = codigo;
  chatWidgetTel = telefone;
  
  const isAdminView = document.getElementById('view-admin').style.display !== 'none';
  
  document.getElementById("chat-widget-codigo").innerText = codigo;
  if (isAdminView) {
      document.getElementById("chat-widget-title").innerText = clienteNome || telefone || "Cliente";
  } else {
      document.getElementById("chat-widget-title").innerText = "Atendimento";
  }
  
  document.getElementById("chat-widget").style.display = "flex";
  
  carregarMensagensChat();
  
  // Polling para novas mensagens (a cada 5 segundos)
  if (chatWidgetInterval) clearInterval(chatWidgetInterval);
  chatWidgetInterval = setInterval(carregarMensagensChat, 5000);
}

function fecharChatWidget() {
  document.getElementById("chat-widget").style.display = "none";
  if (chatWidgetInterval) clearInterval(chatWidgetInterval);
}

async function carregarMensagensChat() {
  if (!chatWidgetRef) return;
  
  const headers = {};
  const isAdminView = document.getElementById('view-admin').style.display !== 'none';
  
  if (isAdminView && state.adminToken) {
    headers["X-Admin-Token"] = state.adminToken;
  } else if (!isAdminView && state.clientToken) {
    headers["X-Client-Token"] = state.clientToken;
  }
  
  try {
    const res = await fetch(`/api/chat/${encodeURIComponent(chatWidgetRef)}`, { headers });
    if (!res.ok) return;
    const mensagens = await res.json();
    
    const container = document.getElementById("chat-widget-messages");
    if (mensagens.length === 0) {
      container.innerHTML = `<div style="text-align: center; color: #888; font-size: 0.9rem; margin-top: 20px;">Envie uma mensagem para iniciar o atendimento.</div>`;
      return;
    }
    
    const souAdmin = isAdminView;
    
    container.innerHTML = mensagens.map(m => {
      const isMe = (souAdmin && m.remetente_tipo === "admin") || (!souAdmin && m.remetente_tipo === "cliente");
      const alignClass = isMe ? "cliente" : "admin"; // Using classes from CSS. 'cliente' class floats right (green), 'admin' class floats left (gray).
      const time = new Date(m.data_envio).toLocaleTimeString([], {hour: "2-digit", minute:"2-digit"});
      
      return `
        <div class="chat-msg ${alignClass}">
          <strong>${m.remetente_nome}</strong>
          <div style="margin-top: 4px;">${m.mensagem}</div>
          <span class="chat-msg-time">${time}</span>
        </div>
      `;
    }).join("");
    
    // Auto scroll to bottom
    container.scrollTop = container.scrollHeight;
    
  } catch(e) {
    console.error("Erro chat:", e);
  }
}

async function enviarMensagemChat() {
  const input = document.getElementById("chat-widget-input");
  const msg = input.value.trim();
  if (!msg || !chatWidgetRef) return;
  
  const headers = { "Content-Type": "application/json" };
  const isAdminView = document.getElementById('view-admin').style.display !== 'none';
  
  if (isAdminView && state.adminToken) {
    headers["X-Admin-Token"] = state.adminToken;
  } else if (!isAdminView && state.clientToken) {
    headers["X-Client-Token"] = state.clientToken;
  }
  
  const body = { mensagem: msg };
  if (chatWidgetTel) body.telefone = chatWidgetTel;
  else if (state.clienteLogado) body.telefone = state.clienteLogado.telefone;
  
  try {
    input.value = "";
    const res = await fetch(`/api/chat/${encodeURIComponent(chatWidgetRef)}`, {
      method: "POST",
      headers,
      body: JSON.stringify(body)
    });
    if (res.ok) {
      carregarMensagensChat();
    } else {
      alert("Erro ao enviar mensagem.");
    }
  } catch(e) {
    console.error(e);
  }
}
// ==========================================================================
// WHATSAPP INBOX (ADMIN) & UNREAD POLLING
// ==========================================================================
let inboxInterval = null;
let currentInboxChat = null;
let currentInboxTel = null;

async function checkUnreadBadges() {
  if (state.adminToken) {
    try {
      const res = await fetch("/api/chat/unread/admin", { headers: { "X-Admin-Token": state.adminToken } });
      if (res.ok) {
        const data = await res.json();
        const badge = document.getElementById("badge-whatsapp-unread");
        if (badge) {
          if (data.unread > 0) {
            if (badge.innerText !== data.unread.toString()) {
                const audio = new Audio("https://actions.google.com/sounds/v1/alarms/beep_short.ogg");
                audio.play().catch(e=>console.log(e));
            }
            badge.innerText = data.unread;
            badge.style.display = "inline-block";
          } else {
            badge.style.display = "none";
          }
        }
      }
    } catch(e) {}
  }
  
  if (state.clientToken) {
    try {
      const res = await fetch("/api/chat/unread/cliente", { headers: { "X-Client-Token": state.clientToken } });
      if (res.ok) {
        const data = await res.json();
        const badge = document.getElementById("badge-cli-whatsapp-unread");
        if (badge) {
          if (data.unread > 0) {
            if (badge.innerText !== data.unread.toString()) {
                const audio = new Audio("https://actions.google.com/sounds/v1/alarms/beep_short.ogg");
                audio.play().catch(e=>console.log(e));
            }
            badge.innerText = data.unread;
            badge.style.display = "inline-block";
          } else {
            badge.style.display = "none";
          }
        }
      }
    } catch(e) {}
  }
}

// Global poller
setInterval(checkUnreadBadges, 15000);

async function loadWhatsAppInbox() {
  if (!state.adminToken) return;
  try {
    const res = await fetch("/api/chat/inbox", { headers: { "X-Admin-Token": state.adminToken } });
    if (!res.ok) return;
    const conversas = await res.json();
    
    const list = document.getElementById("inbox-list");
    if (!list) return;
    
    if (conversas.length === 0) {
      list.innerHTML = `<div style="padding: 20px; text-align: center; color: #888;">Nenhuma conversa ativa</div>`;
      return;
    }
    
    list.innerHTML = conversas.map(c => {
      const time = new Date(c.data_envio).toLocaleTimeString([], {hour: "2-digit", minute:"2-digit"});
      const bg = (currentInboxTel === c.telefone_cliente) ? "rgba(255,255,255,0.1)" : "transparent";
      const unreadBadge = c.nao_lidas > 0 ? `<span class="badge badge-danger" style="border-radius: 50%; padding: 2px 6px; font-size: 0.7rem;">${c.nao_lidas}</span>` : "";
      
      const displayName = c.remetente_nome || c.telefone_cliente;
      const nome = c.referencia_codigo === "GERAL" ? displayName : `${c.referencia_codigo} (${displayName})`;
      const iniciais = displayName.substring(0, 2).toUpperCase();
      
      return `
        <div style="padding: 15px; border-bottom: 1px solid var(--border); cursor: pointer; background: ${bg}; display: flex; gap: 12px; align-items: center;" onclick="abrirInboxChat('${c.telefone_cliente}', '${c.remetente_nome}')">
          <div style="width: 42px; height: 42px; border-radius: 50%; background: var(--primary); display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 1.1rem; color: #fff; flex-shrink: 0;">
            ${iniciais}
          </div>
          <div style="overflow: hidden; flex: 1;">
            <div style="font-weight: bold; margin-bottom: 5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: flex; justify-content: space-between; align-items: center;">
                <span style="color: #fff;">${nome}</span>
                <small style="color: #888; font-size: 0.75rem;">${time}</small>
            </div>
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-size: 0.85rem; color: #aaa; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                    ${c.remetente_tipo === "admin" ? "Você: " : ""}${c.mensagem}
                </span>
                ${unreadBadge}
            </div>
          </div>
        </div>
      `;
    }).join("");
    
  } catch(e) {}
}

function abrirConversaInterna(telefone, nome) {
  const btn = document.getElementById("nav-btn-whatsapp");
  if (btn) switchAdminTab('whatsapp', btn);
  else switchAdminTab('whatsapp');
  abrirInboxChat(telefone, nome);
}

async function abrirInboxChat(telefone, nome) {
  currentInboxTel = telefone;
  
  document.getElementById("inbox-title").innerText = nome || "Cliente";
  document.getElementById("inbox-subtitle").innerText = "WhatsApp: " + telefone;
  document.getElementById("inbox-input-area").style.display = "flex";
  document.getElementById("inbox-actions").style.display = "flex";
  
  // Mark as read
  await fetch(`/api/chat/telefone/${encodeURIComponent(currentInboxTel)}/read`, {
    method: "POST",
    headers: { "X-Admin-Token": state.adminToken, "Content-Type": "application/json" },
    body: JSON.stringify({ telefone: currentInboxTel })
  });
  
  loadWhatsAppInbox();
  carregarMensagensInbox();
  checkUnreadBadges();
  
  if (inboxInterval) clearInterval(inboxInterval);
  inboxInterval = setInterval(carregarMensagensInbox, 5000);
}

function salvarContatoInbox() {
  if (!currentInboxTel || !state.adminToken) return;
  document.getElementById("save-contact-name").value = "";
  document.getElementById("modal-save-contact").style.display = "flex";
  setTimeout(() => document.getElementById("save-contact-name").focus(), 100);
}

async function confirmSaveContact() {
  if (!currentInboxTel || !state.adminToken) return;
  const nome = document.getElementById("save-contact-name").value.trim();
  if (!nome) return;
  
  try {
    const res = await fetch("/api/chat/save_contact", {
      method: "POST",
      headers: { "X-Admin-Token": state.adminToken, "Content-Type": "application/json" },
      body: JSON.stringify({ telefone: currentInboxTel, nome: nome })
    });
    const data = await res.json();
    if (data.status === "sucesso") {
      alert(`Cliente salvo com sucesso! A senha gerada é: ${data.senha}`);
      closeModal('modal-save-contact');
    } else {
      alert(data.message || "Erro ao salvar contato.");
    }
  } catch(e) {
    alert("Erro de conexão.");
  }
}

async function apagarConversaInbox() {
  if (!currentInboxChat || !currentInboxTel || !state.adminToken) return;
  if (!(await window.confirmAsync("Tem certeza que deseja apagar essa conversa inteira?"))) return;
  
  try {
    const res = await fetch(`/api/chat/${encodeURIComponent(currentInboxChat)}?telefone=${encodeURIComponent(currentInboxTel)}`, {
      method: "DELETE",
      headers: { "X-Admin-Token": state.adminToken }
    });
    if (res.ok) {
      currentInboxChat = null;
      currentInboxTel = null;
      document.getElementById("inbox-title").innerText = "Selecione uma conversa";
      document.getElementById("inbox-subtitle").innerText = "";
      document.getElementById("inbox-input-area").style.display = "none";
      document.getElementById("inbox-actions").style.display = "none";
      document.getElementById("inbox-messages").innerHTML = "";
      loadWhatsAppInbox();
    }
  } catch(e) {}
}

async function carregarMensagensInbox() {
  if (!currentInboxTel || !state.adminToken) return;
  try {
    const res = await fetch(`/api/chat/telefone/${encodeURIComponent(currentInboxTel)}`, { headers: { "X-Admin-Token": state.adminToken } });
    if (!res.ok) return;
    const mensagens = await res.json();
    
    const filtered = mensagens;
    
    const container = document.getElementById("inbox-messages");
    if (!container) return;
    
    container.innerHTML = filtered.map(m => {
      const isMe = m.remetente_tipo === "admin";
      const alignClass = isMe ? "cliente" : "admin"; // Reusing chat widget classes (green for me)
      const time = new Date(m.data_envio).toLocaleTimeString([], {hour: "2-digit", minute:"2-digit"});
      
      return `
        <div class="chat-msg ${alignClass}" style="max-width: 70%; align-self: ${isMe ? "flex-end" : "flex-start"};">
          <div style="margin-top: 4px;">${m.mensagem}</div>
          <span class="chat-msg-time">${time}</span>
        </div>
      `;
    }).join("");
    
    container.scrollTop = container.scrollHeight;
  } catch(e) {}
}

async function enviarMensagemInbox() {
  const input = document.getElementById("inbox-input");
  const msg = input.value.trim();
  
  const fileInput = document.getElementById('inbox-file-input');
  const hasFile = fileInput && fileInput.files.length > 0;
  
  if ((!msg && !hasFile) || !currentInboxTel || !state.adminToken) return;
  
  const payload = { mensagem: msg };
  if (hasFile) {
      const file = fileInput.files[0];
      const reader = new FileReader();
      const base64Promise = new Promise(resolve => { reader.onload = e => resolve(e.target.result); });
      reader.readAsDataURL(file);
      const b64 = await base64Promise;
      payload.file_base64 = b64;
      payload.file_name = file.name;
      payload.file_mime = file.type;
      if (file.type.startsWith('image/')) payload.file_type = 'image';
      else if (file.type.startsWith('audio/')) payload.file_type = 'audio';
      else if (file.type.startsWith('video/')) payload.file_type = 'video';
      else payload.file_type = 'document';
      fileInput.value = '';
  }
  
  try {
    input.value = "";
    const res = await fetch(`/api/chat/telefone/${encodeURIComponent(currentInboxTel)}`, {
      method: "POST",
      headers: { "X-Admin-Token": state.adminToken, "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      carregarMensagensInbox();
      loadWhatsAppInbox();
    }
  } catch(e) {}
}

function copiarWebhook() {
  const input = document.getElementById("cfg-webhook-url");
  if (input) {
    navigator.clipboard.writeText(input.value).then(() => {
      alert("URL copiada com sucesso!");
    });
  }
}

function handleChatEnter(e) {
  if (e.key === "Enter") enviarMensagemChat();
}


async function excluirMovimentoCaixa(id) {
  if (!(await window.confirmAsync('Deseja realmente excluir esta movimentao?'))) return;
  try {
    const res = await fetch(/api/caixa/movimento/${id}, {
      method: 'DELETE',
      headers: { 'X-Admin-Token': state.adminToken }
    });
    if (res.ok) {
      loadAdminCaixa();
    }
  } catch (err) {
    console.error('Erro ao excluir caixa:', err);
  }
}

async function editarInsumoAdmin(id) {
  try {
    const res = await fetch('/api/estoque', { headers: { 'X-Admin-Token': state.adminToken } });
    const insumos = await res.json();
    const ins = insumos.find(i => i.id === id);
    if (!ins) return;
    const form = document.getElementById('form-admin-insumo');
    form.dataset.id = ins.id;
    document.getElementById('insumo-nome').value = ins.nome_insumo;
    document.getElementById('insumo-categoria').value = ins.categoria;
    document.getElementById('insumo-qtd').value = ins.quantidade_atual;
    document.getElementById('insumo-qtd-min').value = ins.quantidade_minima;
    document.getElementById('insumo-unidade').value = ins.unidade_medida;
    openModal('modal-admin-insumo');
  } catch (err) {
    console.error('Erro ao editar insumo:', err);
  }
}

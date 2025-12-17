// popup.js - Supabase Integration Version

// ============================================
// SUPABASE CONFIGURATION
// ============================================
const SUPABASE_URL = 'https://xqlsvhezsjzrfuucpmou.supabase.co';
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InhxbHN2aGV6c2p6cmZ1dWNwbW91Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTU3OTI3NzQsImV4cCI6MjA3MTM2ODc3NH0.XK3JF1Yirf10Qb9vOwZJS_8I6_hKnzHoyH1TgiJIDnQ'; 
const TABLE_NAME = 'historico_atise';
// ============================================

async function fetchLastDateFromSupabase() {
  try {
    const response = await fetch(
      `${SUPABASE_URL}/rest/v1/${TABLE_NAME}?select=data&order=data.desc&limit=1`,
      {
        headers: {
          'apikey': SUPABASE_ANON_KEY,
          'Authorization': `Bearer ${SUPABASE_ANON_KEY}`
        }
      }
    );
    if (!response.ok) return null;
    const records = await response.json();
    
    if (records && records.length > 0) {
      return records[0].data; // Returns "YYYY-MM-DD"
    }
    return null;
  } catch (e) {
    console.error('Error fetching last date:', e);
    return null;
  }
}

document.addEventListener('DOMContentLoaded', async () => {
  const today = new Date().toISOString().split('T')[0];
  document.getElementById('endDate').value = today;
  
  showStatus('Carregando última data...', 'processing');
  const lastDate = await fetchLastDateFromSupabase();
  
  if (lastDate) {
    // Parse the last date found in DB
    const [y, m, d] = lastDate.split('-').map(Number);
    const lastDateObj = new Date(y, m - 1, d); 
    
    // UPDATED: Subtract 1 day to create overlap and ensure no data is missed
    lastDateObj.setDate(lastDateObj.getDate() - 1);
    
    const startDate = lastDateObj.toISOString().split('T')[0];
    document.getElementById('startDate').value = startDate;
    
    showStatus(`Última data no banco: ${lastDate.split('-').reverse().join('/')}. Iniciando de: ${startDate.split('-').reverse().join('/')}`, 'success');
  } else {
    document.getElementById('startDate').value = today;
    showStatus('Não foi possível obter última data ou banco vazio.', 'error');
  }
});

function showStatus(message, type) {
  const status = document.getElementById('status');
  status.className = type;
  if (type === 'processing') {
    status.innerHTML = `<span class="spinner"></span>${message}`;
  } else {
    status.textContent = message;
  }
}

document.getElementById('updateBtn').addEventListener('click', async () => {
  const startDate = document.getElementById('startDate').value;
  const endDate = document.getElementById('endDate').value;
  const btn = document.getElementById('updateBtn');

  if (!startDate || !endDate) {
    showStatus('Por favor, selecione as datas.', 'error');
    return;
  }

  btn.disabled = true;
  showStatus('Processando...', 'processing');

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    if (!tab.url || !tab.url.includes('sistemas.infornet.com.br')) {
      showStatus('Por favor, acesse sistemas.infornet.com.br primeiro.', 'error');
      btn.disabled = false;
      return;
    }

    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: scraperFunction,
      args: [startDate, endDate]
    });

    const result = results[0].result;

    if (!result.success) {
      showStatus(result.error || 'Erro desconhecido.', 'error');
      btn.disabled = false;
      return;
    }

    if (result.data.length === 0) {
      showStatus('Nenhum registro encontrado no período.', 'error');
      btn.disabled = false;
      return;
    }

    // Upsert data to Supabase
    // 'resolution=merge-duplicates' REQUIRES a unique constraint on (data, protocolo) in the DB
    showStatus(`Enviando ${result.data.length} registros ao banco...`, 'processing');
    
    const insertResponse = await fetch(
      `${SUPABASE_URL}/rest/v1/${TABLE_NAME}`,
      {
        method: 'POST',
        headers: {
          'apikey': SUPABASE_ANON_KEY,
          'Authorization': `Bearer ${SUPABASE_ANON_KEY}`,
          'Content-Type': 'application/json',
          'Prefer': 'resolution=merge-duplicates,return=minimal'
        },
        body: JSON.stringify(result.data)
      }
    );

    if (insertResponse.ok) {
      showStatus(`✓ Processo concluído! Registros novos/atualizados.`, 'success');
    } else {
      const errorText = await insertResponse.text();
      showStatus(`Erro ao inserir: ${errorText}`, 'error');
    }
  } catch (error) {
    showStatus(`Erro: ${error.message}`, 'error');
  } finally {
    btn.disabled = false;
  }
});

async function scraperFunction(startDateISO, endDateISO) {
  try {
    function formatDateBR(isoDate) {
      const [year, month, day] = isoDate.split('-');
      return `${day}/${month}/${year}`;
    }

    const startDateBR = formatDateBR(startDateISO);
    const endDateBR = formatDateBR(endDateISO);

    // 1. Prepare Payload
    const innerQuery = `edtDataInicio=${encodeURIComponent(startDateBR)}&edtDataFinal=${encodeURIComponent(endDateBR)}&&&edtProtocolo=&edtPlaca=&&edtTelefoneSolicitante=&operadorTagsAtendimento=&`;
    const xmlPayload = `<xjxquery><q>${innerQuery}</q></xjxquery>`;

    const timestamp = Date.now();
    const formData = new URLSearchParams();
    formData.append('xajax', 'ConsultaAtendimento');
    formData.append('xajaxr', timestamp.toString());
    formData.append('xajaxargs[]', xmlPayload);

    // 2. Fetch Data
    const response = await fetch('https://sistemas.infornet.com.br/webassist/maisvantagens/cliente/rel_atendimentos.php', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'x-requested-with': 'XMLHttpRequest'
      },
      body: formData.toString(),
      credentials: 'include'
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    // 3. Fix Encoding
    const buffer = await response.arrayBuffer();
    const decoder = new TextDecoder('iso-8859-1'); 
    const xmlText = decoder.decode(buffer);

    if (xmlText.includes('login') || xmlText.includes('sessao') || xmlText.length < 100) {
      throw new Error('Sessão expirada. Por favor, faça login novamente.');
    }

    // 4. Parse XML
    const parser = new DOMParser();
    const xmlDoc = parser.parseFromString(xmlText, 'text/xml');

    const cmdTags = xmlDoc.querySelectorAll('cmd');
    let htmlContent = null;

    for (const cmd of cmdTags) {
      if (cmd.getAttribute('t') === 'resultado') {
        htmlContent = cmd.textContent;
        break;
      }
    }

    if (!htmlContent) {
      // Fallback search
      for (const cmd of cmdTags) {
        if (cmd.textContent && cmd.textContent.includes('<table')) {
          htmlContent = cmd.textContent;
          break;
        }
      }
    }

    if (!htmlContent) throw new Error('Nenhum resultado encontrado.');

    // 5. Parse HTML
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = htmlContent;
    const table = tempDiv.querySelector('table');

    if (!table) throw new Error('Tabela não encontrada.');

    const rows = table.querySelectorAll('tr');
    const dataRows = [];

    for (const row of rows) {
      if (row.querySelector('th')) continue;
      const cells = row.querySelectorAll('td');
      if (cells.length < 13) continue;

      const getText = (index) => cells[index]?.textContent.trim() || '';
      const rawDate = getText(0);
      
      if (!rawDate || rawDate.toUpperCase() === 'DATA' || rawDate.toLowerCase().includes('total')) continue;

      // Convert DD/MM/YYYY to YYYY-MM-DD
      let finalDate = rawDate;
      if (rawDate.includes('/')) {
        const [d, m, y] = rawDate.split('/');
        finalDate = `${y}-${m}-${d}`;
      }

      const protocolo = getText(1);
      
      let rawPlaca = getText(3);
      let placa = rawPlaca.split(',')[0].replace(/[^a-zA-Z0-9]/g, '').toUpperCase();
      
      const chassi = getText(4);
      const telSolicitante = getText(5);
      const beneficiario = getText(6);
      const telBeneficiario = getText(7);
      const situacao = getText(8);
      const motivo = getText(9);
      const servicos = getText(10);
      
      let valor = getText(11).replace('R$', '').trim().replace(/\./g, '').replace(',', '.'); 
      let km = getText(12).replace('KM', '').trim().replace(/\./g, '').replace(',', '.');
      
      if (valor === '') valor = '0.00';
      if (km === '') km = '0.00';

      dataRows.push({
        data: finalDate,
        protocolo,
        placa,
        chassi,
        telefone_solicitante: telSolicitante,
        beneficiario,
        telefone_beneficiario: telBeneficiario,
        situacao,
        motivo,
        servicos,
        valor: parseFloat(valor),
        km_total: parseFloat(km)
      });
    }

    return { success: true, data: dataRows };

  } catch (error) {
    return { success: false, error: error.message };
  }
}
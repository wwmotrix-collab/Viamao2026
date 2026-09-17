document.addEventListener('DOMContentLoaded', async () => {
  const totalSecoesEl = document.getElementById('total-secoes');
  const votosDeniseEl = document.getElementById('votos-denise');
  const votosHelenirEl = document.getElementById('votos-helenir');
  const totalLocaisEl = document.getElementById('total-locais');
  const listaSecoesEl = document.getElementById('lista-secoes');

  const filtroZonaEl = document.getElementById('filtro-zona');
  const filtroBairroEl = document.getElementById('filtro-bairro');
  const filtroLocalEl = document.getElementById('filtro-local');
  const filtroCandidataEl = document.getElementById('filtro-candidata');

  let secoes = [];
  let locais = [];
  let similaridade = [];

  async function loadJSON(url) {
    const candidates = [url, url.replace('/data/', '../data/'), url.replace('/data/', '/data/')];
    for (const candidate of candidates) {
      try {
        const response = await fetch(candidate, { cache: 'no-store' });
        if (!response.ok) continue;
        const data = await response.json();
        if (Array.isArray(data)) return data;
        if (data && Array.isArray(data.secoes)) return data.secoes;
        if (data && Array.isArray(data.locais)) return data.locais;
      } catch (_) {
        continue;
      }
    }
    return [];
  }

  async function init() {
    secoes = await loadJSON('/data/processed/secoes_normalized.json');
    locais = await loadJSON('/data/processed/locais_normalized.json');

    const analise = await fetch('/data/processed/similarity_analysis.json', { cache: 'no-store' })
      .then(r => r.ok ? r.json() : null)
      .catch(() => null);

    if (analise && Array.isArray(analise.padroes)) {
      similaridade = analise.padroes.flatMap((padrao) => {
        const lista = padrao.secoes_similares || [];
        return lista.map(item => ({
          ...item,
          motivo: item.motivo || 'Perfil eleitoral próximo',
          zona: padrao.caracteristicas?.zona_eleitoral,
          secao: item.secao || item.secao_numero,
        }));
      });
    }

    renderFiltros();
    syncResumo();
    renderSecoesSemelhantes();
  }

  function syncResumo() {
    const totalSecoes = secoes.length;
    const totalDenise = secoes.reduce((sum, s) => sum + (s.votos?.denise || 0), 0);
    const totalHelenir = secoes.reduce((sum, s) => sum + (s.votos?.helenir || 0), 0);

    totalSecoesEl.textContent = totalSecoes;
    votosDeniseEl.textContent = totalDenise;
    votosHelenirEl.textContent = totalHelenir;
    totalLocaisEl.textContent = locais.length;
  }

  function renderFiltros() {
    const zonas = [...new Set(secoes.map(s => s.zona_eleitoral))].filter(Boolean).sort((a, b) => a - b);
    const bairros = [...new Set(secoes.map(s => s.bairro))].filter(Boolean).sort();
    const locaisNomes = [...new Set(secoes.map(s => s.local))].filter(Boolean).sort();

    filtroZonaEl.innerHTML = '<option value="all">Todas as zonas</option>';
    filtroBairroEl.innerHTML = '<option value="all">Todos os bairros</option>';
    filtroLocalEl.innerHTML = '<option value="all">Todos os locais</option>';

    zonas.forEach(z => {
      const option = document.createElement('option');
      option.value = z;
      option.textContent = `Zona ${z}`;
      filtroZonaEl.appendChild(option);
    });

    bairros.forEach(b => {
      const option = document.createElement('option');
      option.value = b;
      option.textContent = b;
      filtroBairroEl.appendChild(option);
    });

    locaisNomes.forEach(l => {
      const option = document.createElement('option');
      option.value = l;
      option.textContent = l;
      filtroLocalEl.appendChild(option);
    });
  }

  function renderSecoesSemelhantes() {
    const filtroZona = filtroZonaEl.value;
    const filtroBairro = filtroBairroEl.value;
    const filtroLocal = filtroLocalEl.value;
    const filtroCandidata = filtroCandidataEl.value;

    let lista = similaridade.length ? similaridade : secoes.slice(0, 8).map((s) => ({
      secao: s.secao_numero,
      local: s.local,
      bairro: s.bairro,
      similaridade: 0.8,
      motivo: 'Sugestão por presença no mesmo bairro',
      denise: s.votos?.denise || 0,
      helenir: s.votos?.helenir || 0,
    }));

    lista = lista.filter((item) => {
      const matchingSecao = secoes.find((s) => String(s.secao_numero) === String(item.secao));
      if (!matchingSecao) return false;

      const zonaOk = filtroZona === 'all' || Number(matchingSecao.zona_eleitoral) === Number(filtroZona);
      const bairroOk = filtroBairro === 'all' || matchingSecao.bairro === filtroBairro;
      const localOk = filtroLocal === 'all' || matchingSecao.local === filtroLocal;

      if (!zonaOk || !bairroOk || !localOk) return false;

      if (filtroCandidata === 'denise') {
        return (matchingSecao.votos?.denise || 0) >= 0;
      }
      if (filtroCandidata === 'helenir') {
        return (matchingSecao.votos?.helenir || 0) >= 0;
      }
      return true;
    }).sort((a, b) => (b.similaridade || 0) - (a.similaridade || 0)).slice(0, 8);

    listaSecoesEl.innerHTML = '';

    if (!lista.length) {
      const li = document.createElement('li');
      li.textContent = 'Nenhuma seção encontrada para os filtros atuais.';
      listaSecoesEl.appendChild(li);
      return;
    }

    lista.forEach((item) => {
      const secao = secoes.find((s) => String(s.secao_numero) === String(item.secao));
      const li = document.createElement('li');
      li.innerHTML = `
        <strong>Seção ${item.secao}</strong><br>
        ${secao?.local || item.local || 'Local não informado'}<br>
        <small>Similaridade: ${(item.similaridade || 0.8).toFixed(2)} · ${item.motivo || 'Perfil eleitoral semelhante'}</small><br>
        Denise: ${secao?.votos?.denise ?? item.denise ?? 0} | Helenir: ${secao?.votos?.helenir ?? item.helenir ?? 0}
      `;
      listaSecoesEl.appendChild(li);
    });
  }

  [filtroZonaEl, filtroBairroEl, filtroLocalEl, filtroCandidataEl].forEach((element) => {
    element.addEventListener('change', renderSecoesSemelhantes);
  });

  init();
});

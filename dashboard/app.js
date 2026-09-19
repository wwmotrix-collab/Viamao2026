document.addEventListener('DOMContentLoaded', async () => {
  const $ = (id) => document.getElementById(id);
  const totalSecoesEl = $('total-secoes');
  const votosDeniseEl = $('votos-denise');
  const votosHelenirEl = $('votos-helenir');
  const totalLocaisEl = $('total-locais');
  const listaSecoesEl = $('lista-secoes');
  const perfilSecaoEl = $('perfil-secao');
  const listaPerfilSimilarEl = $('lista-perfil-similar');
  const filtroZonaEl = $('filtro-zona');
  const filtroBairroEl = $('filtro-bairro');
  const filtroLocalEl = $('filtro-local');
  const filtroCandidataEl = $('filtro-candidata');
  const filtroSecaoEl = $('filtro-secao');

  let secoes = [];
  let locais = [];
  let similaridade = [];
  let perfil = new Map();

  async function loadJSON(url) {
    for (const candidate of [url, url.replace('/data/', '../data/')]) {
      try {
        const response = await fetch(candidate, { cache: 'no-store' });
        if (!response.ok) continue;
        const data = await response.json();
        if (Array.isArray(data)) return data;
        if (data && Array.isArray(data.secoes)) return data.secoes;
        if (data && Array.isArray(data.locais)) return data.locais;
      } catch (_) {}
    }
    return [];
  }

  async function loadPerfil() {
    const response = await fetch('/data/processed/viamao_perfil_2024.json?v=20260919', { cache: 'no-store' });
    if (!response.ok) throw new Error('Perfil 2024 indisponível');
    const pkg = await response.json();
    if (pkg.encoding !== 'gzip+base64') throw new Error('Formato de perfil não suportado');
    if (!('DecompressionStream' in window)) throw new Error('Navegador sem suporte à descompressão gzip');

    const raw = atob(pkg.dados);
    const bytes = Uint8Array.from(raw, c => c.charCodeAt(0));
    const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'));
    const json = JSON.parse(await new Response(stream).text());

    perfil.clear();
    for (const x of json) {
      // Formato v2: [zona, secao, local, registros, feminino, idade1..4, escolaridade1..6]
      perfil.set(x[0] + ':' + x[1], {
        z: Number(x[0]),
        s: Number(x[1]),
        l: Number(x[2]),
        r: Number(x[3]),
        f: Number(x[4]),
        a: x.slice(5, 9).map(Number),
        e: x.slice(9, 15).map(Number)
      });
    }
    renderSecoesPerfil();
  }

  function profileVector(p) {
    return [p.f, ...p.a, ...p.e];
  }

  function profileDistance(a, b) {
    const av = profileVector(a);
    const bv = profileVector(b);
    let sum = 0;
    for (let i = 0; i < Math.min(av.length, bv.length); i++) {
      sum += (av[i] - bv[i]) ** 2;
    }
    return Math.sqrt(sum);
  }

  function similarProfiles(base) {
    if (!base) return [];
    return [...perfil.values()]
      .filter(p => !(p.z === base.z && p.s === base.s))
      .map(p => ({ p, d: profileDistance(base, p) }))
      .sort((a, b) => a.d - b.d)
      .slice(0, 6);
  }

  function pct(v) {
    return Number(v || 0).toFixed(1) + '%';
  }

  function bar(label, value) {
    return '<div class="perfil-bar-row">' +
      '<span>' + label + '</span>' +
      '<div class="perfil-bar-track"><i style="width:' + Math.max(0, Math.min(100, Number(value) || 0)) + '%"></i></div>' +
      '<strong>' + pct(value) + '</strong></div>';
  }

  function renderSecoesPerfil() {
    const keys = [...perfil.keys()].sort((a, b) => {
      const [az, as] = a.split(':').map(Number);
      const [bz, bs] = b.split(':').map(Number);
      return az - bz || as - bs;
    });

    filtroSecaoEl.innerHTML = '<option value="all">Selecione uma seção</option>';
    for (const key of keys) {
      const p = perfil.get(key);
      const o = document.createElement('option');
      o.value = key;
      o.textContent = 'Zona ' + p.z + ' · Seção ' + p.s;
      filtroSecaoEl.appendChild(o);
    }
  }

  function renderPerfilSelecionado() {
    const key = filtroSecaoEl.value;
    listaPerfilSimilarEl.innerHTML = '';

    if (key === 'all') {
      perfilSecaoEl.innerHTML = '<small>Selecione uma seção para visualizar os dados detalhados do eleitorado de 2024.</small>';
      return;
    }

    const p = perfil.get(key);
    if (!p) return;

    const total = p.r || 0;
    perfilSecaoEl.innerHTML =
      '<div class="perfil-header"><strong>Zona ' + p.z + ' · Seção ' + p.s + '</strong>' +
      '<span>Registros observados: ' + total + '</span></div>' +
      '<div class="perfil-grid">' +
        '<div><h5>Gênero</h5>' +
          bar('Feminino', p.f) +
          bar('Masculino', 100 - p.f) +
        '</div>' +
        '<div><h5>Faixa etária</h5>' +
          bar('18–29', p.a[0]) +
          bar('30–44', p.a[1]) +
          bar('45–59', p.a[2]) +
          bar('60+', p.a[3]) +
        '</div>' +
      '</div>' +
      '<div class="perfil-block"><h5>Escolaridade</h5>' +
        bar('Analfabeto', p.e[0]) +
        bar('Lê e escreve', p.e[1]) +
        bar('Fundamental', p.e[2]) +
        bar('Médio', p.e[3]) +
        bar('Superior', p.e[4]) +
        bar('Outro', p.e[5]) +
      '</div>' +
      '<small class="perfil-nota">Os percentuais são proporções calculadas sobre os registros de perfil extraídos do arquivo de 2024; o campo “registros observados” não deve ser interpretado como total oficial de eleitores da seção.</small>';

    for (const item of similarProfiles(p)) {
      const li = document.createElement('li');
      li.innerHTML = '<strong>Zona ' + item.p.z + ' · Seção ' + item.p.s +
        '</strong><br><small>distância estatística de perfil: ' + item.d.toFixed(2) + '</small>';
      li.style.cursor = 'pointer';
      li.title = 'Abrir perfil desta seção';
      li.addEventListener('click', () => {
        filtroSecaoEl.value = item.p.z + ':' + item.p.s;
        renderPerfilSelecionado();
      });
      listaPerfilSimilarEl.appendChild(li);
    }
  }

  async function init() {
    secoes = await loadJSON('/data/processed/secoes_normalized.json');
    locais = await loadJSON('/data/processed/locais_normalized.json');

    const analise = await fetch('/data/processed/similarity_analysis.json', { cache: 'no-store' })
      .then(r => r.ok ? r.json() : null)
      .catch(() => null);

    if (analise && Array.isArray(analise.padroes)) {
      similaridade = analise.padroes.flatMap(padrao =>
        (padrao.secoes_similares || []).map(item => ({
          ...item,
          zona: padrao.caracteristicas?.zona_eleitoral,
          secao: item.secao || item.secao_numero
        }))
      );
    }

    renderFiltros();
    syncResumo();
    renderSecoesSemelhantes();

    try {
      await loadPerfil();
    } catch (e) {
      console.error('Perfil 2024:', e);
      perfilSecaoEl.innerHTML =
        '<small>Não foi possível carregar o perfil detalhado de 2024. Atualize a página ou abra em um navegador com suporte a gzip.</small>';
    }
  }

  function syncResumo() {
    totalSecoesEl.textContent = secoes.length;
    votosDeniseEl.textContent = secoes.reduce((sum, s) => sum + (s.votos?.denise || 0), 0);
    votosHelenirEl.textContent = secoes.reduce((sum, s) => sum + (s.votos?.helenir || 0), 0);
    totalLocaisEl.textContent = locais.length;
  }

  function renderFiltros() {
    const zonas = [...new Set(secoes.map(s => s.zona_eleitoral))].filter(Boolean).sort((a,b) => a-b);
    const bairros = [...new Set(secoes.map(s => s.bairro))].filter(Boolean).sort();
    const nomes = [...new Set(secoes.map(s => s.local))].filter(Boolean).sort();

    filtroZonaEl.innerHTML = '<option value="all">Todas as zonas</option>';
    filtroBairroEl.innerHTML = '<option value="all">Todos os bairros</option>';
    filtroLocalEl.innerHTML = '<option value="all">Todos os locais</option>';

    for (const z of zonas) filtroZonaEl.insertAdjacentHTML('beforeend', '<option value="' + z + '">Zona ' + z + '</option>');
    for (const b of bairros) filtroBairroEl.insertAdjacentHTML('beforeend', '<option value="' + b + '">' + b + '</option>');
    for (const l of nomes) filtroLocalEl.insertAdjacentHTML('beforeend', '<option value="' + l + '">' + l + '</option>');
  }

  function renderSecoesSemelhantes() {
    const zona = filtroZonaEl.value;
    const bairro = filtroBairroEl.value;
    const local = filtroLocalEl.value;

    let lista = similaridade.length ? similaridade : secoes.slice(0, 8).map(s => ({
      secao: s.secao_numero,
      local: s.local,
      bairro: s.bairro,
      similaridade: 0.8
    }));

    lista = lista.filter(item => {
      const s = secoes.find(x =>
        Number(x.zona_eleitoral) === Number(item.zona) &&
        String(x.secao_numero) === String(item.secao)
      ) || secoes.find(x => String(x.secao_numero) === String(item.secao));

      if (!s) return false;

      return (zona === 'all' || Number(s.zona_eleitoral) === Number(zona)) &&
        (bairro === 'all' || s.bairro === bairro) &&
        (local === 'all' || s.local === local);
    }).sort((a,b) => (b.similaridade || 0) - (a.similaridade || 0)).slice(0, 8);

    listaSecoesEl.innerHTML = '';

    if (!lista.length) {
      listaSecoesEl.innerHTML = '<li>Nenhuma seção encontrada para os filtros atuais.</li>';
      return;
    }

    for (const item of lista) {
      const s = secoes.find(x =>
        Number(x.zona_eleitoral) === Number(item.zona) &&
        String(x.secao_numero) === String(item.secao)
      ) || secoes.find(x => String(x.secao_numero) === String(item.secao));

      const li = document.createElement('li');
      li.innerHTML =
        '<strong>Zona ' + s.zona_eleitoral + ' · Seção ' + item.secao + '</strong><br>' +
        (s.local || item.local || 'Local não informado') + '<br>' +
        '<small>Semelhança eleitoral: ' + Number(item.similaridade || 0).toFixed(2) + '</small><br>' +
        'Denise: ' + (s.votos?.denise ?? 0) + ' | Helenir: ' + (s.votos?.helenir ?? 0);

      li.style.cursor = 'pointer';
      li.title = 'Abrir perfil 2024 desta seção';

      li.addEventListener('click', () => {
        const key = Number(s.zona_eleitoral) + ':' + Number(s.secao_numero);
        if (perfil.has(key)) {
          filtroSecaoEl.value = key;
          renderPerfilSelecionado();
          document.querySelector('.perfil-panel')?.scrollIntoView({behavior:'smooth', block:'nearest'});
        }
      });

      listaSecoesEl.appendChild(li);
    }
  }

  [filtroZonaEl, filtroBairroEl, filtroLocalEl, filtroCandidataEl]
    .forEach(el => el.addEventListener('change', renderSecoesSemelhantes));

  filtroSecaoEl.addEventListener('change', renderPerfilSelecionado);

  init();
});

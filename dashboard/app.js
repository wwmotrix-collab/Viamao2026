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

  let secoes = [], locais = [], similaridade = [], perfil = new Map();

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
    // O v3 está publicado como pacote gzip+base64 em viamao_perfil_2024_v3.json.
    const response = await fetch('/data/processed/viamao_perfil_2024_v3.json?v=20260919', { cache: 'no-store' });
    if (!response.ok) throw new Error('Perfil 2024 indisponível');
    const pkg = await response.json();
    perfil.clear();

    if (pkg.schema !== 'viamao2024.perfil-eleitorado.v3' || pkg.encoding !== 'gzip+base64' || !pkg.dados) {
      throw new Error('Pacote v3 de perfil inválido');
    }
    if (!('DecompressionStream' in window)) throw new Error('Navegador sem suporte à descompressão gzip');

    const raw = atob(pkg.dados);
    const bytes = Uint8Array.from(raw, c => c.charCodeAt(0));
    const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'));
    const decoded = JSON.parse(await new Response(stream).text());
    const secoesV3 = Array.isArray(decoded) ? decoded : decoded.secoes;

    if (!Array.isArray(secoesV3)) throw new Error('Seções v3 não encontradas após descompressão');

    for (const x of secoesV3) {
      perfil.set(Number(x.zona) + ':' + Number(x.secao), {
        z: Number(x.zona), s: Number(x.secao), l: Number(x.local_codigo),
        total: Number(x.total || 0), genero: x.genero || {},
        faixa_etaria: x.faixa_etaria || {}, escolaridade: x.escolaridade || {},
        biometria: Number(x.biometria || 0), deficiencia: Number(x.deficiencia || 0),
        nome_social: Number(x.nome_social || 0)
      });
    }
    renderSecoesPerfil();
  }

  function pct(v, total) {
    return total ? ((Number(v || 0) / total) * 100).toFixed(1) + '%' : '0.0%';
  }
  function bar(label, value, total) {
    const p = total ? (Number(value || 0) / total) * 100 : Number(value || 0);
    return '<div class="perfil-bar-row"><span>' + label + '</span><div class="perfil-bar-track"><i style="width:' +
      Math.max(0, Math.min(100, p)) + '%"></i></div><strong>' + Number(value || 0).toLocaleString('pt-BR') +
      ' (' + (total ? pct(value, total) : Number(value || 0).toFixed(1) + '%') + ')</strong></div>';
  }

  function profileVector(p) {
    if (p.genero) {
      const total = p.total || 1;
      const f = (p.genero.FEMININO || 0) / total * 100;
      const ages = ['16 anos','17 anos','18 anos','19 anos','20 anos','21 a 24 anos','25 a 29 anos','30 a 34 anos','35 a 39 anos','40 a 44 anos','45 a 49 anos','50 a 54 anos','55 a 59 anos','60 a 64 anos','65 a 69 anos','70 a 74 anos','75 a 79 anos','80 a 84 anos','85 a 89 anos','90 a 94 anos','95 a 99 anos','100 anos ou mais'];
      const age = ages.map(k => (p.faixa_etaria?.[k] || 0) / total * 100);
      return [f, ...age];
    }
    return [p.f, ...(p.a || []), ...(p.e || [])];
  }

  function profileDistance(a, b) {
    const av = profileVector(a), bv = profileVector(b);
    let sum = 0;
    for (let i = 0; i < Math.min(av.length, bv.length); i++) sum += (av[i] - bv[i]) ** 2;
    return Math.sqrt(sum);
  }

  function similarProfiles(base) {
    if (!base) return [];
    return [...perfil.values()].filter(p => !(p.z === base.z && p.s === base.s))
      .map(p => ({ p, d: profileDistance(base, p) })).sort((a,b) => a.d-b.d).slice(0,6);
  }

  function renderSecoesPerfil() {
    const keys = [...perfil.keys()].sort((a,b) => {
      const [az,as] = a.split(':').map(Number), [bz,bs] = b.split(':').map(Number);
      return az-bz || as-bs;
    });
    filtroSecaoEl.innerHTML = '<option value="all">Selecione uma seção</option>';
    for (const key of keys) {
      const p = perfil.get(key), o = document.createElement('option');
      o.value = key; o.textContent = 'Zona ' + p.z + ' · Seção ' + p.s;
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

    if (p.genero) {
      const total = p.total;
      const age = p.faixa_etaria || {}, edu = p.escolaridade || {};
      const ageGroups = [
        ['16–29', ['16 anos','17 anos','18 anos','19 anos','20 anos','21 a 24 anos','25 a 29 anos']],
        ['30–44', ['30 a 34 anos','35 a 39 anos','40 a 44 anos']],
        ['45–59', ['45 a 49 anos','50 a 54 anos','55 a 59 anos']],
        ['60+', ['60 a 64 anos','65 a 69 anos','70 a 74 anos','75 a 79 anos','80 a 84 anos','85 a 89 anos','90 a 94 anos','95 a 99 anos','100 anos ou mais']]
      ];
      const ageHtml = ageGroups.map(([label, keys]) => bar(label, keys.reduce((s,k)=>s+(age[k]||0),0), total)).join('');
      const eduOrder = ['ANALFABETO','LÊ E ESCREVE','ENSINO FUNDAMENTAL INCOMPLETO','ENSINO FUNDAMENTAL COMPLETO','ENSINO MÉDIO INCOMPLETO','ENSINO MÉDIO COMPLETO','SUPERIOR INCOMPLETO','SUPERIOR COMPLETO','NÃO INFORMADO'];
      const eduHtml = eduOrder.map(k => edu[k] != null ? bar(k, edu[k], total) : '').join('');
      perfilSecaoEl.innerHTML =
        '<div class="perfil-header"><strong>Zona ' + p.z + ' · Seção ' + p.s + '</strong><span>Total: ' + total.toLocaleString('pt-BR') + ' eleitores</span></div>' +
        '<div class="perfil-grid"><div><h5>Gênero</h5>' + bar('Feminino', p.genero.FEMININO || 0, total) + bar('Masculino', p.genero.MASCULINO || 0, total) + '</div>' +
        '<div><h5>Faixa etária</h5>' + ageHtml + '</div></div>' +
        '<div class="perfil-block"><h5>Escolaridade</h5>' + eduHtml + '</div>' +
        '<div class="perfil-grid"><div><h5>Indicadores</h5>' +
        '<div class="perfil-metric">Biometria: <strong>' + p.biometria.toLocaleString('pt-BR') + ' (' + pct(p.biometria,total) + ')</strong></div>' +
        '<div class="perfil-metric">Deficiência: <strong>' + p.deficiencia.toLocaleString('pt-BR') + ' (' + pct(p.deficiencia,total) + ')</strong></div>' +
        '<div class="perfil-metric">Nome social: <strong>' + p.nome_social.toLocaleString('pt-BR') + ' (' + pct(p.nome_social,total) + ')</strong></div>' +
        '</div></div>' +
        '<small class="perfil-nota">Contagens absolutas agregadas por seção a partir do arquivo TSE 2024 fornecido. Percentuais são calculados sobre o total de eleitores com perfil registrado na seção.</small>';
    } else {
      const total = p.r || 0;
      perfilSecaoEl.innerHTML =
        '<div class="perfil-header"><strong>Zona ' + p.z + ' · Seção ' + p.s + '</strong><span>Registros observados: ' + total + '</span></div>' +
        '<small class="perfil-nota">Pacote v2 legado: percentuais calculados sobre registros extraídos; não representam contagem oficial da seção.</small>';
    }

    for (const item of similarProfiles(p)) {
      const li = document.createElement('li');
      li.innerHTML = '<strong>Zona ' + item.p.z + ' · Seção ' + item.p.s + '</strong><br><small>distância estatística de perfil: ' + item.d.toFixed(2) + '</small>';
      li.style.cursor='pointer';
      li.addEventListener('click',()=>{ filtroSecaoEl.value=item.p.z+':'+item.p.s; renderPerfilSelecionado(); });
      listaPerfilSimilarEl.appendChild(li);
    }
  }

  async function init() {
    secoes = await loadJSON('/data/processed/secoes_normalized.json');
    locais = await loadJSON('/data/processed/locais_normalized.json');
    const analise = await fetch('/data/processed/similarity_analysis.json',{cache:'no-store'}).then(r=>r.ok?r.json():null).catch(()=>null);
    if (analise && Array.isArray(analise.padroes)) similaridade = analise.padroes.flatMap(p => (p.secoes_similares||[]).map(item => ({...item,zona:p.caracteristicas?.zona_eleitoral,secao:item.secao||item.secao_numero})));
    renderFiltros(); syncResumo(); renderSecoesSemelhantes();
    try { await loadPerfil(); } catch(e) { console.error('Perfil 2024:',e); perfilSecaoEl.innerHTML='<small>Não foi possível carregar o perfil detalhado de 2024.</small>'; }
  }

  function syncResumo() {
    totalSecoesEl.textContent=secoes.length;
    votosDeniseEl.textContent=secoes.reduce((sum,s)=>sum+(s.votos?.denise||0),0);
    votosHelenirEl.textContent=secoes.reduce((sum,s)=>sum+(s.votos?.helenir||0),0);
    totalLocaisEl.textContent=locais.length;
  }

  function renderFiltros() {
    const zonas=[...new Set(secoes.map(s=>s.zona_eleitoral))].filter(Boolean).sort((a,b)=>a-b);
    const bairros=[...new Set(secoes.map(s=>s.bairro))].filter(Boolean).sort();
    const nomes=[...new Set(secoes.map(s=>s.local))].filter(Boolean).sort();
    filtroZonaEl.innerHTML='<option value="all">Todas as zonas</option>';
    filtroBairroEl.innerHTML='<option value="all">Todos os bairros</option>';
    filtroLocalEl.innerHTML='<option value="all">Todos os locais</option>';
    for(const z of zonas) filtroZonaEl.insertAdjacentHTML('beforeend','<option value="'+z+'">Zona '+z+'</option>');
    for(const b of bairros) filtroBairroEl.insertAdjacentHTML('beforeend','<option value="'+b+'">'+b+'</option>');
    for(const l of nomes) filtroLocalEl.insertAdjacentHTML('beforeend','<option value="'+l+'">'+l+'</option>');
  }

  function renderSecoesSemelhantes() {
    const zona=filtroZonaEl.value,bairro=filtroBairroEl.value,local=filtroLocalEl.value;
    let lista=similaridade.length?similaridade:secoes.slice(0,8).map(s=>({secao:s.secao_numero,local:s.local,bairro:s.bairro,similaridade:0.8}));
    lista=lista.filter(item=>{
      const s=secoes.find(x=>Number(x.zona_eleitoral)===Number(item.zona)&&String(x.secao_numero)===String(item.secao))||secoes.find(x=>String(x.secao_numero)===String(item.secao));
      return s&&(zona==='all'||Number(s.zona_eleitoral)===Number(zona))&&(bairro==='all'||s.bairro===bairro)&&(local==='all'||s.local===local);
    }).sort((a,b)=>(b.similaridade||0)-(a.similaridade||0)).slice(0,8);
    listaSecoesEl.innerHTML='';
    if(!lista.length){listaSecoesEl.innerHTML='<li>Nenhuma seção encontrada para os filtros atuais.</li>';return;}
    for(const item of lista){
      const s=secoes.find(x=>Number(x.zona_eleitoral)===Number(item.zona)&&String(x.secao_numero)===String(item.secao))||secoes.find(x=>String(x.secao_numero)===String(item.secao));
      const li=document.createElement('li');
      li.innerHTML='<strong>Zona '+s.zona_eleitoral+' · Seção '+item.secao+'</strong><br>'+(s.local||item.local||'Local não informado')+'<br><small>Semelhança eleitoral: '+Number(item.similaridade||0).toFixed(2)+'</small><br>Denise: '+(s.votos?.denise??0)+' | Helenir: '+(s.votos?.helenir??0);
      li.style.cursor='pointer'; li.addEventListener('click',()=>{const key=Number(s.zona_eleitoral)+':'+Number(s.secao_numero);if(perfil.has(key)){filtroSecaoEl.value=key;renderPerfilSelecionado();document.querySelector('.perfil-panel')?.scrollIntoView({behavior:'smooth',block:'nearest'});}});
      listaSecoesEl.appendChild(li);
    }
  }

  [filtroZonaEl,filtroBairroEl,filtroLocalEl,filtroCandidataEl].forEach(el=>el.addEventListener('change',renderSecoesSemelhantes));
  filtroSecaoEl.addEventListener('change',renderPerfilSelecionado);
  init();
});
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

  const secoes = await fetch('../data/processed/secoes_normalized.json').then(r => r.json()).then(d => d.secoes);
  const locais = await fetch('../data/processed/locais_normalized.json').then(r => r.json()).then(d => d.locais);

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
    const zonas = [...new Set(secoes.map(s => s.zona_eleitoral))].sort((a, b) => a - b);
    const bairros = [...new Set(secoes.map(s => s.bairro))].sort();
    const locaisNomes = [...new Set(secoes.map(s => s.local))].sort();

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
    const selecionadas = secoes.slice(0, 6).map(s => ({
      secao: s.secao_numero,
      bairro: s.bairro,
      local: s.local,
      denise: s.votos?.denise || 0,
      helenir: s.votos?.helenir || 0,
    }));

    listaSecoesEl.innerHTML = '';
    selecionadas.forEach(item => {
      const li = document.createElement('li');
      li.innerHTML = `<strong>Seção ${item.secao}</strong><br>${item.local}<br>Denise: ${item.denise} | Helenir: ${item.helenir}`;
      listaSecoesEl.appendChild(li);
    });
  }

  filtroZonaEl.addEventListener('change', () => {
    // futura lógica de filtro real
  });

  renderFiltros();
  syncResumo();
  renderSecoesSemelhantes();
});

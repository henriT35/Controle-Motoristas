(function () {
  'use strict';

  const geometryCache = new Map();
  const localityCache = new Map();
  const chartCache = new WeakMap();

  function normalize(value) {
    return String(value || '')
      .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
      .toUpperCase().replace(/[^A-Z0-9]+/g, ' ').trim().replace(/\s+/g, ' ');
  }

  function fmt(value, format) {
    const n = Number(value || 0);
    if (format === 'percent') return `${n.toLocaleString('pt-BR', {maximumFractionDigits: 1})}%`;
    if (format === 'weight') {
      if (Math.abs(n) >= 1000) return `${(n / 1000).toLocaleString('pt-BR', {maximumFractionDigits: 1})} t`;
      return `${n.toLocaleString('pt-BR', {maximumFractionDigits: 0})} kg`;
    }
    return n.toLocaleString('pt-BR', {maximumFractionDigits: 0});
  }

  function shortName(value, max = 18) {
    const name = String(value || '').trim();
    if (name.length <= max) return name;
    return `${name.slice(0, Math.max(8, max - 1)).trim()}…`;
  }

  function escapeHtml(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
  }

  function featureName(feature, properties) {
    const p = feature.properties || {};
    for (const key of properties || []) {
      if (p[key]) return String(p[key]);
    }
    for (const key of [
      'name', 'nome', 'NOME', 'nomearea', 'NM_MUN', 'BAI_NM', 'NM_BAIRRO',
      'bairro', 'BAIRRO', 'nome_bairro', 'Name'
    ]) {
      if (p[key]) return String(p[key]);
    }
    return '';
  }

  function featureCode(feature, properties) {
    const p = feature.properties || {};
    for (const key of properties || []) {
      if (p[key] !== undefined && p[key] !== null && String(p[key]).trim()) {
        return String(p[key]).trim();
      }
    }
    for (const key of ['codarea', 'CD_MUN', 'id']) {
      if (p[key] !== undefined && p[key] !== null && String(p[key]).trim()) {
        return String(p[key]).trim();
      }
    }
    return '';
  }

  async function fetchJSON(url) {
    if (geometryCache.has(url)) return geometryCache.get(url);
    const promise = fetch(url, {headers: {'Accept': 'application/vnd.geo+json, application/json'}})
      .then(r => {
        if (!r.ok) throw new Error(`Geometria indisponível (${r.status})`);
        return r.json();
      });
    geometryCache.set(url, promise);
    return promise;
  }

  async function fetchLocalities(url) {
    if (localityCache.has(url)) return localityCache.get(url);
    const promise = fetch(url, {headers: {'Accept': 'application/json'}})
      .then(r => {
        if (!r.ok) throw new Error(`Cadastro geográfico indisponível (${r.status})`);
        return r.json();
      })
      .then(rows => {
        const byCode = new Map();
        for (const row of Array.isArray(rows) ? rows : []) {
          if (row && row.id !== undefined && row.nome) byCode.set(String(row.id), String(row.nome));
        }
        return byCode;
      });
    localityCache.set(url, promise);
    return promise;
  }

  async function loadMunicipalityNames(geometry) {
    const sources = geometry.locality_sources || [];
    if (!sources.length) return new Map();
    const maps = await Promise.all(sources.map(source => fetchLocalities(source.url)));
    const names = new Map();
    for (const sourceMap of maps) {
      for (const [code, name] of sourceMap.entries()) names.set(code, name);
    }
    return names;
  }

  async function loadGeometry(geometry) {
    const urls = geometry.urls || [];
    if (!urls.length) throw new Error('Não há geometria de bairro homologada para esta região.');
    const [collections, municipalityNames] = await Promise.all([
      Promise.all(urls.map(fetchJSON)),
      geometry.level === 'municipality' ? loadMunicipalityNames(geometry) : Promise.resolve(new Map()),
    ]);
    const features = [];
    let rawFeatureCount = 0;
    for (const collection of collections) {
      const rows = collection && collection.type === 'FeatureCollection' ? collection.features : [];
      rawFeatureCount += Array.isArray(rows) ? rows.length : 0;
      for (const feature of rows || []) {
        if (!feature || !feature.geometry) continue;
        let name = featureName(feature, geometry.feature_name_properties);
        if (!name && geometry.level === 'municipality') {
          const code = featureCode(feature, geometry.feature_code_properties);
          if (code) name = municipalityNames.get(code) || '';
        }
        if (!name) continue;
        feature.properties = feature.properties || {};
        feature.properties.name = name;
        features.push(feature);
      }
    }
    if (!features.length) {
      if (rawFeatureCount) {
        throw new Error('A malha foi recebida, mas os municípios não puderam ser identificados.');
      }
      throw new Error('A fonte geográfica respondeu sem polígonos utilizáveis.');
    }
    return {type: 'FeatureCollection', features};
  }

  function palette(payload) {
    if (payload.metric.palette === 'negative') {
      return ['#263238', '#3b3831', '#514034', '#66463a', '#765047'];
    }
    return ['#1d3230', '#26423a', '#305346', '#39634e', '#44735a'];
  }

  function metricLead(payload, row) {
    const key = payload.metric.key;
    return fmt(row && row[key] !== undefined ? row[key] : row?.value, payload.metric.format);
  }

  function tooltipHTML(payload, name, row) {
    if (!row || !row.attempts) {
      return `<div class="geo-tooltip-card geo-tooltip-empty"><div class="geo-tooltip-region">${name}</div><div class="geo-tooltip-muted">Sem movimento no período</div></div>`;
    }
    return `
      <div class="geo-tooltip-card">
        <div class="geo-tooltip-top">
          <div>
            <div class="geo-tooltip-kicker">${payload.level === 'neighborhood' ? 'Bairro' : 'Município'}</div>
            <div class="geo-tooltip-region">${name}</div>
          </div>
          <div class="geo-tooltip-lead"><b>${metricLead(payload, row)}</b><span>${payload.metric.label}</span></div>
        </div>
        <div class="geo-tooltip-rule"></div>
        <div class="geo-tooltip-grid">
          <span>Tentativas <b>${fmt(row.attempts, 'integer')}</b></span>
          <span>Entregas <b>${fmt(row.delivered, 'integer')}</b></span>
          <span>Sucesso <b>${fmt(row.success_rate, 'percent')}</b></span>
          <span>Entregas limpas <b>${fmt(row.clean_deliveries, 'integer')}</b></span>
          <span>Retenções <b>${fmt(row.retentions, 'integer')}</b></span>
          <span>Horário <b>${fmt(row.time_window_failures, 'integer')}</b></span>
          <span class="geo-tooltip-wide">Comprovantes ativos <b>${fmt(row.active_proofs, 'integer')}</b></span>
        </div>
      </div>`;
  }

  function chartOption(payload, geometry, mapName, compact) {
    const visualRegions = payload.map_regions || payload.regions || [];
    const byNorm = new Map(visualRegions.map(r => [normalize(r.name), r]));
    const data = [];
    for (const feature of geometry.features) {
      const name = feature.properties && feature.properties.name;
      if (!name) continue;
      const row = byNorm.get(normalize(name));
      data.push({
        ...(row || {}),
        name,
        value: row ? Number(row.value || 0) : null,
        _metricValue: row ? Number(row.value || 0) : 0,
        _labelTier: 0,
        itemStyle: row ? {
          borderColor: 'rgba(112,135,154,.48)',
          borderWidth: 0.72,
          opacity: 0.96,
        } : {
          areaColor: '#101d29',
          borderColor: 'rgba(76,98,119,.27)',
          borderWidth: 0.58,
          opacity: 0.42,
        },
      });
    }

    const active = data.filter(x => x.attempts);
    const values = active.map(x => Number(x._metricValue || 0)).filter(Number.isFinite);
    const max = Math.max(...values, 1);
    const colors = palette(payload);

    // Hierarquia visual de labels: poucos nomes completos, alguns valores e o
    // restante apenas no hover. É apresentação, não altera dados/agregações.
    const sorted = [...active].sort((a, b) =>
      (b._metricValue - a._metricValue) || (b.attempts - a.attempts)
    );
    const primaryLimit = compact ? 3 : (payload.level === 'neighborhood' ? 7 : Math.min(active.length, 15));
    const secondaryLimit = compact ? 5 : (payload.level === 'neighborhood' ? 12 : primaryLimit);
    sorted.forEach((row, index) => {
      // No nível MUNICÍPIO, todas as regiões ativas recebem nome + valor quando a
      // amostra é razoável. O hideOverlap ainda evita poluição em áreas densas.
      row._labelTier = index < primaryLimit ? 1 : (index < secondaryLimit ? 2 : 0);
    });
    for (const row of data) {
      row.label = {show: Boolean(row.attempts && row._labelTier)};
    }

    // O enquadramento é intencionalmente um pouco mais fechado para o mapa
    // ocupar o card. Outliers continuam sendo definidos pelo backend; aqui só
    // refinamos a apresentação do conjunto já entregue pela API.
    let zoom = 1.12;
    let layoutSize = '106%';
    let layoutCenter = ['50%', '50%'];
    if (payload.level === 'municipality') {
      if (active.length <= 5) zoom = 1.52;
      else if (active.length <= 8) zoom = 1.40;
      else if (active.length <= 12) zoom = 1.30;
      else zoom = 1.22;
      layoutSize = compact ? '108%' : '116%';
      layoutCenter = compact ? ['47%', '50%'] : ['46%', '49%'];
    } else {
      zoom = active.length <= 8 ? 1.20 : 1.12;
      layoutSize = compact ? '104%' : '108%';
      layoutCenter = ['50%', '50%'];
    }
    if (compact) zoom = Math.max(1.08, zoom - 0.10);

    return {
      animation: true,
      animationDuration: 360,
      animationDurationUpdate: 220,
      animationEasing: 'cubicOut',
      animationEasingUpdate: 'cubicOut',
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'item',
        confine: true,
        renderMode: 'html',
        className: 'geo-echarts-tooltip',
        backgroundColor: 'rgba(7,17,29,.992)',
        borderColor: 'rgba(96,119,140,.36)',
        borderWidth: 1,
        padding: 0,
        textStyle: {color: '#dbe7f4', fontFamily: 'Inter, sans-serif'},
        extraCssText: 'border-radius:13px;box-shadow:0 16px 38px rgba(0,0,0,.30);backdrop-filter:blur(10px);',
        formatter(params) {
          return tooltipHTML(payload, params.name, params.data || {});
        }
      },
      visualMap: {
        show: false,
        min: 0,
        max,
        inRange: {color: colors},
      },
      series: [{
        type: 'map',
        map: mapName,
        roam: true,
        selectedMode: false,
        zoom,
        scaleLimit: {min: 0.90, max: 8},
        layoutCenter,
        layoutSize,
        label: {
          show: true,
          color: '#c7d3de',
          fontFamily: 'Inter, sans-serif',
          fontSize: compact ? 8 : 9.5,
          fontWeight: 520,
          lineHeight: compact ? 11 : 13,
          textBorderColor: 'rgba(4,12,21,.94)',
          textBorderWidth: compact ? 2.5 : 3,
          formatter: p => {
            const row = p.data || {};
            if (!row.attempts || !row._labelTier) return '';
            const value = fmt(row._metricValue, payload.metric.format);
            if (row._labelTier === 2) return `{valueOnly|${value}}`;
            const maxChars = compact ? 11 : (payload.level === 'neighborhood' ? 13 : 15);
            return `${shortName(p.name, maxChars)}
{value|${value}}`;
          },
          rich: {
            value: {
              color: '#edf2f6',
              fontSize: compact ? 9 : 11,
              fontWeight: 680,
              lineHeight: compact ? 12 : 15,
            },
            valueOnly: {
              color: '#dbe5ed',
              fontSize: compact ? 8.5 : 10,
              fontWeight: 650,
              lineHeight: compact ? 11 : 13,
              backgroundColor: 'rgba(5,14,24,.42)',
              padding: [2, 4],
              borderRadius: 4,
            }
          },
        },
        labelLayout: {
          hideOverlap: true,
          moveOverlap: 'shiftY',
        },
        itemStyle: {
          areaColor: '#101d29',
          borderColor: 'rgba(92,114,135,.38)',
          borderWidth: 0.66,
        },
        emphasis: {
          label: {
            show: true,
            color: '#f2f5f8',
            fontWeight: 620,
            textBorderColor: 'rgba(4,12,21,.96)',
            textBorderWidth: 3,
          },
          itemStyle: {
            borderColor: 'rgba(183,199,212,.76)',
            borderWidth: 1.05,
            shadowBlur: 3,
            shadowColor: 'rgba(0,0,0,.22)',
          },
        },
        data,
      }]
    };
  }

  function ensureMapChrome(root) {
    const stage = root.parentElement;
    if (!stage) return {};
    let breadcrumb = stage.querySelector('[data-geo-breadcrumb]');
    if (!breadcrumb) {
      breadcrumb = document.createElement('div');
      breadcrumb.className = 'geo-breadcrumb';
      breadcrumb.dataset.geoBreadcrumb = '';
      breadcrumb.hidden = true;
      stage.appendChild(breadcrumb);
    }
    let legend = stage.querySelector('[data-geo-legend]');
    if (!legend) {
      legend = document.createElement('div');
      legend.className = 'geo-legend';
      legend.dataset.geoLegend = '';
      legend.hidden = true;
      stage.appendChild(legend);
    }
    let hint = stage.querySelector('[data-geo-roam-hint]');
    if (!hint && root.dataset.compact !== '1') {
      hint = document.createElement('div');
      hint.className = 'geo-roam-hint';
      hint.dataset.geoRoamHint = '';
      hint.textContent = 'Arraste para mover · scroll para zoom';
      stage.appendChild(hint);
    }
    return {breadcrumb, legend, hint};
  }

  function renderLegend(root, payload) {
    const {legend} = ensureMapChrome(root);
    if (!legend || root.dataset.compact === '1') return;
    const colors = palette(payload);
    legend.hidden = false;
    legend.style.setProperty('--geo-legend-gradient', `linear-gradient(90deg, ${colors.join(', ')})`);
    legend.innerHTML = `
      <div class="geo-legend-head"><span>${payload.metric.label}</span><b>${payload.metric.higher_is_better ? 'desempenho/volume' : 'atenção operacional'}</b></div>
      <div class="geo-legend-scale"></div>
      <div class="geo-legend-labels"><span>Menor</span><span>Maior</span></div>`;
  }

  function renderBreadcrumb(root, payload) {
    const {breadcrumb} = ensureMapChrome(root);
    if (!breadcrumb || root.dataset.compact === '1') return;
    const parent = payload.parent || {};
    if (payload.level !== 'neighborhood' || (!parent.state && !parent.city)) {
      breadcrumb.hidden = true;
      breadcrumb.innerHTML = '';
      return;
    }
    breadcrumb.hidden = false;
    breadcrumb.innerHTML = `<span>${parent.state || 'UF'}</span><i>›</i><b>${parent.city || 'Município'}</b>`;
  }

  function renderRanking(root, payload) {
    const box = root.closest('.geo-shell')?.querySelector('[data-geo-ranking]');
    if (!box) return;
    const levelLabel = payload.level === 'neighborhood' ? 'Bairros' : 'Municípios';
    const title = box.closest('.panel')?.querySelector('[data-ranking-title]');
    if (title) title.textContent = `Top 5 ${levelLabel} — ${payload.metric.label}`;
    if (!payload.ranking.length) {
      box.innerHTML = '<div class="geo-empty-small">Sem regiões com movimento.</div>';
      return;
    }
    const peak = Math.max(...payload.ranking.map(r => Number(r.value || 0)), 1);
    box.innerHTML = payload.ranking.map((r, i) => `
      <div class="geo-rank-row" title="${r.name}: ${fmt(r.value, payload.metric.format)}">
        <span class="geo-rank-pos">${String(i + 1).padStart(2, '0')}</span>
        <span class="geo-rank-name">${r.name}<small>${fmt(r.attempts, 'integer')} tentativas</small></span>
        <span class="geo-rank-value">${fmt(r.value, payload.metric.format)}</span>
        <span class="geo-rank-bar"><i style="width:${Math.max(4, (Number(r.value || 0) / peak) * 100)}%"></i></span>
      </div>`).join('');
  }

  function renderAlerts(root, payload) {
    const box = root.closest('.geo-shell')?.querySelector('[data-geo-alerts]');
    if (!box) return;
    if (!payload.alerts.length) {
      box.innerHTML = '<div class="geo-empty-small geo-alert-clear"><span class="geo-ok-dot"></span><span>Nenhum alerta regional relevante para a amostra.</span></div>';
      return;
    }
    box.innerHTML = payload.alerts.slice(0, 4).map(a => `
      <div class="geo-alert-row ${a.severity || 'medium'}">
        <span class="geo-alert-dot"></span>
        <span><b>${a.region}</b><small>${a.message}</small></span>
      </div>`).join('');
  }

  function renderSummary(root, payload) {
    const shell = root.closest('.geo-shell');
    if (!shell) return;
    shell.querySelectorAll('[data-geo-summary]').forEach(node => {
      const key = node.dataset.geoSummary;
      const format = node.dataset.format || 'integer';
      node.textContent = fmt(payload.summary[key], format);
    });
    const unresolved = shell.querySelector('[data-geo-unresolved]');
    if (unresolved) {
      const n = payload.summary.unresolved || 0;
      const out = payload.outlier_attempts || 0;
      const parts = [];
      if (n) parts.push(`${n} sem localização suficiente`);
      if (out) parts.push(`+ ${out} fora da área principal`);
      unresolved.hidden = !parts.length;
      unresolved.textContent = parts.join(' · ');
      if (unresolved.tagName === 'BUTTON') {
        unresolved.disabled = !parts.length;
        unresolved.setAttribute('aria-label', parts.length ? `${parts.join('. ')}. Ver detalhes.` : 'Sem pendências geográficas');
      }
    }
  }

  function unresolvedDetail(root) {
    const payload = root._geoPayload;
    const shell = root.closest('.geo-shell');
    const detail = shell?.querySelector('[data-geo-detail]');
    if (!payload || !detail) return;
    const reasons = payload.summary?.unresolved_reasons || {};
    const labels = payload.unresolved_reason_labels || {};
    const entries = Object.entries(reasons).filter(([, count]) => Number(count || 0) > 0);
    const samples = (payload.unresolved_details || []).slice(0, 12);
    detail.hidden = false;
    detail.innerHTML = `
      <div class="geo-detail-head">
        <div><small>Diagnóstico geográfico</small><h3>Sem localização suficiente</h3></div>
        <button type="button" class="icon-btn" data-geo-detail-close aria-label="Fechar detalhes">×</button>
      </div>
      <p class="geo-detail-note">Os registros continuam válidos operacionalmente. Esta lista explica apenas por que eles não puderam ser posicionados no nível geográfico atual.</p>
      <div class="geo-unresolved-reasons">${entries.length ? entries.map(([key,count]) => `<div><span>${escapeHtml(labels[key] || key)}</span><b>${fmt(count,'integer')}</b></div>`).join('') : '<small class="muted">Nenhuma insuficiência de endereço identificada.</small>'}</div>
      ${samples.length ? `<div class="geo-unresolved-samples"><div class="geo-fallback-title">Amostra de registros</div>${samples.map(item => `<div><span><b>${escapeHtml(item.cte || 'CT-e não informado')}</b>${item.nf ? ` · NF ${escapeHtml(item.nf)}` : ''}</span><small>${escapeHtml(item.client || 'Cliente não informado')} · ${escapeHtml(item.city)} / ${escapeHtml(item.district)} · ${escapeHtml(labels[item.reason] || item.reason)}</small></div>`).join('')}</div>` : ''}`;
    detail.querySelector('[data-geo-detail-close]')?.addEventListener('click', () => { detail.hidden = true; });
  }

  function renderMapFallback(root, payload, error) {
    const chart = chartCache.get(root);
    if (chart) {
      try { chart.dispose(); } catch (_) {}
      chartCache.delete(root);
    }
    const compact = root.dataset.compact === '1';
    const regions = (payload.ranking?.length ? payload.ranking : payload.regions || []).filter(row => Number(row.attempts || 0) > 0);
    const limit = compact ? 4 : 12;
    const visible = regions.slice(0, limit);
    const title = payload.level === 'neighborhood' ? 'Bairros identificados no SSW' : 'Regiões identificadas no SSW';
    const explanation = payload.level === 'neighborhood'
      ? 'A fonte geográfica não retornou polígonos utilizáveis para este município. As entregas continuam disponíveis abaixo.'
      : 'A malha geográfica não pôde ser carregada. Os dados operacionais continuam disponíveis abaixo.';
    root.classList.add('geo-map-fallback-active');
    root.innerHTML = `<div class="geo-map-fallback ${compact ? 'compact' : ''}">
      <div class="geo-map-fallback-head"><span class="geo-fallback-icon">⌖</span><div><b>${escapeHtml(title)}</b><small>${escapeHtml(explanation)}</small></div></div>
      ${visible.length ? `<div class="geo-map-fallback-list">${visible.map(row => `<div class="geo-map-fallback-row"><span><b>${escapeHtml(row.name)}</b><small>${fmt(row.attempts,'integer')} tentativas · ${fmt(row.delivered,'integer')} entregas · ${fmt(row.retentions,'integer')} retenções</small></span><strong>${fmt(row.value,payload.metric.format)}</strong></div>`).join('')}</div>` : '<div class="geo-empty-small">Não há regiões resolvidas, mas os registros sem localização permanecem contabilizados no diagnóstico.</div>'}
      ${!compact && error ? `<small class="geo-fallback-error">Geometria: ${escapeHtml(error.message || String(error))}</small>` : ''}
    </div>`;
    showState(root, 'ready', '');
  }

  function renderLevel(root, payload) {
    const shell = root.closest('.geo-shell');
    if (!shell) return;
    shell.querySelectorAll('[data-geo-level-label]').forEach(n => n.textContent = payload.level === 'neighborhood' ? 'Bairros' : 'Municípios');
    const back = shell.querySelector('[data-geo-back]');
    if (back) {
      back.hidden = payload.level !== 'neighborhood';
      if (payload.level !== 'neighborhood') delete back.dataset.fallback;
    }
    renderBreadcrumb(root, payload);
  }

  function showState(root, type, message) {
    const state = root.parentElement?.querySelector('[data-geo-state]');
    if (!state) return;
    state.hidden = type === 'ready';
    state.dataset.state = type;
    if (type !== 'ready') {
      const heading = type === 'error' ? 'Mapa indisponível' : (type === 'empty' ? 'Sem cobertura no período' : 'Carregando mapa');
      state.innerHTML = `<span class="geo-state-${type}"><b>${heading}</b><small>${message}</small></span>`;
    }
  }

  async function loadPayload(root, overrides = {}) {
    const shell = root.closest('.geo-shell');
    const api = root.dataset.api;
    const form = shell?.querySelector('[data-geo-filters]');
    const params = new URLSearchParams();
    if (form) {
      new FormData(form).forEach((value, key) => { if (value !== '') params.set(key, value); });
    } else {
      for (const key of ['date', 'branch', 'metric', 'level', 'parent_state', 'parent_city']) {
        if (root.dataset[key]) params.set(key, root.dataset[key]);
      }
    }
    Object.entries(overrides).forEach(([k, v]) => {
      if (v === null || v === undefined || v === '') params.delete(k); else params.set(k, v);
    });
    const response = await fetch(`${api}?${params.toString()}`, {headers: {'X-Requested-With': 'XMLHttpRequest'}});
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || 'Falha ao carregar análise geográfica.');
    return payload;
  }

  async function draw(root, overrides = {}) {
    showState(root, 'loading', 'Preparando geometria e métricas da operação…');
    let payload;
    try {
      payload = await loadPayload(root, overrides);
    } catch (error) {
      showState(root, 'error', error.message || 'Não foi possível carregar os dados operacionais.');
      return;
    }

    root._geoPayload = payload;
    renderRanking(root, payload);
    renderAlerts(root, payload);
    renderSummary(root, payload);
    renderLevel(root, payload);
    renderLegend(root, payload);

    if (!payload.regions.length) {
      const chart = chartCache.get(root);
      if (chart) chart.clear();
      if (payload.summary?.unresolved) {
        renderMapFallback(root, payload, new Error('Os registros existem, mas não possuem localização suficiente para formar regiões.'));
      } else {
        showState(root, 'empty', 'Não há entregas localizadas para este período. Tente outro período ou filial.');
      }
      return;
    }

    let geometry;
    try {
      geometry = await loadGeometry(payload.geometry);
    } catch (error) {
      // Falha de GeoJSON nunca bloqueia a consulta operacional. Mantemos ranking,
      // métricas e uma lista navegável das regiões/bairros existentes no SSW.
      renderMapFallback(root, payload, error);
      return;
    }

    try {
      const visualRegions = payload.map_regions || payload.regions || [];
      const allowed = new Set(visualRegions.map(r => normalize(r.name)));
      if (payload.level === 'municipality' && allowed.size) {
        const selected = geometry.features.filter(feature => allowed.has(normalize(feature.properties && feature.properties.name)));
        if (selected.length) geometry = {type: 'FeatureCollection', features: selected};
      }
      const mapName = `geo-${payload.level}-${Date.now()}-${Math.random().toString(36).slice(2)}`;
      echarts.registerMap(mapName, geometry);
      let chart = chartCache.get(root);
      if (!chart) {
        root.classList.remove('geo-map-fallback-active');
        root.innerHTML = '';
        chart = echarts.init(root, null, {renderer: 'canvas'});
        chartCache.set(root, chart);
        chart.on('click', params => handleClick(root, params));
      }
      chart.setOption(chartOption(payload, geometry, mapName, root.dataset.compact === '1'), true);
      requestAnimationFrame(() => chart.resize());
      showState(root, 'ready', '');
    } catch (error) {
      renderMapFallback(root, payload, error);
    }
  }

  async function loadMunicipalityBreakdown(root, row, detail) {
    if (!detail) return;
    const target = detail.querySelector('[data-geo-municipality-breakdown]');
    if (!target) return;
    target.innerHTML = '<small class="muted">Carregando bairros/regiões identificados no SSW…</small>';
    try {
      const sub = await loadPayload(root, {
        level: 'neighborhood',
        parent_state: row.state || '',
        parent_city: row.city || row.name || '',
      });
      const regions = (sub.ranking || sub.regions || []).filter(x => x.attempts).slice(0, 10);
      if (!regions.length) {
        target.innerHTML = '<small class="muted">Não há bairros identificados para este município no período. O resumo municipal continua disponível.</small>';
        return;
      }
      target.innerHTML = `<div class="geo-fallback-title">Bairros/regiões identificados no SSW</div><small class="muted">Este município ainda não possui malha de bairros homologada. Os dados abaixo continuam navegáveis e usam a mesma métrica do mapa.</small><div class="geo-fallback-list">${regions.map(r => `<div><span>${r.name}</span><b>${fmt(r.value, sub.metric.format)}</b><small>${fmt(r.attempts,'integer')} tentativas · ${fmt(r.delivered,'integer')} entregas · ${fmt(r.retentions,'integer')} retenções · ${fmt(r.time_window_failures,'integer')} horário</small></div>`).join('')}</div>`;
      const rankBox = root.closest('.geo-shell')?.querySelector('[data-geo-ranking]');
      const rankTitle = rankBox?.closest('.panel')?.querySelector('[data-ranking-title]');
      if(rankBox){
        if(rankTitle)rankTitle.textContent=`Bairros/regiões de ${row.name}`;
        rankBox.innerHTML=regions.slice(0,5).map((r,i)=>`<div class="geo-rank-row"><span class="geo-rank-pos">${String(i+1).padStart(2,'0')}</span><span class="geo-rank-name">${r.name}<small>${fmt(r.attempts,'integer')} tentativas</small></span><span class="geo-rank-value">${fmt(r.value,sub.metric.format)}</span><span class="geo-rank-bar"><i style="width:${Math.max(4,(Number(r.value||0)/Math.max(...regions.map(x=>Number(x.value||0)),1))*100)}%"></i></span></div>`).join('');
      }
      const back=root.closest('.geo-shell')?.querySelector('[data-geo-back]');
      if(back){back.hidden=false;back.dataset.fallback='1';}
    } catch (error) {
      target.innerHTML = `<small class="muted">Não foi possível detalhar os bairros, mas os dados municipais acima permanecem válidos.</small>`;
    }
  }

  async function handleClick(root, params) {
    const payload = root._geoPayload;
    const row = params.data;
    if (!payload || !row || !row.attempts) return;
    const shell = root.closest('.geo-shell');
    const detail = shell?.querySelector('[data-geo-detail]');
    if (detail) {
      detail.hidden = false;
      detail.innerHTML = `
        <div class="geo-detail-head">
          <div><small>${payload.level === 'neighborhood' ? 'Bairro' : 'Município'}</small><h3>${row.name}</h3></div>
          <button type="button" class="icon-btn" data-geo-detail-close aria-label="Fechar detalhes">×</button>
        </div>
        <div class="geo-detail-lead"><span>${payload.metric.label}</span><b>${metricLead(payload, row)}</b></div>
        <div class="geo-detail-grid">
          <div><small>Tentativas</small><b>${fmt(row.attempts, 'integer')}</b></div>
          <div><small>Entregas</small><b>${fmt(row.delivered, 'integer')}</b></div>
          <div><small>Retenções</small><b>${fmt(row.retentions, 'integer')}</b></div>
          <div><small>Horário</small><b>${fmt(row.time_window_failures, 'integer')}</b></div>
          <div><small>Entregas limpas</small><b>${fmt(row.clean_deliveries, 'integer')}</b></div>
          <div><small>Sucesso</small><b>${fmt(row.success_rate, 'percent')}</b></div>
        </div>
        ${payload.level === 'municipality' && (!row.has_neighborhood_geometry || row.neighborhood_geometry_mode === 'dynamic') ? '<div class="geo-fallback-breakdown" data-geo-municipality-breakdown></div>' : ''}`;
      detail.querySelector('[data-geo-detail-close]')?.addEventListener('click', () => { detail.hidden = true; });
      if (payload.level === 'municipality' && (!row.has_neighborhood_geometry || row.neighborhood_geometry_mode === 'dynamic')) loadMunicipalityBreakdown(root, row, detail);
    }
    if (payload.level === 'municipality' && root.dataset.compact !== '1' && row.has_neighborhood_geometry) {
      const form = shell?.querySelector('[data-geo-filters]');
      if (form) {
        form.elements.level.value = 'neighborhood';
        form.elements.parent_state.value = row.state || '';
        form.elements.parent_city.value = row.city || '';
      }
      root.classList.add('geo-map-transitioning');
      await draw(root);
      window.setTimeout(() => root.classList.remove('geo-map-transitioning'), 260);
    }
  }

  function wire(root) {
    const shell = root.closest('.geo-shell');
    const form = shell?.querySelector('[data-geo-filters]');
    ensureMapChrome(root);
    if (form) {
      form.addEventListener('submit', e => { e.preventDefault(); draw(root); });
      form.querySelectorAll('select[data-live], input[data-live]').forEach(el => el.addEventListener('change', () => draw(root)));
    }
    shell?.querySelector('[data-geo-back]')?.addEventListener('click', () => {
      if (form) {
        form.elements.level.value = 'municipality';
        form.elements.parent_state.value = '';
        form.elements.parent_city.value = '';
      }
      const detail = shell?.querySelector('[data-geo-detail]');
      if (detail) detail.hidden = true;
      draw(root);
    });
    shell?.querySelector('[data-geo-unresolved]')?.addEventListener('click', () => unresolvedDetail(root));
    draw(root);
  }

  document.addEventListener('DOMContentLoaded', () => {
    if (typeof echarts === 'undefined') return;
    const maps = document.querySelectorAll('[data-geo-map]');
    maps.forEach(wire);
    window.addEventListener('resize', () => maps.forEach(root => chartCache.get(root)?.resize()));
  });
})();

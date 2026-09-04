const __painelCharts=new Set();
let __resizeTimer=null;
function registerPainelChart(chart){if(!chart)return chart;__painelCharts.add(chart);return chart;}
window.addEventListener('resize',()=>{clearTimeout(__resizeTimer);__resizeTimer=setTimeout(()=>{__painelCharts.forEach(chart=>{try{chart.resize();}catch(_e){__painelCharts.delete(chart);}});},180);});

document.addEventListener('DOMContentLoaded',()=>{
  if(window.lucide){lucide.createIcons();}
  setTimeout(()=>document.querySelectorAll('.toast').forEach(x=>x.remove()),5000);
  const sidebar=document.getElementById('app-sidebar');
  const toggle=document.querySelector('.mobile-nav-toggle');
  const close=document.querySelector('.sidebar-close');
  const backdrop=document.querySelector('.sidebar-backdrop');
  const setOpen=(open)=>{
    if(!sidebar)return;
    sidebar.classList.toggle('mobile-open',open);
    backdrop?.classList.toggle('visible',open);
    document.body.classList.toggle('nav-open',open);
    toggle?.setAttribute('aria-expanded',open?'true':'false');
  };
  toggle?.addEventListener('click',()=>setOpen(!sidebar?.classList.contains('mobile-open')));
  close?.addEventListener('click',()=>setOpen(false));
  backdrop?.addEventListener('click',()=>setOpen(false));
  sidebar?.querySelectorAll('a.nav-item').forEach(link=>link.addEventListener('click',()=>setOpen(false)));
  document.addEventListener('keydown',event=>{if(event.key==='Escape')setOpen(false);});
});
function darkAxis(){return{axisLabel:{color:'#94a3b8'},axisLine:{lineStyle:{color:'#1D3552'}},splitLine:{lineStyle:{color:'rgba(148,163,184,.10)'}}};}
window.initDashboard=async function({retention=0,evolution=null,evolution_url=''}){
  if(!window.echarts)return;
  const donut=document.getElementById('chart-donut');
  if(donut){const c=registerPainelChart(echarts.init(donut));c.setOption({tooltip:{trigger:'item',backgroundColor:'#081524',borderColor:'#1D3552',textStyle:{color:'#fff'}},series:[{type:'pie',radius:['58%','78%'],label:{show:false},data:[{value:Math.max(0,100-Number(retention)),name:'Liberado',itemStyle:{color:'#22c55e'}},{value:Number(retention),name:'Retido',itemStyle:{color:'#ef4444'}}]}]});}
  if(!evolution&&evolution_url){
    try{
      const response=await fetch(evolution_url,{headers:{'X-Requested-With':'XMLHttpRequest'},cache:'no-store'});
      if(response.ok)evolution=await response.json();
    }catch(_e){/* falha visual não bloqueia KPIs */}
  }
  const evo=document.getElementById('chart-evolution');
  if(!evo)return;
  if(!evolution){evo.innerHTML='<div class="empty-state">Não foi possível carregar a série. Atualize a página para tentar novamente.</div>';return;}
  evo.innerHTML='';
  evolution={labels:[],dates:[],entregas:[],retencoes:[],pendencias:[],detail_url:'/operacao/hoje/',...evolution};
  const c=registerPainelChart(echarts.init(evo));
  const many=(evolution.labels||[]).length>45;
  c.setOption({backgroundColor:'transparent',animation:!many,tooltip:{trigger:'axis',backgroundColor:'#081524',borderColor:'#1D3552',textStyle:{color:'#fff'}},legend:{top:0,textStyle:{color:'#94a3b8'}},grid:{left:45,right:20,top:45,bottom:many?62:35},dataZoom:many?[{type:'inside',filterMode:'none'},{type:'slider',height:18,bottom:7,start:Math.max(0,100-(45/Math.max(evolution.labels.length,45))*100),end:100}]:[],xAxis:{type:'category',data:evolution.labels,triggerEvent:true,boundaryGap:false,...darkAxis(),axisLabel:{color:'#94a3b8',hideOverlap:true,cursor:'pointer'}},yAxis:{type:'value',...darkAxis()},series:[{name:'Entregas',type:'line',smooth:.18,symbol:'circle',showSymbol:false,data:evolution.entregas},{name:'Retenções',type:'line',smooth:.18,symbol:'circle',showSymbol:false,data:evolution.retencoes},{name:'Pendências',type:'line',smooth:.18,symbol:'circle',showSymbol:false,data:evolution.pendencias}]});
  const openDaily=(selectedDate,focus='')=>{if(!selectedDate)return;const url=new URL(evolution.detail_url||'/operacao/hoje/',window.location.origin);url.searchParams.set('date',selectedDate);if(focus)url.searchParams.set('focus',focus);window.location.href=url.pathname+url.search;};
  c.on('click',params=>{if(params.componentType==='series'){const idx=Number(params.dataIndex);openDaily(evolution.dates?.[idx],{Entregas:'deliveries','Retenções':'retentions','Pendências':'proofs'}[params.seriesName]||'');}else if(params.componentType==='xAxis'){const idx=(evolution.labels||[]).indexOf(String(params.value??params.name??''));openDaily(evolution.dates?.[idx]||'');}});
  evo.style.cursor='pointer';
};
window.initDriverProfile=function(){if(!window.echarts)return;const parse=id=>JSON.parse(document.getElementById(id)?.textContent||'[]');const line=document.getElementById('driver-monthly');if(line){const c=registerPainelChart(echarts.init(line));c.setOption({tooltip:{trigger:'axis'},grid:{left:35,right:10,top:20,bottom:25},xAxis:{type:'category',data:parse('monthly-labels'),...darkAxis()},yAxis:{type:'value',...darkAxis()},series:[{type:'line',smooth:true,data:parse('monthly-values'),areaStyle:{color:'rgba(37,99,235,.14)'},lineStyle:{color:'#3b82f6',width:3},itemStyle:{color:'#60a5fa'}}]});}const occ=document.getElementById('driver-occurrences');if(occ){const labels=parse('occ-labels'),values=parse('occ-values');const c=registerPainelChart(echarts.init(occ));c.setOption({tooltip:{trigger:'item'},legend:{bottom:0,textStyle:{color:'#94a3b8'},type:'scroll'},series:[{type:'pie',radius:['45%','70%'],label:{show:false},data:labels.map((name,i)=>({name,value:values[i]}))}]});}const cli=document.getElementById('driver-clients');if(cli){const labels=parse('client-labels'),values=parse('client-values');const c=registerPainelChart(echarts.init(cli));c.setOption({grid:{left:120,right:15,top:15,bottom:20},xAxis:{type:'value',...darkAxis()},yAxis:{type:'category',data:labels.reverse(),axisLabel:{color:'#cbd5e1',width:110,overflow:'truncate'}},series:[{type:'bar',data:values.reverse(),itemStyle:{color:'#2563eb',borderRadius:[0,6,6,0]}}]});}};
window.initClients=function(){
  const city=document.getElementById('client-city-filter');
  const district=document.getElementById('client-district-filter');
  const optionNode=document.getElementById('client-district-options');
  let districtMap={};
  try{districtMap=JSON.parse(optionNode?.textContent||'{}')||{};}catch(_e){districtMap={};}
  const rebuildDistricts=()=>{
    if(!district)return;
    const selected=district.dataset.selected||district.value||'';
    const cityName=city?.value||'';
    const rows=cityName?(districtMap[cityName]||[]):Array.from(new Set(Object.values(districtMap).flat())).sort((a,b)=>String(a).localeCompare(String(b),'pt-BR'));
    district.innerHTML='<option value="">Todos</option>'+rows.map(name=>`<option value="${String(name).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;')}">${String(name)}</option>`).join('');
    if(rows.includes(selected))district.value=selected;else district.value='';
    district.dataset.selected=district.value;
  };
  city?.addEventListener('change',()=>{if(district)district.dataset.selected='';rebuildDistricts();});
  rebuildDistricts();
  if(!window.echarts)return;
  const el=document.getElementById('clients-retained-chart');
  const data=JSON.parse(document.getElementById('client-chart-data')?.textContent||'[]');
  if(el){const c=registerPainelChart(echarts.init(el));c.setOption({grid:{left:125,right:15,top:15,bottom:25},xAxis:{type:'value',...darkAxis()},yAxis:{type:'category',data:data.map(x=>x.name).reverse(),axisLabel:{color:'#cbd5e1',width:115,overflow:'truncate'}},series:[{type:'bar',data:data.map(x=>x.value).reverse(),itemStyle:{color:'#ef4444',borderRadius:[0,6,6,0]}}]});}
};


function initExpandableCharts(){
  const resizeTarget=id=>{
    const el=document.getElementById(id);
    if(!el||!window.echarts)return;
    const chart=echarts.getInstanceByDom(el);
    setTimeout(()=>{try{chart?.resize();}catch(_e){}},40);
    setTimeout(()=>{try{chart?.resize();}catch(_e){}},240);
  };
  document.querySelectorAll('[data-chart-fullscreen]').forEach(btn=>{
    btn.addEventListener('click',()=>{
      const id=btn.dataset.chartFullscreen;
      const panel=btn.closest('[data-chart-panel]');
      if(!panel)return;
      const expanded=panel.classList.toggle('chart-panel-fullscreen');
      document.body.classList.toggle('chart-expanded',expanded);
      const label=btn.querySelector('span');
      if(label)label.textContent=expanded?'Fechar':'Ampliar';
      resizeTarget(id);
    });
  });
  document.querySelectorAll('[data-chart-reset]').forEach(btn=>btn.addEventListener('click',()=>{
    const el=document.getElementById(btn.dataset.chartReset||'');
    const chart=el&&window.echarts?echarts.getInstanceByDom(el):null;
    try{chart?.dispatchAction({type:'dataZoom',start:0,end:100});}catch(_e){}
  }));
  document.addEventListener('keydown',event=>{
    if(event.key!=='Escape')return;
    const panel=document.querySelector('.chart-panel-fullscreen');
    if(!panel)return;
    panel.classList.remove('chart-panel-fullscreen');
    document.body.classList.remove('chart-expanded');
    const btn=panel.querySelector('[data-chart-fullscreen]');
    const label=btn?.querySelector('span');if(label)label.textContent='Ampliar';
    resizeTarget(panel.dataset.chartPanel||'');
  });
}
document.addEventListener('DOMContentLoaded',initExpandableCharts);

function initSswRoutineForms(){
  document.querySelectorAll('[data-routine-form]').forEach(form=>{
    const mode=form.querySelector('[data-routine-mode]');
    if(!mode)return;
    const render=()=>{
      const fixed=String(mode.value||'RECENT').toUpperCase()==='FIXED';
      form.querySelectorAll('[data-routine-fixed]').forEach(el=>el.hidden=!fixed);
      form.querySelectorAll('[data-routine-recent]').forEach(el=>el.hidden=fixed);
    };
    mode.addEventListener('change',render);render();
    form.querySelectorAll('[data-routine-close]').forEach(btn=>btn.addEventListener('click',()=>{const details=form.closest('details');if(details)details.open=false;}));
  });
  document.addEventListener('keydown',event=>{
    if(event.key!=='Escape')return;
    document.querySelectorAll('.ssw-routine-edit[open],.ssw-routine-new[open]').forEach(details=>{details.open=false;});
  });
}
document.addEventListener('DOMContentLoaded',initSswRoutineForms);

function initSswLiveImport(){
  const form=document.getElementById('ssw-upload-form');
  if(!form)return;
  const box=document.getElementById('ssw-import-live');
  const bar=document.getElementById('ssw-progress-bar');
  const percent=document.getElementById('ssw-progress-percent');
  const message=document.getElementById('ssw-progress-message');
  const status=document.getElementById('ssw-progress-status');
  const elapsed=document.getElementById('ssw-progress-elapsed');
  const fileLabel=document.getElementById('ssw-progress-file');
  const metricParse=document.getElementById('ssw-metric-parse');
  const metricNormalize=document.getElementById('ssw-metric-normalize');
  const metricPreload=document.getElementById('ssw-metric-preload');
  const metricCompare=document.getElementById('ssw-metric-compare');
  const metricDatabase=document.getElementById('ssw-metric-database');
  const submit=form.querySelector('button[type="submit"]');
  const fileInput=form.querySelector('input[type="file"]');
  let pollTimer=null, clockTimer=null, startedAt=null, serverProcessing=false;

  const fmtElapsed=()=>{
    if(!startedAt)return '00:00';
    const secs=Math.max(0,Math.floor((Date.now()-startedAt)/1000));
    const mm=String(Math.floor(secs/60)).padStart(2,'0');
    const ss=String(secs%60).padStart(2,'0');
    return `${mm}:${ss}`;
  };
  const fmtSeconds=value=>{const n=Number(value);return Number.isFinite(n)&&n>0?`${n.toFixed(n<1?3:2)}s`:'—';};
  const setProgress=(value,indeterminate=false)=>{
    const v=Math.max(0,Math.min(100,Number(value)||0));
    bar.style.width=`${v}%`;
    bar.classList.toggle('indeterminate',indeterminate);
    percent.textContent=indeterminate?'Processando':`${Math.round(v)}%`;
  };
  const stopTimers=()=>{
    if(pollTimer){clearInterval(pollTimer);pollTimer=null;}
    if(clockTimer){clearInterval(clockTimer);clockTimer=null;}
  };
  const poll=async()=>{
    try{
      const response=await fetch(form.dataset.progressUrl,{headers:{'X-Requested-With':'XMLHttpRequest'},cache:'no-store'});
      if(!response.ok)return;
      const data=await response.json();
      if(!data.run)return;
      const run=data.run;
      if(run.file)fileLabel.textContent=run.file;
      status.textContent=run.status_display||run.status||'Processando';
      if(metricParse)metricParse.textContent=fmtSeconds(run.parse_seconds);
      if(metricNormalize)metricNormalize.textContent=fmtSeconds(run.normalize_seconds);
      if(metricPreload)metricPreload.textContent=fmtSeconds(run.preload_seconds);
      if(metricCompare)metricCompare.textContent=fmtSeconds(run.compare_seconds);
      if(metricDatabase)metricDatabase.textContent=fmtSeconds(run.database_seconds);
      if(data.active){
        serverProcessing=true;
        const hasPercent=run.live_percent!==null&&run.live_percent!==undefined;
        setProgress(hasPercent?run.live_percent:100,!hasPercent);
        const count=(run.live_current!==null&&run.live_current!==undefined&&run.live_total)?` · ${run.live_current}/${run.live_total}`:'';
        message.textContent=`${run.live_phase||run.step||'Processamento'} — ${run.live_message||run.step_message||'Processando dados do SSW...'}${count}`;
      }else if(serverProcessing){
        setProgress(100,false);
        message.textContent=run.status==='ERROR'?'A importação terminou com erro. Atualizando a tela...':'Importação concluída. Atualizando indicadores...';
      }
    }catch(_error){/* O XHR principal continua sendo a fonte de verdade. */}
  };

  form.addEventListener('submit',event=>{
    if(!fileInput?.files?.length)return;
    event.preventDefault();
    stopTimers();
    startedAt=Date.now();
    serverProcessing=false;
    box.hidden=false;
    box.scrollIntoView({behavior:'smooth',block:'center'});
    submit.disabled=true;
    fileInput.disabled=true;
    status.textContent='Enviando';
    message.textContent='Enviando arquivo(s) para o servidor...';
    fileLabel.textContent=[...fileInput.files].map(f=>f.name).join(', ');
    setProgress(0,false);
    clockTimer=setInterval(()=>{elapsed.textContent=fmtElapsed();},500);

    const xhr=new XMLHttpRequest();
    xhr.open('POST',form.action||window.location.href,true);
    xhr.setRequestHeader('X-Requested-With','XMLHttpRequest');
    xhr.upload.addEventListener('progress',e=>{
      if(!e.lengthComputable)return;
      const value=(e.loaded/e.total)*100;
      setProgress(value,false);
      message.textContent=value<100?'Enviando arquivo(s) para o servidor...':'Upload concluído. Iniciando leitura e processamento do SSW...';
    });
    xhr.upload.addEventListener('load',()=>{
      status.textContent='Processando';
      message.textContent='Upload concluído. Validando e processando os dados do SSW...';
      setProgress(100,true);
      poll();
      pollTimer=setInterval(poll,1200);
    });
    xhr.addEventListener('load',()=>{
      stopTimers();
      elapsed.textContent=fmtElapsed();
      if(xhr.status>=200&&xhr.status<400){
        setProgress(100,false);
        status.textContent='Concluído';
        message.textContent='Processamento concluído. Atualizando o painel...';
        setTimeout(()=>window.location.reload(),350);
      }else{
        status.textContent='Erro';
        status.className='chip chip-red';
        message.textContent='A importação não foi concluída. Recarregue a página para ver os detalhes.';
        submit.disabled=false;
        fileInput.disabled=false;
      }
    });
    xhr.addEventListener('error',()=>{
      stopTimers();
      status.textContent='Erro de conexão';
      status.className='chip chip-red';
      message.textContent='A conexão com o servidor foi interrompida durante a importação.';
      submit.disabled=false;
      fileInput.disabled=false;
    });
    // O input precisa permanecer habilitado até o FormData ser construído.
    fileInput.disabled=false;
    const finalData=new FormData(form);
    fileInput.disabled=true;
    xhr.send(finalData);
  });
}

document.addEventListener('DOMContentLoaded',initSswLiveImport);

function initRobotRunLive(){
  const panel=document.getElementById('robot-run-live');
  if(!panel||panel.dataset.active!=='1')return;
  const url=panel.dataset.progressUrl;
  if(!url)return;
  const phaseEl=document.getElementById('robot-live-phase');
  const messageEl=document.getElementById('robot-live-message');
  const percentEl=document.getElementById('robot-live-percent');
  const bar=document.getElementById('robot-live-bar');
  let finished=false;
  const poll=async()=>{
    try{
      const response=await fetch(url,{headers:{'X-Requested-With':'XMLHttpRequest'},cache:'no-store'});
      if(!response.ok)return;
      const data=await response.json();
      if(!data.run)return;
      const r=data.run;
      const phase=r.live_phase||r.step||'Processando';
      const msg=r.live_message||r.step_message||r.message||'';
      const hasPercent=r.live_percent!==null&&r.live_percent!==undefined;
      if(phaseEl)phaseEl.textContent=phase;
      if(messageEl)messageEl.textContent=msg;
      if(percentEl)percentEl.textContent=hasPercent?`${Math.round(Number(r.live_percent)||0)}%`:'Processando';
      if(bar){
        bar.style.width=hasPercent?`${Math.max(0,Math.min(100,Number(r.live_percent)||0))}%`:'42%';
        bar.classList.toggle('indeterminate',!hasPercent);
      }
      if(!data.active&&!finished){
        finished=true;
        if(percentEl)percentEl.textContent=r.status==='ERROR'?'Erro':'100%';
        setTimeout(()=>window.location.reload(),650);
      }
    }catch(_error){/* execução continua no worker; tenta novamente no próximo polling */}
  };
  poll();
  setInterval(poll,1200);
}
document.addEventListener('DOMContentLoaded',initRobotRunLive);


function initSingleSubmitForms(){
  document.querySelectorAll('form[data-single-submit="1"]').forEach(form=>{
    let submitted=false;
    form.addEventListener('submit',event=>{
      if(submitted){
        event.preventDefault();
        return;
      }
      submitted=true;
      form.querySelectorAll('button[type="submit"],input[type="submit"]').forEach(button=>{
        button.disabled=true;
        button.setAttribute('aria-busy','true');
      });
    });
  });
}
document.addEventListener('DOMContentLoaded',initSingleSubmitForms);

function initCopyActions(){
  document.querySelectorAll('[data-copy-text]').forEach(btn=>{
    btn.addEventListener('click',async()=>{
      const text=btn.dataset.copyText||'';
      if(!text)return;
      try{await navigator.clipboard.writeText(text);const old=btn.innerHTML;btn.innerHTML='✓ Copiado';setTimeout(()=>btn.innerHTML=old,1400);}catch(_e){window.prompt('Copie o link:',text);}
    });
  });
}
document.addEventListener('DOMContentLoaded',initCopyActions);

function initWhatsAppCenter(){
  const root=document.querySelector('[data-whatsapp-center]');
  if(!root)return;
  const url=root.dataset.statusUrl;
  const title=root.querySelector('[data-whatsapp-status-title]');
  const message=root.querySelector('[data-whatsapp-status-message]');
  const icon=root.querySelector('[data-whatsapp-status-icon]');
  const browser=root.querySelector('[data-whatsapp-browser]');
  const waiting=root.querySelector('[data-whatsapp-waiting]');
  const currentUrl=root.querySelector('[data-whatsapp-url]');
  const pending=document.querySelector('[data-whatsapp-pending]');
  const startForm=root.querySelector('[data-whatsapp-start]');
  const stopForm=root.querySelector('[data-whatsapp-stop]');
  const loginArea=root.querySelector('[data-whatsapp-login-area]');
  const qrCard=root.querySelector('[data-whatsapp-qr-card]');
  const qrImg=root.querySelector('[data-whatsapp-qr-img]');
  const loginWait=root.querySelector('[data-whatsapp-login-wait]');
  const previewLink=root.querySelector('[data-whatsapp-preview-link]');
  const logLink=root.querySelector('[data-whatsapp-log-link]');
  const diagnosticLink=root.querySelector('[data-whatsapp-diagnostic-link]');
  if(!url)return;

  const titleFor=data=>{
    const status=String(data.status||'').toUpperCase();
    if(data.connected)return 'Conectado e pronto';
    if(status==='WAITING_QR')return 'Escaneie o QR Code';
    if(status==='LOADING_LOGIN')return 'Carregando WhatsApp Web';
    if(status==='STARTING')return 'Iniciando bot';
    if(status==='STOPPING')return 'Encerrando bot';
    if(status==='UNRESPONSIVE')return 'Bot sem resposta';
    if(status==='RECONNECTING')return 'Reconectando';
    if(status==='LOGGED_OUT')return 'Sessão desconectada';
    if(status==='ERROR')return 'Erro no bot';
    return data.process_alive?'Bot em execução':'Offline';
  };

  const render=data=>{
    const alive=Boolean(data.process_alive||data.online);
    const connected=alive&&Boolean(data.connected);
    const status=String(data.status||'').toUpperCase();
    const qr=alive&&!connected&&Boolean(data.qr_available);
    const showLogin=alive&&!connected&&status!=='STOPPING';

    if(title)title.textContent=titleFor(data);
    if(message)message.textContent=data.message||(alive?'Bot em execução.':'O Painel continua funcionando mesmo com o bot desligado.');
    if(browser)browser.textContent=`Motor: ${data.backend||'Baileys / Node.js'}`;
    if(waiting)waiting.textContent=data.waiting_seconds!==undefined&&alive&&!connected?`Aguardando há ${data.waiting_seconds}s`:'';
    if(currentUrl)currentUrl.textContent=data.account_name?`Conta: ${data.account_name}`:(data.account_jid?`Conta: ${String(data.account_jid).split('@')[0]}`:'');
    if(pending&&data.pending!==undefined)pending.textContent=String(data.pending);
    if(icon){
      icon.classList.remove('green','warning','red');
      icon.classList.add(connected?'green':(alive?'warning':'red'));
    }
    if(startForm)startForm.hidden=alive;
    if(stopForm)stopForm.hidden=!alive;
    if(loginArea)loginArea.hidden=!showLogin;
    if(qrCard)qrCard.hidden=!qr;
    if(loginWait)loginWait.hidden=!showLogin||qr;

    if(qrImg&&qr&&data.qr_url){
      const base=data.qr_url.split('?')[0];
      qrImg.src=`${base}?t=${Date.now()}`;
    }
    if(previewLink){
      previewLink.hidden=!Boolean(data.preview_url)&&!Boolean(data.preview_available);
      if(data.preview_url)previewLink.href=`${data.preview_url}?t=${Date.now()}`;
    }
    if(logLink){
      logLink.hidden=!Boolean(data.log_url);
      if(data.log_url)logLink.href=data.log_url;
    }
    if(diagnosticLink){
      diagnosticLink.hidden=!Boolean(data.diagnostic_url);
      if(data.diagnostic_url)diagnosticLink.href=data.diagnostic_url;
    }
  };

  const poll=async()=>{
    try{
      const response=await fetch(url,{headers:{'X-Requested-With':'XMLHttpRequest'},cache:'no-store'});
      if(response.ok)render(await response.json());
    }catch(_e){/* status visual é auxiliar; controles continuam disponíveis */}
  };
  poll();
  const timer=setInterval(poll,2000);
  window.addEventListener('beforeunload',()=>clearInterval(timer),{once:true});
}
document.addEventListener('DOMContentLoaded',initWhatsAppCenter);

function initConfirmActions(){
  document.querySelectorAll('[data-confirm]').forEach(el=>{
    if(el.dataset.confirmReady==='1')return;
    el.dataset.confirmReady='1';
    const message=el.dataset.confirm||'Confirmar esta ação?';
    if(el.tagName==='FORM')el.addEventListener('submit',event=>{if(!window.confirm(message))event.preventDefault();});
    else el.addEventListener('click',event=>{if(!window.confirm(message))event.preventDefault();});
  });
}
document.addEventListener('DOMContentLoaded',initConfirmActions);

function getCookie(name){const row=document.cookie.split('; ').find(x=>x.startsWith(name+'='));return row?decodeURIComponent(row.split('=').slice(1).join('=')):'';}
function initGlobalSswUpdate(){
  document.querySelectorAll('[data-ssw-update-now]').forEach(btn=>{
    if(btn.dataset.ready==='1')return;btn.dataset.ready='1';
    btn.addEventListener('click',async()=>{
      const status=document.querySelector('[data-ssw-inline-status]');const text=status?.querySelector('[data-ssw-inline-text]');
      btn.disabled=true;if(status)status.hidden=false;if(text)text.textContent='Solicitando atualização SSW…';
      try{
        const response=await fetch(btn.dataset.url,{method:'POST',headers:{'X-CSRFToken':getCookie('csrftoken'),'X-Requested-With':'XMLHttpRequest','Accept':'application/json'}});
        const data=await response.json().catch(()=>({}));
        if(!response.ok){throw new Error(data.error||data.message||'Falha ao solicitar atualização.');}
        if(text)text.textContent=`${data.status_display||'Na fila'} · acompanhando o robô sem sair desta tela…`;
        const progressUrl=data.progress_url||btn.dataset.progressUrl;let done=false;
        const poll=async()=>{if(done)return;try{const r=await fetch(progressUrl,{headers:{'X-Requested-With':'XMLHttpRequest'},cache:'no-store'});if(!r.ok)return;const p=await r.json();if(p.run){if(text)text.textContent=`${p.run.live_phase||p.run.step||p.run.status_display}: ${p.run.live_message||p.run.step_message||''}`;if(!p.active){done=true;if(text)text.textContent=p.run.status==='ERROR'?'Atualização terminou com erro.':'Atualização concluída. Atualizando os dados desta tela…';setTimeout(()=>window.location.reload(),700);}}}catch(_e){}};
        await poll();if(!done){const timer=setInterval(async()=>{await poll();if(done)clearInterval(timer);},1400);}
      }catch(err){if(text)text.textContent=err.message||'Falha ao solicitar atualização.';btn.disabled=false;}
    });
  });
}
document.addEventListener('DOMContentLoaded',initGlobalSswUpdate);

function initQualityReviewModal(){
  const modal=document.getElementById('quality-review-modal');
  if(!modal)return;
  const form=document.getElementById('quality-review-form');
  const visible=document.getElementById('quality-visible-reason');
  const internal=document.getElementById('quality-internal-note');
  const reopen=document.getElementById('quality-reopen-button');
  const fields={
    driver:document.getElementById('quality-modal-driver'),date:document.getElementById('quality-modal-date'),
    manifest:document.getElementById('quality-modal-manifest'),cte:document.getElementById('quality-modal-cte'),
    client:document.getElementById('quality-modal-client'),status:document.getElementById('quality-modal-status')
  };
  let opener=null;
  const close=()=>{
    modal.hidden=true;modal.setAttribute('aria-hidden','true');document.body.classList.remove('modal-open');
    opener?.focus();opener=null;
  };
  const open=btn=>{
    opener=btn;
    form.action=btn.dataset.reviewUrl||'';
    fields.driver.textContent=btn.dataset.driver||'—';fields.date.textContent=btn.dataset.date||'—';
    fields.manifest.textContent=btn.dataset.manifest||'—';fields.cte.textContent=btn.dataset.cte||'—';
    fields.client.textContent=btn.dataset.client||'—';fields.status.textContent=btn.dataset.statusLabel||'—';
    visible.value=btn.dataset.visibleReason||'';internal.value=btn.dataset.internalNote||'';
    reopen.hidden=(btn.dataset.status||'PENDING')==='PENDING';
    modal.hidden=false;modal.setAttribute('aria-hidden','false');document.body.classList.add('modal-open');
    setTimeout(()=>visible.focus(),20);
  };
  document.querySelectorAll('.js-quality-review').forEach(btn=>btn.addEventListener('click',()=>open(btn)));
  modal.querySelectorAll('[data-quality-close]').forEach(btn=>btn.addEventListener('click',close));
  document.addEventListener('keydown',event=>{if(event.key==='Escape'&&!modal.hidden)close();});
  form.addEventListener('submit',event=>{
    const submitter=event.submitter;
    if(submitter?.value==='responsible'&&!visible.value.trim()){
      event.preventDefault();visible.setCustomValidity('Informe o motivo visível ao motorista.');visible.reportValidity();visible.focus();
      return;
    }
    visible.setCustomValidity('');
    form.querySelectorAll('button[type="submit"]').forEach(btn=>btn.disabled=true);
  });
}
document.addEventListener('DOMContentLoaded',initQualityReviewModal);

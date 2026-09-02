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
window.initDashboard=function({retention=0,evolution={labels:[],dates:[],entregas:[],retencoes:[],pendencias:[],detail_url:'/operacao/hoje/'}}){
  if(!window.echarts)return;
  const evo=document.getElementById('chart-evolution');
  if(evo){
    const c=registerPainelChart(echarts.init(evo));
    c.setOption({backgroundColor:'transparent',tooltip:{trigger:'axis',backgroundColor:'#081524',borderColor:'#1D3552',textStyle:{color:'#F8FAFC'},extraCssText:'border-radius:10px;padding:10px 12px'},legend:{textStyle:{color:'#cbd5e1'},data:['Entregas','Retenções','Pendências']},grid:{left:38,right:15,top:45,bottom:34},xAxis:{type:'category',data:evolution.labels,triggerEvent:true,...darkAxis(),axisLabel:{color:'#94a3b8',hideOverlap:true,cursor:'pointer'}},yAxis:{type:'value',...darkAxis()},series:[{name:'Entregas',type:'line',smooth:true,symbol:'circle',showSymbol:true,symbolSize:8,data:evolution.entregas,lineStyle:{width:3,color:'#22c55e'},itemStyle:{color:'#22c55e'}},{name:'Retenções',type:'line',smooth:true,symbol:'circle',showSymbol:true,symbolSize:8,data:evolution.retencoes,lineStyle:{width:3,color:'#ef4444'},itemStyle:{color:'#ef4444'}},{name:'Pendências',type:'line',smooth:true,symbol:'circle',showSymbol:true,symbolSize:8,data:evolution.pendencias,lineStyle:{width:3,color:'#f59e0b'},itemStyle:{color:'#f59e0b'}}]});
    const openDaily=(selectedDate,focus='')=>{
      if(!selectedDate)return;
      const url=new URL(evolution.detail_url||'/operacao/hoje/',window.location.origin);
      url.searchParams.set('date',selectedDate);
      if(focus)url.searchParams.set('focus',focus);
      window.location.href=url.pathname+url.search;
    };
    c.on('click',params=>{
      if(params.componentType==='series'){
        const idx=Number(params.dataIndex);
        const selectedDate=evolution.dates?.[idx];
        const focus={Entregas:'deliveries','Retenções':'retentions','Pendências':'proofs'}[params.seriesName]||'';
        openDaily(selectedDate,focus);
        return;
      }
      // O usuário costuma clicar diretamente na DATA do eixo, não apenas na bolinha.
      // triggerEvent=true transforma o rótulo em um atalho para a Operação do Dia.
      if(params.componentType==='xAxis'){
        const label=String(params.value??params.name??'');
        const idx=(evolution.labels||[]).indexOf(label);
        openDaily(evolution.dates?.[idx]||'');
      }
    });
    evo.style.cursor='pointer';
  }
  const donut=document.getElementById('chart-donut');if(donut){const c=registerPainelChart(echarts.init(donut));c.setOption({tooltip:{trigger:'item',backgroundColor:'#081524',borderColor:'#1D3552',textStyle:{color:'#fff'}},series:[{type:'pie',radius:['58%','78%'],label:{show:false},data:[{value:Math.max(0,100-Number(retention)),name:'Liberado',itemStyle:{color:'#22c55e'}},{value:Number(retention),name:'Retido',itemStyle:{color:'#ef4444'}}]}]});}
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

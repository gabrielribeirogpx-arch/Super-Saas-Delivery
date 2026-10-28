(() => {
  'use strict';
  const config = window.FOMIZERO_CONFIG;
  const app = new URL(config.appOrigin);
  if (app.protocol !== 'https:') throw new Error('Invalid application origin');
  const allowedPlans = new Set(['essential', 'operation', 'pro']);
  const attributionKeys = ['utm_source','utm_medium','utm_campaign','utm_content','utm_term','fbclid'];
  const query = new URLSearchParams(location.search);
  document.querySelectorAll('[data-plan]').forEach(link => {
    const plan = link.dataset.plan;
    if (!allowedPlans.has(plan)) return;
    const target = new URL('/onboarding', app);
    target.searchParams.set('plan', plan);
    // Preserve campaign attribution without adding customer data or replacing SCK.
    attributionKeys.forEach(key => { const value = query.get(key); if (value && value.length <= 500) target.searchParams.set(key,value); });
    link.href = target.href;
  });
  document.querySelectorAll('[data-login]').forEach(link => {link.href = new URL('/entrar',app).href;});
  document.getElementById('year').textContent = new Date().getFullYear();

  document.querySelectorAll('a span, .float-arrow').forEach(el=>{if(el.textContent.trim()==='↗')el.innerHTML='<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 18 18 6M6 6h12v12"/></svg>';});
  const icons = {
    menu:'<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 8h6M9 12h6M9 16h4"/>',
    orders:'<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18M9 9v11M13 13h4M13 16h3"/>',
    kitchen:'<path d="M4 16h16M6 16v-3a6 6 0 0 1 12 0v3M12 5V3M3 20h18"/>',
    finance:'<rect x="3" y="5" width="18" height="15" rx="2"/><path d="M3 9h18M16 14h2M7 3v4M17 3v4"/>',
    stock:'<path d="m3 7 9-4 9 4v11l-9 4-9-4zM3 7l9 4 9-4M12 11v11M7 5l9 4"/>',
    growth:'<path d="M3 20h18M5 16l5-5 4 3 6-9M15 5h5v5"/>'
  };
  document.querySelectorAll('[data-icon]').forEach(el => {el.innerHTML = '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">'+icons[el.dataset.icon]+'</svg>';});

  const initialArt = document.getElementById('step-art').innerHTML;
  const steps = {
    cardapio:{label:'01 / CARDÁPIO DIGITAL',title:'Sua vitrine, pronta<br>para abrir o apetite.',description:'Organize produtos, categorias e preços em um cardápio digital com a identidade do seu restaurante. Confira a prévia antes de compartilhar com os clientes.',note:'Cardápio digital incluído nos três planos.',art:initialArt},
    pedidos:{label:'02 / PEDIDOS E COZINHA',title:'Cada pedido tem<br>seu próximo passo.',description:'Acompanhe os pedidos no painel e organize o preparo na tela da cozinha. Mantenha os detalhes da operação acessíveis para quem precisa executar.',note:'Pedidos e KDS incluídos nos três planos.',art:'<div class="kds-preview"><div class="kds-heading"><span>Fomizero</span><strong>KDS — Cozinha</strong><small>Acompanhe o preparo dos pedidos</small></div><div class="kds-board"><div><h4>PENDENTE <b>1</b></h4><p>Aguardando início</p><article><b>#025</b><small>Delivery</small><strong>1× Combo especial</strong><span>Iniciar preparo</span></article></div><div><h4>EM PREPARO <b>1</b></h4><p>Sendo preparado</p><article><b>#024</b><small>Delivery</small><strong>2× Burger da casa</strong><span>Marcar pronto</span></article></div><div><h4>PRONTO <b>1</b></h4><p>Finalizado na área</p><article><b>#022</b><small>Delivery</small><strong>1× Burger da casa</strong><span>Pronto para sair</span></article></div></div></div><span class="art-caption">Recriação ilustrativa do KDS · dados fictícios</span>'},
    entregas:{label:'03 / ÁREA DO ENTREGADOR',title:'Um acesso próprio.<br>Uma etapa mais clara.',description:'Cadastre sua equipe de entregas e dê a cada entregador seu próprio acesso. Nos planos Operação e Pro, conte também com acompanhamento de entregas após configurar a integração.',note:'Localização depende de conexão e permissões no aparelho.',art:'<div class="delivery-preview"><div class="driver-preview-brand"><img src="/assets/fomizero-logo.svg" alt="" width="95" height="27"><span>☰</span></div><div class="driver-greeting"><strong>Olá, Ana</strong><span>Pronto para as entregas de hoje?</span></div><div class="driver-preview-stats"><div><b>03</b><span>Disponíveis</span></div><div><b>02</b><span>Minhas entregas</span></div><div><b>01</b><span>Em andamento</span></div><div><b>08</b><span>Concluídas hoje</span></div></div><h4>MINHAS ENTREGAS</h4><div class="delivery-card"><div><b>Pedido #022</b><span>Em andamento</span></div><h5>Lucas A.</h5><p>Rua Exemplo, 123 · Centro</p><strong>Ver entrega →</strong></div><div class="driver-bottom"><span>⌂ Início</span><span>▤ Entregas</span></div></div><span class="art-caption">Recriação ilustrativa da área do entregador</span>'}
  };
  const tabs = [...document.querySelectorAll('[data-step]')];
  function setStep(tab) {
    tabs.forEach(item => {const selected = item === tab; item.setAttribute('aria-selected',String(selected));item.tabIndex = selected ? 0 : -1;});
    const data = steps[tab.dataset.step];
    document.getElementById('step-label').textContent = data.label;
    document.getElementById('step-title').innerHTML = data.title;
    document.getElementById('step-description').textContent = data.description;
    document.getElementById('step-note').textContent = data.note;
    document.getElementById('step-art').innerHTML = data.art;
    document.getElementById('demo-panel').setAttribute('aria-labelledby',tab.id);
  }
  tabs.forEach((tab,index) => {
    tab.addEventListener('click',() => setStep(tab));
    tab.addEventListener('keydown',event => {
      let next;
      if(event.key === 'ArrowRight') next = (index+1)%tabs.length;
      if(event.key === 'ArrowLeft') next = (index+tabs.length-1)%tabs.length;
      if(event.key === 'Home') next = 0;
      if(event.key === 'End') next = tabs.length-1;
      if(next !== undefined){event.preventDefault();setStep(tabs[next]);tabs[next].focus();}
    });
  });

  const choiceKey = 'fomizero:landing-measurement-consent:v2';
  const banner = document.getElementById('consent');
  const dialog = document.getElementById('privacy-dialog');
  let choice = null;
  try {const stored=JSON.parse(localStorage.getItem(choiceKey));if(stored && ['granted','denied'].includes(stored.value) && Date.now()-stored.at < 180*86400000) choice=stored.value;} catch {}
  let pixelStarted = false;
  let analyticsStarted = false;
  let analyticsReady = false;
  let analyticsConfigured = false;
  function activateAnalytics(measurementId) {
    if (!analyticsReady || choice !== 'granted') return;
    window.gtag('consent', 'update', {analytics_storage: 'granted'});
    if (!analyticsConfigured) {
      window.gtag('config', measurementId, {send_page_view: true});
      analyticsConfigured = true;
    }
  }
  function enableAnalytics() {
    const measurementId = config.ga4MeasurementId;
    if (choice !== 'granted' || !config.productionHosts.includes(location.hostname) || !/^G-[A-Z0-9]+$/.test(measurementId || '')) return;
    if (analyticsStarted) {
      activateAnalytics(measurementId);
      return;
    }
    analyticsStarted = true;
    window.dataLayer = window.dataLayer || [];
    window.gtag = function(){window.dataLayer.push(arguments);};
    window.gtag('js', new Date());
    window.gtag('consent', 'default', {analytics_storage: 'denied', ad_storage: 'denied', ad_user_data: 'denied', ad_personalization: 'denied'});
    const script = document.createElement('script');
    script.async = true;
    script.src = 'https://www.googletagmanager.com/gtag/js?id=' + encodeURIComponent(measurementId);
    script.onload = () => {
      analyticsReady = true;
      activateAnalytics(measurementId);
    };
    document.head.appendChild(script);
  }
  function enablePixel() {
    if (choice !== 'granted' || !config.productionHosts.includes(location.hostname) || !/^\d+$/.test(config.pixelId)) return;
    if (pixelStarted) {window.fbq('consent','grant');return;}
    pixelStarted = true;
    const fbq = window.fbq = function(){fbq.callMethod ? fbq.callMethod.apply(fbq,arguments) : fbq.queue.push(arguments);};
    if(!window._fbq)window._fbq=fbq;
    fbq.push=fbq;fbq.loaded=true;fbq.version='2.0';fbq.queue=[];
    fbq('consent','grant');fbq('init',config.pixelId);fbq('track','PageView');
    const script=document.createElement('script');script.async=true;script.src='https://connect.facebook.net/en_US/fbevents.js';document.head.appendChild(script);
  }
  function choose(value) {
    const previous=choice;choice=value;
    try{localStorage.setItem(choiceKey,JSON.stringify({value,at:Date.now()}));}catch{}
    banner.hidden=true;
    if(dialog.open)dialog.close();
    if(value==='granted' && previous!=='granted') {enablePixel();enableAnalytics();}
    if(value==='denied' && window.fbq) window.fbq('consent','revoke');
    if(value==='denied' && window.gtag) window.gtag('consent','update',{analytics_storage:'denied'});
  }
  document.querySelectorAll('[data-consent]').forEach(button => button.addEventListener('click',() => choose(button.dataset.consent)));
  document.querySelectorAll('[data-privacy]').forEach(button => button.addEventListener('click',() => {
    document.getElementById('consent-state').textContent=choice==='granted'?'Sua escolha atual: medição aceita.':choice==='denied'?'Sua escolha atual: medição recusada.':'Você ainda não escolheu.';
    dialog.showModal();
  }));
  document.getElementById('close-privacy').addEventListener('click',() => dialog.close());
  dialog.addEventListener('click',event => {if(event.target===dialog){const rect=dialog.getBoundingClientRect();if(event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom)dialog.close();}});
  if(choice===null)banner.hidden=false;
  if(choice==='granted'){enablePixel();enableAnalytics();}
  document.querySelectorAll('[data-plan]').forEach(link => link.addEventListener('click', () => {
    if (choice === 'granted' && window.fbq) window.fbq('trackCustom', 'PlanSelected', {plan: link.dataset.plan, placement: link.dataset.placement || 'plans'});
    if (choice === 'granted' && analyticsConfigured) window.gtag('event', 'plan_selected', {plan: link.dataset.plan, placement: link.dataset.placement || 'plans'});
  }));
  // PlanSelected/plan_selected record a plan click, not a checkout start or purchase.
  // Checkout and Purchase are measured in Hotmart, never inferred from this page.
})();

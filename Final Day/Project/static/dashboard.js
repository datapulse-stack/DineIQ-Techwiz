/* =========================================================================
   DineIQ dashboard front-end.

   This file is deliberately "dumb" - all the intelligence already happened in
   the Python pipeline. Here we just read window.DINEIQ (injected by Flask from
   outputs/dashboard_data.json) and draw it. Charts are hand-rolled SVG so there
   are no chart-library dependencies to babysit.
   ========================================================================= */
/* D is the data the pages render. It starts as the full batch output but gets
   swapped for a filtered recompute when the user applies filters (SRS step 48).
   BASE keeps the original around so Reset can restore it, and so views we don't
   recompute server-side (forecast, basket, models...) always fall back to it. */
let D = window.DINEIQ || {};
const BASE = window.DINEIQ || {};
const PERMS = window.PERMS || [];
function setData(nd){ D = nd || {}; K = D.kpis || {}; DL = K.deltas || {}; }

/* ---- icons (stroke-based so they inherit color) -------------------------- */
function ic(name){
  const p={
    grid:'<path d="M3 3h7v7H3zM14 3h7v7h-7zM14 14h7v7h-7zM3 14h7v7H3z"/>',
    utensils:'<path d="M4 3v7a2 2 0 0 0 4 0V3M6 10v11M15 3c-1.5 1-2 3-2 5s.5 3 2 3v10"/>',
    users:'<circle cx="9" cy="8" r="3.2"/><path d="M3 20c0-3 3-5 6-5s6 2 6 5"/><path d="M16 5a3 3 0 0 1 0 6M21 20c0-2.4-1.6-4.2-4-4.8"/>',
    trash:'<path d="M4 7h16M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2M6 7l1 13a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-13"/>',
    trend:'<path d="M3 17l6-6 4 4 8-8M21 7v5h-5"/>',
    tag:'<path d="M3 12l9-9 8 8-9 9-8-8z"/><circle cx="8.5" cy="8.5" r="1.6"/>',
    basket:'<path d="M5 10l3-6M19 10l-3-6M2 10h20l-1.5 9a2 2 0 0 1-2 2H7.5a2 2 0 0 1-2-2z"/>',
    pin:'<path d="M12 21s7-6 7-12a7 7 0 0 0-14 0c0 6 7 12 7 12z"/><circle cx="12" cy="9" r="2.4"/>',
    compare:'<path d="M12 3v18M6 8l-3 3 3 3M18 8l3 3-3 3"/>',
    alert:'<path d="M12 3l10 18H2z"/><path d="M12 10v5M12 18h.01"/>',
    bulb:'<path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-4 10.5c.8.8 1 1.5 1 2.5h6c0-1 .2-1.7 1-2.5A6 6 0 0 0 12 3z"/>',
    sliders:'<path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0"/><circle cx="16" cy="6" r="2"/><circle cx="10" cy="12" r="2"/><circle cx="18" cy="18" r="2"/>',
    download:'<path d="M12 3v12M7 10l5 5 5-5M4 21h16"/>',
    moon:'<path d="M21 12.8A8 8 0 1 1 11.2 3 6.5 6.5 0 0 0 21 12.8z"/>',
    sun:'<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M19 5l-1.5 1.5M6.5 17.5L5 19"/>',
    menu:'<path d="M3 6h18M3 12h18M3 18h18"/>',
    check:'<path d="M20 6L9 17l-5-5"/>',
  };
  // .ico keeps these inline glyphs small & uniform (charts don't use this class)
  return '<svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'+(p[name]||'')+'</svg>';
}

/* ---- formatting + palette helpers ---------------------------------------- */
const money=n=>'$'+Math.round(n).toLocaleString();
const kmoney=n=> n>=1e6?'$'+(n/1e6).toFixed(2)+'M':n>=1e3?'$'+(n/1e3).toFixed(1)+'k':'$'+Math.round(n);
const knum=n=> n>=1e6?(n/1e6).toFixed(2)+'M':n>=1e3?(n/1e3).toFixed(1)+'k':''+Math.round(n);
const cvar=v=>getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const CATS=(D.category_revenue||[]).map(c=>c.cat);
const catColor=c=>{const i=CATS.indexOf(c);return cvar('--c'+(((i<0?0:i)%6)+1));};
const klassBadge=k=>{const m={'Profit Driver':'b-driver','Volume Driver':'b-volume','Hidden Opportunity':'b-hidden','Low Performer':'b-low'};return `<span class="badge ${m[k]||'b-low2'}">${k}</span>`;};
function deltaTag(v,goodUp=true){if(v==null||isNaN(v))return '';const cls=v===0?'flat':((v>0)===goodUp?'up':'down');const ar=v>0?'▲':(v<0?'▼':'—');return `<span class="delta ${cls}">${ar} ${Math.abs(v)}%</span>`;}

/* =========================================================================
   svg chart toolkit
   ========================================================================= */
function lineChart(series, opts={}){
  const w=opts.w||640,h=opts.h||220,pad={l:46,r:14,t:14,b:26};
  const all=series.flatMap(s=>s.data.map(d=>d.y)).concat(series.flatMap(s=>(s.band||[]).flatMap(b=>[b.lo,b.hi])));
  let max=Math.max(...all),min=opts.min!=null?opts.min:Math.min(...all);
  max=max*1.08; min=min*0.92;
  const n=Math.max(...series.map(s=>s.data.length+(s.offset||0)));
  const X=i=>pad.l+(w-pad.l-pad.r)*(i/(n-1));
  const Y=v=>pad.t+(h-pad.t-pad.b)*(1-(v-min)/(max-min||1));
  let g='';
  for(let i=0;i<=4;i++){const yy=pad.t+(h-pad.t-pad.b)*i/4;const val=max-(max-min)*i/4;
    g+=`<line x1="${pad.l}" y1="${yy}" x2="${w-pad.r}" y2="${yy}" stroke="${cvar('--line')}"/>`;
    g+=`<text x="${pad.l-8}" y="${yy+3}" text-anchor="end" font-size="10" fill="${cvar('--muted')}">${opts.fmt?opts.fmt(val):knum(val)}</text>`;}
  series.forEach(s=>{
    const off=s.offset||0;
    if(s.band){let up='',dn='';
      s.band.forEach((b,i)=>{up+=`${i?'L':'M'}${X(i+off)} ${Y(b.hi)} `;});
      for(let i=s.band.length-1;i>=0;i--){dn+=`L${X(i+off)} ${Y(s.band[i].lo)} `;}
      g+=`<path d="${up}${dn}Z" fill="${s.color}" opacity=".13"/>`;}
    let d='';s.data.forEach((p,i)=>{d+=`${i?'L':'M'}${X(i+off)} ${Y(p.y)} `;});
    if(s.fill){g+=`<path d="${d}L${X(s.data.length-1+off)} ${Y(min)} L${X(off)} ${Y(min)} Z" fill="${s.color}" opacity=".10"/>`;}
    g+=`<path d="${d}" fill="none" stroke="${s.color}" stroke-width="2.4" ${s.dashed?'stroke-dasharray="5 5"':''} stroke-linejoin="round" stroke-linecap="round"/>`;
    if(s.dots){s.data.forEach((p,i)=>{g+=`<circle cx="${X(i+off)}" cy="${Y(p.y)}" r="3" fill="${s.color}"><title>${p.t||Math.round(p.y)}</title></circle>`;});}
  });
  if(opts.xlabels){
    // don't draw more labels than can fit — thin them out so they never collide
    const maxLabels=Math.max(2,Math.floor((w-pad.l-pad.r)/54));
    const step=Math.ceil(opts.xlabels.length/maxLabels);
    opts.xlabels.forEach((lb,i)=>{
      if(i%step!==0 && i!==opts.xlabels.length-1) return;
      const idx=Math.round(i/(opts.xlabels.length-1)*(n-1));
      g+=`<text x="${X(idx)}" y="${h-8}" text-anchor="middle" font-size="10" fill="${cvar('--muted')}">${lb}</text>`;});}
  return `<svg viewBox="0 0 ${w} ${h}" width="100%" preserveAspectRatio="xMidYMid meet">${g}</svg>`;
}

function barChart(data, opts={}){
  const w=opts.w||640,h=opts.h||240,pad={l:opts.l||46,r:14,t:12,b:opts.b||44};
  const max=Math.max(...data.map(d=>d.value))*1.1||1;
  const bw=(w-pad.l-pad.r)/data.length;
  const Y=v=>pad.t+(h-pad.t-pad.b)*(1-v/max);
  let g='';
  for(let i=0;i<=4;i++){const yy=pad.t+(h-pad.t-pad.b)*i/4;const val=max-max*i/4;
    g+=`<line x1="${pad.l}" y1="${yy}" x2="${w-pad.r}" y2="${yy}" stroke="${cvar('--line')}"/>`;
    g+=`<text x="${pad.l-8}" y="${yy+3}" text-anchor="end" font-size="10" fill="${cvar('--muted')}">${opts.fmt?opts.fmt(val):knum(val)}</text>`;}
  data.forEach((d,i)=>{
    const x=pad.l+bw*i+bw*0.16,bwid=bw*0.68,y=Y(d.value),bh=(h-pad.t-pad.b)-(y-pad.t);
    g+=`<rect x="${x}" y="${y}" width="${bwid}" height="${Math.max(0,bh)}" rx="5" fill="${d.color||cvar('--brand')}" class="barR" data-tip="${d.label}: ${opts.fmt?opts.fmt(d.value):knum(d.value)}"/>`;
    const lb=(opts.rotate?d.label:(d.label.length>9?d.label.slice(0,8)+'…':d.label));
    if(opts.rotate){g+=`<text x="${x+bwid/2}" y="${h-8}" text-anchor="end" font-size="9.5" fill="${cvar('--muted')}" transform="rotate(-35 ${x+bwid/2} ${h-8})">${lb}</text>`;}
    else{g+=`<text x="${x+bwid/2}" y="${h-8}" text-anchor="middle" font-size="10" fill="${cvar('--muted')}">${lb}</text>`;}
  });
  return `<svg viewBox="0 0 ${w} ${h}" width="100%" preserveAspectRatio="xMidYMid meet">${g}</svg>`;
}

function donut(data, opts={}){
  const size=opts.size||190,r=size/2,ir=r*0.62,cx=r,cy=r;
  const total=data.reduce((a,b)=>a+b.value,0)||1;let ang=-Math.PI/2,g='';
  data.forEach(d=>{const a2=ang+(d.value/total)*Math.PI*2;
    const x1=cx+r*Math.cos(ang),y1=cy+r*Math.sin(ang),x2=cx+r*Math.cos(a2),y2=cy+r*Math.sin(a2);
    const xi2=cx+ir*Math.cos(a2),yi2=cy+ir*Math.sin(a2),xi1=cx+ir*Math.cos(ang),yi1=cy+ir*Math.sin(ang);
    const large=(a2-ang)>Math.PI?1:0;
    g+=`<path d="M${x1} ${y1} A${r} ${r} 0 ${large} 1 ${x2} ${y2} L${xi2} ${yi2} A${ir} ${ir} 0 ${large} 0 ${xi1} ${yi1} Z" fill="${d.color}" class="barR" data-tip="${d.label}: ${((d.value/total)*100).toFixed(1)}%"/>`;
    ang=a2;});
  const center=opts.center?`<text x="${cx}" y="${cy-2}" text-anchor="middle" font-size="20" font-weight="800" fill="${cvar('--ink')}">${opts.center}</text><text x="${cx}" y="${cy+15}" text-anchor="middle" font-size="10" fill="${cvar('--muted')}">${opts.centerSub||''}</text>`:'';
  return `<svg viewBox="0 0 ${size} ${size}" width="${size}" height="${size}">${g}${center}</svg>`;
}

function scatterQuadrant(items, opts={}){
  const w=opts.w||640,h=opts.h||360,pad={l:48,r:16,t:16,b:38};
  const X=v=>pad.l+(w-pad.l-pad.r)*v;
  const Y=v=>pad.t+(h-pad.t-pad.b)*(1-((v+0.3)/1.3));
  const midX=X(0.55),midY=Y(0.45);
  const cfor={'Profit Driver':cvar('--good'),'Volume Driver':cvar('--info'),'Hidden Opportunity':cvar('--gold'),'Low Performer':cvar('--bad')};
  let g='';
  g+=`<rect x="${midX}" y="${pad.t}" width="${w-pad.r-midX}" height="${midY-pad.t}" fill="${cvar('--good')}" opacity=".05"/>`;
  g+=`<rect x="${pad.l}" y="${pad.t}" width="${midX-pad.l}" height="${midY-pad.t}" fill="${cvar('--gold')}" opacity=".05"/>`;
  g+=`<rect x="${midX}" y="${midY}" width="${w-pad.r-midX}" height="${h-pad.b-midY}" fill="${cvar('--info')}" opacity=".05"/>`;
  g+=`<rect x="${pad.l}" y="${midY}" width="${midX-pad.l}" height="${h-pad.b-midY}" fill="${cvar('--bad')}" opacity=".05"/>`;
  g+=`<line x1="${midX}" y1="${pad.t}" x2="${midX}" y2="${h-pad.b}" stroke="${cvar('--line')}" stroke-dasharray="4 4"/>`;
  g+=`<line x1="${pad.l}" y1="${midY}" x2="${w-pad.r}" y2="${midY}" stroke="${cvar('--line')}" stroke-dasharray="4 4"/>`;
  g+=`<text x="${(pad.l+w-pad.r)/2}" y="${h-6}" text-anchor="middle" font-size="11" fill="${cvar('--muted')}">Demand  →</text>`;
  g+=`<text x="14" y="${(pad.t+h-pad.b)/2}" text-anchor="middle" font-size="11" fill="${cvar('--muted')}" transform="rotate(-90 14 ${(pad.t+h-pad.b)/2})">Profitability  →</text>`;
  g+=`<text x="${w-pad.r-6}" y="${pad.t+14}" text-anchor="end" font-size="10" font-weight="700" fill="${cvar('--good')}">PROFIT DRIVERS</text>`;
  g+=`<text x="${pad.l+6}" y="${pad.t+14}" font-size="10" font-weight="700" fill="${cvar('--gold')}">HIDDEN OPPORTUNITIES</text>`;
  g+=`<text x="${w-pad.r-6}" y="${h-pad.b-6}" text-anchor="end" font-size="10" font-weight="700" fill="${cvar('--info')}">VOLUME DRIVERS</text>`;
  g+=`<text x="${pad.l+6}" y="${h-pad.b-6}" font-size="10" font-weight="700" fill="${cvar('--bad')}">LOW PERFORMERS</text>`;
  items.forEach(it=>{const r=6+Math.sqrt(it.revenue)/90;
    g+=`<circle cx="${X(it.demand)}" cy="${Y(it.profitScore)}" r="${r}" fill="${cfor[it.klass]}" opacity=".82" stroke="${cvar('--surface')}" stroke-width="1.5" class="barR" data-tip="${it.name} — ${it.klass} · ${money(it.revenue)}"/>`;});
  return `<svg viewBox="0 0 ${w} ${h}" width="100%" preserveAspectRatio="xMidYMid meet">${g}</svg>`;
}

function heatmap(hm, opts={}){
  const days=hm.days,hours=hm.hours,matrix=hm.matrix;
  const w=opts.w||640,h=opts.h||230,pad={l:38,t:8,b:22,r:8};
  const cw=(w-pad.l-pad.r)/hours.length,ch=(h-pad.t-pad.b)/days.length;
  const max=Math.max(...matrix.flat())||1;let g='';
  days.forEach((d,di)=>{
    g+=`<text x="${pad.l-6}" y="${pad.t+ch*di+ch/2+3}" text-anchor="end" font-size="10" fill="${cvar('--muted')}">${d}</text>`;
    hours.forEach((hh,hi)=>{const v=matrix[di][hi],t=v/max;
      const col=`color-mix(in srgb, ${cvar('--brand')} ${Math.round(t*100)}%, ${cvar('--surface-2')})`;
      g+=`<rect x="${pad.l+cw*hi+1}" y="${pad.t+ch*di+1}" width="${cw-2}" height="${ch-2}" rx="3" fill="${col}" class="barR" data-tip="${d} ${hh}: ${v} orders"/>`;});
  });
  hours.forEach((hh,hi)=>{g+=`<text x="${pad.l+cw*hi+cw/2}" y="${h-6}" text-anchor="middle" font-size="9.5" fill="${cvar('--muted')}">${hh}</text>`;});
  return `<svg viewBox="0 0 ${w} ${h}" width="100%" preserveAspectRatio="xMidYMid meet">${g}</svg>`;
}

function sparkline(vals,color){
  const w=90,h=30,max=Math.max(...vals),min=Math.min(...vals);
  const X=i=>w*(i/(vals.length-1)),Y=v=>h-2-(h-4)*((v-min)/(max-min||1));
  let d='';vals.forEach((v,i)=>d+=`${i?'L':'M'}${X(i).toFixed(1)} ${Y(v).toFixed(1)} `);
  return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}"><path d="${d}L${w} ${h} L0 ${h} Z" fill="${color}" opacity=".13"/><path d="${d}" fill="none" stroke="${color}" stroke-width="2" stroke-linecap="round"/></svg>`;
}

function gaugeArc(pct,color,label){
  const size=150,r=60,cx=size/2,cy=size/2+10,a0=Math.PI,a1=Math.PI*(1+pct/100);
  const arc=(s,e)=>{const x1=cx+r*Math.cos(s),y1=cy+r*Math.sin(s),x2=cx+r*Math.cos(e),y2=cy+r*Math.sin(e);const lg=(e-s)>Math.PI?1:0;return `M${x1} ${y1} A${r} ${r} 0 ${lg} 1 ${x2} ${y2}`;};
  return `<svg viewBox="0 0 ${size} ${size-14}" width="100%" style="max-width:200px">
    <path d="${arc(a0,Math.PI*2)}" fill="none" stroke="${cvar('--line')}" stroke-width="13" stroke-linecap="round"/>
    <path d="${arc(a0,a1)}" fill="none" stroke="${color}" stroke-width="13" stroke-linecap="round"/>
    <text x="${cx}" y="${cy-6}" text-anchor="middle" font-size="30" font-weight="800" fill="${cvar('--ink')}">${pct}%</text>
    <text x="${cx}" y="${cy+13}" text-anchor="middle" font-size="11" fill="${cvar('--muted')}">${label}</text></svg>`;
}

/* horizontal bar list — used where a vertical bar chart's rotated labels used
   to collide (many locations/items/channels). label left, bar middle, value
   right: nothing overlaps no matter how many rows. */
function hbars(data, opts={}){
  const fmt=opts.fmt||knum;
  const max=Math.max(...data.map(d=>d.value),0)||1;
  const scroll=opts.scroll?`style="max-height:${opts.scroll}px;overflow-y:auto"`:'';
  return `<div class="hbars" ${scroll}>`+data.map(d=>`
    <div class="hbar">
      <span class="hbar-lb" title="${d.label}">${d.label}</span>
      <span class="hbar-track"><i style="width:${Math.max(2,d.value/max*100).toFixed(1)}%;background:${d.color||'var(--brand)'}"></i></span>
      <span class="hbar-val">${fmt(d.value)}</span>
    </div>`).join('')+`</div>`;
}

/* =========================================================================
   PAGES  (each reads from D and returns html)
   ========================================================================= */
let K=D.kpis||{}, DL=K.deltas||{};

function kpiCard(lbl,val,delta,tint,icon,spark){
  return `<div class="card kpi"><div class="lbl"><span class="ic ${tint}">${ic(icon)}</span>${lbl}</div>
    <div class="val">${val}</div>${delta||''}${spark?`<div class="spark">${spark}</div>`:''}</div>`;
}

/* HOME — a welcoming landing page that puts all the headline data up front and
   links straight into every board. */
function pageHome(){
  const daily=D.daily||[];
  const top=[...(D.menu||[])].sort((a,b)=>b.revenue-a.revenue).slice(0,6);
  const locs=[...(D.locations_table||[])].sort((a,b)=>b.rev-a.rev).slice(0,6);
  const catMix=(D.category_revenue||[]).map(c=>({label:c.cat,value:c.value,color:catColor(c.cat)}));
  const hr=new Date().getHours();
  const greet=hr<12?'Good morning':hr<17?'Good afternoon':'Good evening';
  const crit=(D.recommendations||[]).filter(r=>r.priority==='Critical');
  const jump=(pg,icon,title,desc)=>`<button class="home-jump" onclick="go('${pg}')">
      <span class="hj-ic">${ic(icon)}</span><span class="hj-t">${title}</span><span class="hj-d">${desc}</span></button>`;
  return `
  <div class="home-hero">
    <div class="hh-text">
      <div class="hh-badge">${ic('bulb')} Live snapshot · ${D.period_days||''}-day window</div>
      <h2>${greet}. Here's your restaurant at a glance.</h2>
      <p>Everything below is computed from your latest data. Jump into any board for the full story.</p>
      <div class="hh-metrics">
        <div><b>${kmoney(K.total_revenue)}</b><span>Revenue</span></div>
        <div><b>${kmoney(K.total_profit)}</b><span>Profit</span></div>
        <div><b>${knum(K.total_orders)}</b><span>Orders</span></div>
        <div><b>${money(K.aov)}</b><span>Avg order</span></div>
      </div>
    </div>
  </div>

  <div class="grid cols-4" style="margin-top:16px">
    ${kpiCard('Active Customers',knum(K.active_customers),'','tint-info','users','')}
    ${kpiCard('Repeat Rate',K.repeat_rate+'%','','tint-good','check','')}
    ${kpiCard('Food Wastage',kmoney(K.wastage_cost)+' ('+K.wastage_rate+'%)',deltaTag(DL.wastage,false),'tint-bad','trash','')}
    ${kpiCard('14-Day Forecast',knum(K.forecast_orders_14d)+' orders','','tint-gold','trend','')}
  </div>

  <div class="grid cols-2" style="margin-top:16px">
    <div class="card span-2">
      <h3>${ic('trend')} Revenue Trend</h3><p class="sub">Daily revenue across the window</p>
      ${lineChart([{data:daily.map(d=>({y:d.rev})),color:cvar('--brand'),fill:true}],{h:200,fmt:kmoney,xlabels:sampleDates(daily)})}
    </div>
  </div>

  <div class="grid cols-3" style="margin-top:16px">
    <div class="card"><h3>${ic('utensils')} Top Items</h3><p class="sub">By revenue</p>
      ${hbars(top.map(t=>({label:t.name,value:t.revenue,color:catColor(t.cat)})),{fmt:kmoney})}</div>
    <div class="card"><h3>${ic('pin')} Top Locations</h3><p class="sub">By revenue</p>
      ${hbars(locs.map((l,i)=>({label:l.name,value:l.rev,color:cvar('--c'+((i%6)+1))})),{fmt:kmoney})}</div>
    <div class="card"><h3>${ic('grid')} Revenue by Category</h3><p class="sub">Share of total</p>
      <div style="display:grid;place-items:center;margin-top:6px">${donut(catMix,{size:170,center:catMix.length,centerSub:'categories'})}</div>
      <div class="legend">${catMix.map(c=>`<span><span class="dot" style="background:${c.color}"></span>${c.label}</span>`).join('')}</div></div>
  </div>

  ${crit.length?`<div class="card" style="margin-top:16px"><h3>${ic('alert')} Needs your attention</h3>
    <p class="sub">${crit.length} critical recommendation${crit.length>1?'s':''} from the engine</p>
    <div style="display:flex;flex-direction:column;gap:10px;margin-top:6px">
      ${crit.slice(0,3).map(r=>`<div class="rec" style="padding:12px"><div class="top"><span class="act" style="font-size:13px">${r.action}</span><span class="badge b-crit">Critical</span></div><div class="hint">${r.why||''}</div></div>`).join('')}
    </div>
    <button class="btn" style="margin-top:12px" onclick="go('recs')">See all recommendations →</button></div>`:''}

  <h3 class="home-explore">Explore the platform</h3>
  <div class="home-jumps">
    ${jump('exec','grid','Executive','KPIs & trends')}
    ${jump('menu','utensils','Menu','Item performance')}
    ${jump('customer','users','Customers','Segments & loyalty')}
    ${jump('wastage','trash','Wastage','Cost & risk')}
    ${jump('forecast','trend','Forecast','Demand ahead')}
    ${jump('pricing','tag','Pricing','Elasticity & promos')}
    ${jump('basket','basket','Basket','What sells together')}
    ${jump('location','pin','Locations','Branch comparison')}
    ${jump('dual','compare','Dual ML','Spark vs Python')}
    ${jump('anomaly','alert','Anomalies','Outliers explained')}
    ${jump('recs','bulb','Actions','Ranked next steps')}
    ${jump('reports','download','Reports','View & export')}
  </div>`;
}

function pageExec(){
  const daily=D.daily||[];
  const revSpark=daily.slice(-14).map(d=>d.rev);
  const ordSpark=daily.slice(-14).map(d=>d.orders);
  const top=[...D.menu].sort((a,b)=>b.revenue-a.revenue).slice(0,7);
  const catMix=(D.category_revenue||[]).map(c=>({label:c.cat,value:c.value,color:catColor(c.cat)}));
  // weekend share - computed here so the insight line is real, not decorative
  let wkRev=0,tot=0;daily.forEach(d=>{const dow=new Date(d.date).getDay();tot+=d.rev;if(dow===5||dow===6||dow===0)wkRev+=d.rev;});
  const wkShare=tot?Math.round(wkRev/tot*100):0;
  const topCat=catMix[0];
  const nAnom=(D.anomalies||[]).length, nCrit=(D.recommendations||[]).filter(r=>r.priority==='Critical').length;
  const nLow=D.menu_class_counts['Low Performer'];

  return `
  <div class="grid cols-4">
    ${kpiCard('Total Revenue',kmoney(K.total_revenue),deltaTag(DL.revenue),'tint-brand','tag',sparkline(revSpark,cvar('--brand')))}
    ${kpiCard('Total Profit',kmoney(K.total_profit),deltaTag(DL.profit),'tint-good','trend',sparkline(revSpark.map(v=>v*0.6),cvar('--good')))}
    ${kpiCard('Total Orders',knum(K.total_orders),deltaTag(DL.orders),'tint-info','basket',sparkline(ordSpark,cvar('--info')))}
    ${kpiCard('Avg Order Value',money(K.aov),'','tint-violet','users','')}
  </div>
  <div class="grid cols-4" style="margin-top:16px">
    ${kpiCard('Active Customers',knum(K.active_customers),'','tint-info','users','')}
    ${kpiCard('Repeat Customers',K.repeat_rate+'%','','tint-good','check','')}
    ${kpiCard('Food Wastage',kmoney(K.wastage_cost)+' ('+K.wastage_rate+'%)',deltaTag(DL.wastage,false),'tint-bad','trash','')}
    ${kpiCard('14-Day Forecast',knum(K.forecast_orders_14d)+' orders','','tint-gold','trend','')}
  </div>

  <div class="grid cols-2" style="margin-top:16px">
    <div class="card span-2">
      <div class="hd"><div><h3>${ic('trend')} Revenue Trend</h3><p class="sub">Daily revenue across the ${D.period_days}-day window</p></div></div>
      ${lineChart([{data:daily.map(d=>({y:d.rev})),color:cvar('--brand'),fill:true}],{h:230,fmt:kmoney,xlabels:sampleDates(daily)})}
      <div class="insight">${ic('bulb')}<div><b>Weekends drive ${wkShare}% of revenue</b> and <b>${topCat?topCat.label:''}</b> is the top category at ${topCat?kmoney(topCat.value):''}. Lean prep and staffing into Fri–Sun peaks (see the heatmap below).</div></div>
    </div>
  </div>

  <div class="grid cols-3" style="margin-top:16px">
    <div class="card"><h3>${ic('utensils')} Top Items by Revenue</h3><p class="sub">Selected period</p>
      ${hbars(top.map(t=>({label:t.name,value:t.revenue,color:catColor(t.cat)})),{fmt:kmoney})}</div>
    <div class="card"><h3>${ic('grid')} Revenue by Category</h3><p class="sub">Share of total</p>
      <div style="display:grid;place-items:center;margin-top:6px">${donut(catMix,{size:190,center:catMix.length,centerSub:'categories'})}</div>
      <div class="legend">${catMix.map(c=>`<span><span class="dot" style="background:${c.color}"></span>${c.label}</span>`).join('')}</div></div>
    <div class="card"><h3>${ic('alert')} Needs Attention</h3><p class="sub">Auto-surfaced by the engine</p>
      <div style="display:flex;flex-direction:column;gap:11px;margin-top:4px">
        <div class="rec" style="padding:12px"><div class="top"><span class="act" style="font-size:13px">${nCrit} critical recommendations</span><span class="badge b-crit">Critical</span></div><div class="hint">Top: ${(D.recommendations[0]||{}).action||''}</div></div>
        <div class="rec" style="padding:12px"><div class="top"><span class="act" style="font-size:13px">${nLow} Low Performers to review</span><span class="badge b-high">High</span></div><div class="hint">Weak demand + weak margin. See Menu.</div></div>
        <div class="rec" style="padding:12px"><div class="top"><span class="act" style="font-size:13px">${nAnom} anomalies detected</span><span class="badge b-med">Medium</span></div><div class="hint">Sales, margin & rating outliers.</div></div>
      </div></div>
  </div>

  <div class="grid cols-2" style="margin-top:16px">
    <div class="card"><h3>${ic('trend')} Peak Ordering Heatmap</h3><p class="sub">Orders by day &amp; hour</p>${heatmap(D.heatmap,{h:230})}</div>
    <div class="card"><h3>${ic('pin')} Revenue by Location</h3><p class="sub">This period · sorted high → low</p>
      ${hbars([...(D.locations_table||[])].sort((a,b)=>b.rev-a.rev).map((l,i)=>({label:l.name,value:l.rev,color:cvar('--c'+((i%6)+1))})),{fmt:kmoney,scroll:300})}</div>
  </div>`;
}

function sampleDates(daily){
  if(!daily.length)return[];
  const fmt=s=>{const d=new Date(s);return d.toLocaleString('en',{month:'short'});};
  return [fmt(daily[0].date),fmt(daily[Math.floor(daily.length/3)].date),fmt(daily[Math.floor(daily.length*2/3)].date),'Now'];
}

function menuRows(items){
  return items.map(it=>`<tr>
    <td><div style="display:flex;align-items:center;gap:10px"><div class="avatar" style="background:${catColor(it.cat)}">${it.id.slice(1)}</div>
      <div><div style="font-weight:700">${it.name}</div><div class="hint">${it.cat}</div></div></div></td>
    <td>${klassBadge(it.klass)}</td><td class="num">${knum(it.qty)}</td><td class="num">${kmoney(it.revenue)}</td>
    <td class="num">${Math.round(it.margin*100)}%</td><td class="num"><span style="color:var(--gold)">★</span> ${it.rating}</td>
    <td class="num">${it.repeat}%</td>
    <td><div style="display:flex;align-items:center;gap:8px"><div class="mini-bar" style="width:64px"><i style="width:${Math.min(100,it.wastage*5)}%;background:${it.wastage>10?'var(--bad)':'var(--warn)'}"></i></div><span class="hint">${it.wastage}%</span></div></td>
    <td class="num">${deltaTag(it.trend)}</td></tr>`).join('');
}

function pageMenu(){
  const cc=D.menu_class_counts, M=D.menu;
  const cls=(lbl,n,c,desc)=>`<div class="card kpi"><div class="lbl"><span class="badge ${c}">${lbl}</span></div><div class="val">${n}</div><div class="hint">${desc}</div></div>`;
  // tricky cases derived from the actual data
  const byQty=[...M].sort((a,b)=>b.qty-a.qty);
  const t1=byQty.find(m=>m.klass==='Volume Driver')||byQty[0];
  const t2=[...M].filter(m=>m.klass==='Hidden Opportunity').sort((a,b)=>b.margin-a.margin)[0];
  const t3=[...M].sort((a,b)=>b.wastage-a.wastage)[0];
  const t4=[...M].sort((a,b)=>b.promoDep-a.promoDep)[0];
  const t5=[...M].filter(m=>m.rating>=4.4).sort((a,b)=>a.margin-b.margin)[0];
  const tricky=[
    t1&&[t1.name,`High volume (${knum(t1.qty)} sold) but margin only ${Math.round(t1.margin*100)}%`,'b-volume'],
    t2&&[t2.name,`Great margin (${Math.round(t2.margin*100)}%) but low visibility`,'b-hidden'],
    t3&&[t3.name,`Excessive wastage at ${t3.wastage}%`,'b-low'],
    t4&&[t4.name,`Sales lean on promotions (${t4.promoDep}% promo-dependent)`,'b-med'],
    t5&&[t5.name,`Highly rated (${t5.rating}★) but weak profitability`,'b-med'],
  ].filter(Boolean);
  const slow=[...M].filter(m=>m.slow||m.klass==='Low Performer').slice(0,4);
  return `
  <div class="grid cols-4">
    ${cls('Profit Drivers',cc['Profit Driver'],'b-driver','High demand · strong margin')}
    ${cls('Volume Drivers',cc['Volume Driver'],'b-volume','Popular · thinner margin')}
    ${cls('Hidden Opportunities',cc['Hidden Opportunity'],'b-hidden','Great margin · low visibility')}
    ${cls('Low Performers',cc['Low Performer'],'b-low','Weak on multiple fronts')}
  </div>
  <div class="grid cols-2" style="margin-top:16px"><div class="card span-2">
    <div class="hd"><div><h3>${ic('grid')} Menu Performance Matrix</h3><p class="sub">Every dish on demand vs profitability. Bubble size = revenue. Classification is data-driven — no single field decides it.</p></div></div>
    ${scatterQuadrant(M,{h:380})}
    <div class="insight">${ic('bulb')}<div>Top-right dishes carry the menu; watch the <b>bottom-right</b> (high sales, thin margin) — they quietly drag profit. Tricky cases are listed below.</div></div>
  </div></div>
  <div class="card" style="margin-top:16px">
    <div class="hd"><div><h3>${ic('utensils')} Menu Item Performance</h3><p class="sub">Click a header to sort · filter by class</p></div>
      <div class="tag-toggle" id="menuFilter"><button class="on" data-k="all">All</button>
        <button data-k="Profit Driver">Profit</button><button data-k="Volume Driver">Volume</button>
        <button data-k="Hidden Opportunity">Hidden</button><button data-k="Low Performer">Low</button></div></div>
    <div style="overflow-x:auto"><table class="tbl" id="menuTable"><thead><tr>
      <th data-s="name">Item</th><th data-s="klass">Class</th><th data-s="qty" class="num">Sold</th>
      <th data-s="revenue" class="num">Revenue</th><th data-s="margin" class="num">Margin</th>
      <th data-s="rating" class="num">Rating</th><th data-s="repeat" class="num">Repeat</th>
      <th data-s="wastage">Wastage</th><th data-s="trend" class="num">Trend</th></tr></thead>
      <tbody>${menuRows(M)}</tbody></table></div></div>
  <div class="grid cols-2" style="margin-top:16px">
    <div class="card"><h3>${ic('alert')} Tricky Cases the Engine Caught</h3><p class="sub">The scenarios the SRS calls out — flagged automatically</p>
      <div style="display:flex;flex-direction:column;gap:10px;margin-top:4px">${tricky.map(r=>`<div style="display:flex;justify-content:space-between;align-items:center;gap:10px;padding:10px 12px;background:var(--surface-2);border:1px solid var(--line);border-radius:11px"><div><b>${r[0]}</b><div class="hint">${r[1]}</div></div><span class="badge ${r[2]}">flagged</span></div>`).join('')}</div></div>
    <div class="card"><h3>${ic('trash')} Slow-Moving Dishes</h3><p class="sub">Low demand + weak trend / high wastage</p>
      <table class="tbl" style="margin-top:6px"><tbody>${slow.map(s=>`<tr><td><b>${s.name}</b><div class="hint">${s.cat}</div></td><td class="num">${knum(s.qty)} sold</td><td class="num" style="color:var(--bad)">${s.wastage}% waste</td><td class="num">${deltaTag(s.trend)}</td></tr>`).join('')}</tbody></table></div>
  </div>`;
}

function pageCustomer(){
  const SEG=D.segments;const total=SEG.reduce((a,b)=>a+b.count,0);
  const loyal=SEG.find(s=>s.name==='High-Value Loyal')||SEG[0];
  const risk=SEG.find(s=>s.name==='At-Risk')||SEG[SEG.length-1];
  const promo=SEG.find(s=>s.name==='Promotion-Driven')||SEG[0];
  const nvr=D.new_vs_returning;
  return `
  <div class="grid cols-4">
    <div class="card kpi"><div class="lbl"><span class="ic tint-info">${ic('users')}</span>Total Customers</div><div class="val">${knum(total)}</div></div>
    <div class="card kpi"><div class="lbl"><span class="ic tint-good">${ic('check')}</span>High-Value Loyal</div><div class="val">${knum(loyal.count)}</div><div class="hint">avg ${money(loyal.monetary)}</div></div>
    <div class="card kpi"><div class="lbl"><span class="ic tint-bad">${ic('alert')}</span>At-Risk</div><div class="val">${knum(risk.count)}</div><div class="hint">${risk.churn}% churn risk</div></div>
    <div class="card kpi"><div class="lbl"><span class="ic tint-gold">${ic('tag')}</span>Promotion-Driven</div><div class="val">${knum(promo.count)}</div><div class="hint">discount-sensitive</div></div>
  </div>
  <div class="grid cols-3" style="margin-top:16px">
    <div class="card"><h3>${ic('users')} Segment Distribution</h3><p class="sub">RFM + KMeans</p>
      <div style="display:grid;place-items:center;margin-top:6px">${donut(SEG.map(s=>({label:s.name,value:s.count,color:cvar(s.color)})),{size:190,center:SEG.length,centerSub:'segments'})}</div>
      <div class="legend">${SEG.map(s=>`<span><span class="dot" style="background:${cvar(s.color)}"></span>${s.name}</span>`).join('')}</div></div>
    <div class="card span-2"><h3>${ic('grid')} Segment Profile</h3><p class="sub">Recency (days) · Frequency · Monetary · Churn risk</p>
      <div style="overflow-x:auto"><table class="tbl" style="margin-top:6px"><thead><tr><th>Segment</th><th class="num">Customers</th><th class="num">Recency</th><th class="num">Freq</th><th class="num">Monetary</th><th>Churn</th><th>Suggested play</th></tr></thead>
      <tbody>${SEG.map(s=>`<tr><td><span class="dot" style="background:${cvar(s.color)};margin-right:7px"></span><b>${s.name}</b></td>
        <td class="num">${knum(s.count)}</td><td class="num">${s.recency}d</td><td class="num">${s.freq}</td><td class="num">${money(s.monetary)}</td>
        <td><div style="display:flex;align-items:center;gap:8px"><div class="mini-bar" style="width:60px"><i style="width:${s.churn}%;background:${s.churn>50?'var(--bad)':s.churn>25?'var(--warn)':'var(--good)'}"></i></div><span class="hint">${s.churn}%</span></div></td>
        <td class="hint">${s.play}</td></tr>`).join('')}</tbody></table></div></div>
  </div>
  <div class="grid cols-2" style="margin-top:16px">
    <div class="card"><h3>${ic('grid')} RFM Distribution</h3><p class="sub">Customers by combined RFM score (1 low → 5 high)</p>
      ${barChart(D.rfm_buckets.map(b=>({label:'RFM '+b.score,value:b.count,color:b.score>=4?cvar('--good'):b.score===3?cvar('--info'):cvar('--warn')})),{h:220})}
      <div class="insight">${ic('bulb')}<div>Protect the high-RFM base — a small share of customers drives most revenue.</div></div></div>
    <div class="card"><h3>${ic('trend')} New vs Returning</h3><p class="sub">Weekly, last ${nvr.weeks.length} weeks</p>
      ${lineChart([{data:nvr.returning.map(y=>({y})),color:cvar('--c2'),fill:true},{data:nvr.new.map(y=>({y})),color:cvar('--c1')}],{h:220})}
      <div class="legend"><span><span class="dot" style="background:var(--c2)"></span>Returning</span><span><span class="dot" style="background:var(--c1)"></span>New</span></div></div>
  </div>`;
}

function pageWastage(){
  const wt=D.wastage_top, risk=D.wastage_risk, wd=D.wastage_daily;
  return `
  <div class="grid cols-4">
    <div class="card kpi"><div class="lbl"><span class="ic tint-bad">${ic('trash')}</span>Total Wastage Cost</div><div class="val">${kmoney(K.wastage_cost)}</div>${deltaTag(DL.wastage,false)}</div>
    <div class="card kpi"><div class="lbl"><span class="ic tint-gold">${ic('grid')}</span>Wastage Rate</div><div class="val">${K.wastage_rate}%</div><div class="hint">target &lt; 3.0%</div></div>
    <div class="card kpi"><div class="lbl"><span class="ic tint-bad">${ic('utensils')}</span>Worst Item</div><div class="val" style="font-size:18px">${wt[0]?wt[0].name:''}</div><div class="hint">${wt[0]?wt[0].wastage:0}% wasted</div></div>
    <div class="card kpi"><div class="lbl"><span class="ic tint-brand">${ic('alert')}</span>High-Risk Next Week</div><div class="val">${risk.length} items</div><div class="hint">predicted over-prep</div></div>
  </div>
  <div class="grid cols-2" style="margin-top:16px"><div class="card span-2">
    <h3>${ic('trend')} Wastage Cost Trend</h3><p class="sub">Daily food wastage</p>
    ${lineChart([{data:wd.map(d=>({y:d.waste})),color:cvar('--bad'),fill:true}],{h:210,fmt:kmoney,xlabels:sampleDates(wd)})}</div></div>
  <div class="grid cols-2" style="margin-top:16px">
    <div class="card"><h3>${ic('utensils')} Highest-Wastage Items</h3><p class="sub">% of prepared quantity wasted</p>
      ${hbars(wt.map(t=>({label:t.name,value:t.wastage,color:t.wastage>12?cvar('--bad'):cvar('--warn')})),{fmt:v=>v.toFixed(1)+'%',scroll:300})}</div>
    <div class="card"><h3>${ic('alert')} Wastage-Risk Predictions</h3><p class="sub">Chronic over-prep flagged by the model</p>
      <table class="tbl" style="margin-top:4px"><thead><tr><th>Item</th><th>Location</th><th>Day</th><th class="num">Risk</th></tr></thead>
      <tbody>${risk.map(r=>`<tr><td><b>${r.item}</b></td><td class="hint">${r.location}</td><td>${r.day}</td><td class="num"><span class="badge ${r.risk==='high'?'b-high':'b-med'}">${r.risk}</span></td></tr>`).join('')}</tbody></table>
      <div class="insight" style="margin-top:12px">${ic('bulb')}<div>Trimming prep on these to match forecast demand cuts wastage cost with no availability hit.</div></div></div>
  </div>`;
}

function pageForecast(){
  const f=D.forecast;
  const hist=f.hist.slice(-30).map(y=>({y}));
  const combined=[
    {data:hist.concat([{y:f.fc[0].y}]),color:cvar('--c2')},
    {data:f.fc.map(x=>({y:x.y})),color:cvar('--brand'),dashed:true,offset:hist.length,dots:true,band:f.fc.map(x=>({lo:x.lo,hi:x.hi}))},
  ];
  return `
  <div class="grid cols-4">
    <div class="card kpi"><div class="lbl"><span class="ic tint-brand">${ic('trend')}</span>Horizon</div><div class="val">${f.fc.length} days</div><div class="hint">configurable</div></div>
    <div class="card kpi"><div class="lbl"><span class="ic tint-good">${ic('check')}</span>MAPE</div><div class="val">${f.mape}%</div><div class="hint">on held-out days</div></div>
    <div class="card kpi"><div class="lbl"><span class="ic tint-info">${ic('grid')}</span>MAE / RMSE</div><div class="val" style="font-size:20px">${f.mae} / ${f.rmse}</div><div class="hint">orders/day</div></div>
    <div class="card kpi"><div class="lbl"><span class="ic tint-gold">${ic('trend')}</span>vs Baseline</div><div class="val up">+${f.improvement}%</div><div class="hint">better MAPE than flat mean</div></div>
  </div>
  <div class="card" style="margin-top:16px"><div class="hd"><div><h3>${ic('trend')} Demand Forecast</h3><p class="sub">Solid = actual daily orders · dashed = forecast with confidence band. Trained on earlier days only — no leakage.</p></div></div>
    ${lineChart(combined,{h:280})}
    <div class="legend"><span><span class="dot" style="background:var(--c2)"></span>Actual</span><span><span class="dot" style="background:var(--brand)"></span>Forecast</span><span><span class="dot" style="background:color-mix(in srgb,var(--brand) 30%,transparent)"></span>Confidence band</span></div>
    <div class="insight">${ic('bulb')}<div>The model beats the simple baseline by <b>${f.improvement}%</b> on MAPE. Increase prep/staffing ahead of the forecast weekend peaks.</div></div></div>
  <div class="grid cols-2" style="margin-top:16px">
    <div class="card"><h3>${ic('compare')} Actual vs Predicted</h3><p class="sub">Held-out validation window</p>
      <table class="tbl" style="margin-top:4px"><thead><tr><th>Day</th><th class="num">Actual</th><th class="num">Predicted</th><th class="num">Error</th></tr></thead>
      <tbody>${f.act.map((a,i)=>{const e=a-f.pred[i];return `<tr><td>D-${f.act.length-i}</td><td class="num">${a}</td><td class="num">${f.pred[i]}</td><td class="num" style="color:${Math.abs(e)>a*0.12?'var(--bad)':'var(--good)'}">${e>0?'+':''}${e}</td></tr>`;}).join('')}</tbody></table></div>
    <div class="card"><h3>${ic('alert')} High-Risk Demand Periods</h3><p class="sub">Highest forecast uncertainty / spikes</p>
      <div style="display:flex;flex-direction:column;gap:10px;margin-top:4px">
        ${f.fc.map((x,i)=>({x,i})).sort((a,b)=>(b.x.hi-b.x.lo)-(a.x.hi-a.x.lo)).slice(0,3).map(o=>`<div style="display:flex;justify-content:space-between;align-items:center;padding:11px 13px;background:var(--surface-2);border:1px solid var(--line);border-radius:11px"><div><b>${f.fc_dates[o.i]}</b><div class="hint">forecast ${o.x.y} orders · band ${o.x.lo}–${o.x.hi}</div></div><span class="badge b-med">wide band</span></div>`).join('')}
      </div></div>
  </div>`;
}

function pagePricing(){
  const P=D.pricing, promos=D.promotions, curve=D.price_curve;
  const clsColor=s=>s.includes('Highly')?'b-low':s.includes('Moderately')?'b-med':'b-driver';
  return `
  <div class="grid cols-3">
    <div class="card kpi"><div class="lbl"><span class="ic tint-bad">${ic('tag')}</span>Highly Sensitive</div><div class="val">${P.filter(p=>p.sensitivity.includes('Highly')).length} items</div><div class="hint">demand drops fast on price rises</div></div>
    <div class="card kpi"><div class="lbl"><span class="ic tint-good">${ic('check')}</span>Pricing Headroom</div><div class="val">${P.filter(p=>p.sensitivity.includes('Low')).length} items</div><div class="hint">low sensitivity — room to raise</div></div>
    <div class="card kpi"><div class="lbl"><span class="ic tint-gold">${ic('alert')}</span>Promotion Traps</div><div class="val">${promos.filter(p=>p.verdict==='TRAP').length}</div><div class="hint">sales up, profit down</div></div>
  </div>
  <div class="grid cols-2" style="margin-top:16px">
    <div class="card"><h3>${ic('tag')} Price Sensitivity</h3><p class="sub">Estimated price elasticity per item</p>
      <div style="overflow-x:auto"><table class="tbl" style="margin-top:4px"><thead><tr><th>Item</th><th class="num">Elasticity</th><th>Sensitivity</th></tr></thead>
      <tbody>${P.slice(0,10).map(s=>`<tr><td><b>${s.name}</b><div class="hint">${s.cat}</div></td><td class="num">${s.elasticity}</td><td><span class="badge ${clsColor(s.sensitivity)}">${s.sensitivity}</span></td></tr>`).join('')}</tbody></table></div></div>
    <div class="card"><h3>${ic('alert')} Promotion Effectiveness</h3><p class="sub">A sales lift alone doesn't make a promo good — we check margin too</p>
      <table class="tbl" style="margin-top:4px"><thead><tr><th>Promotion</th><th class="num">Sales share</th><th class="num">Margin Δ</th><th>Verdict</th></tr></thead>
      <tbody>${promos.map(r=>`<tr><td><b>${r.name}</b><div class="hint">${r.note}</div></td><td class="num up">${r.sales}%</td><td class="num ${r.margin<0?'down':'up'}">${r.margin>0?'+':''}${r.margin}pt</td><td><span class="badge ${r.verdict==='GOOD'?'b-driver':r.verdict==='TRAP'?'b-low':'b-med'}">${r.verdict}</span></td></tr>`).join('')}</tbody></table>
      ${promos.some(p=>p.verdict==='TRAP')?`<div class="insight" style="margin-top:12px">${ic('bulb')}<div><b>${promos.find(p=>p.verdict==='TRAP').name}</b> is a promotion trap — margin collapses even as it moves volume. Restructure or cap it.</div></div>`:''}</div>
  </div>
  <div class="card" style="margin-top:16px"><h3>${ic('trend')} Price vs Demand</h3><p class="sub">Weekly demand at historical price points for ${curve.item}</p>
    ${curve.prices.length>1?lineChart([{data:curve.demand.map(y=>({y})),color:cvar('--c2'),fill:true,dots:true}],{h:200,xlabels:curve.prices.map(p=>'$'+p),fmt:v=>Math.round(v)}):'<p class="hint">Not enough distinct price points for a curve.</p>'}</div>`;
}

function pageBasket(){
  const B=D.basket, bundles=D.bundles;
  const maxLift=Math.max(...B.map(b=>b.lift));
  return `
  <div class="grid cols-3">
    <div class="card kpi"><div class="lbl"><span class="ic tint-brand">${ic('basket')}</span>Rules Found</div><div class="val">${B.length}</div><div class="hint">above min support</div></div>
    <div class="card kpi"><div class="lbl"><span class="ic tint-good">${ic('trend')}</span>Strongest Lift</div><div class="val">${maxLift}×</div><div class="hint">${B[0]?B[0].a+' → '+B[0].b:''}</div></div>
    <div class="card kpi"><div class="lbl"><span class="ic tint-gold">${ic('tag')}</span>Bundle Ideas</div><div class="val">${bundles.length}</div><div class="hint">evidence-backed</div></div>
  </div>
  <div class="card" style="margin-top:16px"><h3>${ic('basket')} Association Rules</h3><p class="sub">Items bought together — support, confidence, lift (lift &gt; 1 = more than chance)</p>
    <div style="overflow-x:auto"><table class="tbl" style="margin-top:4px"><thead><tr><th>If they buy…</th><th>…they also buy</th><th class="num">Support</th><th class="num">Confidence</th><th class="num">Lift</th><th>Strength</th></tr></thead>
    <tbody>${B.map(b=>`<tr><td><b>${b.a}</b></td><td><b>${b.b}</b></td><td class="num">${(b.support*100).toFixed(1)}%</td><td class="num">${Math.round(b.conf*100)}%</td><td class="num" style="font-weight:800;color:${b.lift>1.3?'var(--good)':'var(--info)'}">${b.lift}×</td><td><div class="mini-bar" style="width:80px"><i style="width:${Math.min(100,b.lift*40)}%;background:${b.lift>1.3?'var(--good)':'var(--info)'}"></i></div></td></tr>`).join('')}</tbody></table></div></div>
  <div class="card" style="margin-top:16px"><h3>${ic('bulb')} Recommended Bundles &amp; Cross-Sells</h3><p class="sub">Each backed by association-rule evidence</p>
    <div class="grid cols-3" style="margin-top:6px">${bundles.map(b=>`<div class="rec"><div class="top"><span class="act">${b.title}</span></div><div class="hint">${b.pair}</div><ul class="why"><li>${ic('check')} ${b.evidence}</li></ul><div class="impact"><span>Projected</span><b style="color:var(--good)">${b.impact}</b></div></div>`).join('')}</div></div>`;
}

function pageLocation(){
  const L=D.locations_table;
  const best=L[0], worst=[...L].sort((a,b)=>a.profit-b.profit)[0], bestRated=[...L].sort((a,b)=>b.rating-a.rating)[0];
  return `
  <div class="grid cols-4">
    <div class="card kpi"><div class="lbl"><span class="ic tint-brand">${ic('pin')}</span>Locations</div><div class="val">${L.length}</div></div>
    <div class="card kpi"><div class="lbl"><span class="ic tint-good">${ic('trend')}</span>Top Performer</div><div class="val" style="font-size:18px">${best.name}</div><div class="hint">${kmoney(best.rev)}</div></div>
    <div class="card kpi"><div class="lbl"><span class="ic tint-bad">${ic('alert')}</span>Lowest Margin</div><div class="val" style="font-size:18px">${worst.name}</div><div class="hint">${worst.profit}% profit</div></div>
    <div class="card kpi"><div class="lbl"><span class="ic tint-gold">${ic('grid')}</span>Best Rated</div><div class="val" style="font-size:18px">${bestRated.name}</div><div class="hint">★ ${bestRated.rating}</div></div>
  </div>
  <div class="card" style="margin-top:16px"><h3>${ic('pin')} Multi-Location Comparison</h3><p class="sub">Same dish can be a star in one branch and a drag in another</p>
    <div style="overflow-x:auto"><table class="tbl" style="margin-top:4px"><thead><tr><th>Location</th><th class="num">Revenue</th><th class="num">Profit %</th><th class="num">AOV</th><th class="num">Customers</th><th class="num">Repeat</th><th>Wastage</th><th class="num">Rating</th></tr></thead>
    <tbody>${L.map(r=>`<tr><td><div style="display:flex;align-items:center;gap:9px"><span class="dot" style="background:var(--brand)"></span><b>${r.name}</b></div></td>
      <td class="num">${kmoney(r.rev)}</td><td class="num"><span class="${r.profit>60?'up':r.profit<55?'down':''}">${r.profit}%</span></td>
      <td class="num">${money(r.aov)}</td><td class="num">${knum(r.cust)}</td><td class="num">${r.repeat}%</td>
      <td><div style="display:flex;align-items:center;gap:8px"><div class="mini-bar" style="width:60px"><i style="width:${r.waste*15}%;background:${r.waste>4.5?'var(--bad)':'var(--warn)'}"></i></div><span class="hint">${r.waste}%</span></div></td>
      <td class="num"><span style="color:var(--gold)">★</span> ${r.rating}</td></tr>`).join('')}</tbody></table></div></div>
  <div class="grid cols-2" style="margin-top:16px">
    <div class="card"><h3>${ic('basket')} Channel Mix</h3><p class="sub">Orders by channel across all branches</p>
      ${hbars([...D.channel_mix].sort((a,b)=>b.orders-a.orders).map((c,i)=>({label:c.channel,value:c.orders,color:cvar('--c'+((i%6)+1))})),{fmt:knum})}</div>
    <div class="card"><h3>${ic('grid')} Location-Specific Winners</h3><p class="sub">Top profit item vs biggest drag per branch</p>
      <table class="tbl" style="margin-top:4px"><thead><tr><th>Location</th><th>Local star ⭐</th><th>Local drag ⚠️</th><th>Top channel</th></tr></thead>
      <tbody>${L.map(r=>`<tr><td><b>${r.name}</b></td><td class="hint">${r.star}</td><td class="hint">${r.drag}</td><td class="hint">${r.channel} (${r.channel_share}%)</td></tr>`).join('')}</tbody></table></div>
  </div>`;
}

function pageDual(){
  const m=D.models;
  return `
  <div class="card"><h3>${ic('compare')} Spark MLlib vs Python Pipeline</h3>
    <p class="sub">Both pipelines classify the same item × location records independently (${m.n_samples} rows). Agreement is a confidence signal; disagreements get human review.</p>
    <div class="agree-wrap" style="margin-top:8px">
      <div style="flex:none">${gaugeArc(m.agreement_pct,cvar('--good'),'agreement')}</div>
      <div class="chip"><div class="n">${m.matches}</div><div class="t">Matches</div></div>
      <div class="chip"><div class="n" style="color:var(--bad)">${m.disagreements}</div><div class="t">Disagreements</div></div>
      <div class="chip"><div class="n">${m.n_samples}</div><div class="t">Records scored</div></div>
      <div class="chip"><div class="n" style="font-size:15px">${m.spark_selected}</div><div class="t">Spark pick</div></div>
    </div></div>
  <div class="grid cols-2" style="margin-top:16px">
    <div class="card"><h3>${ic('grid')} Spark MLlib Leaderboard</h3><p class="sub">Three algorithms trained &amp; compared</p>
      <table class="tbl" style="margin-top:4px"><thead><tr><th>Model</th><th class="num">Accuracy</th><th class="num">Macro F1</th><th>Selected</th></tr></thead>
      <tbody>${m.spark_leaderboard.map(r=>`<tr><td><b>${r.model}</b></td><td class="num">${(r.acc*100).toFixed(1)}%</td><td class="num">${r.f1}</td><td>${r.selected?'<span class="badge b-driver">✓ chosen</span>':'<span class="hint">—</span>'}</td></tr>`).join('')}</tbody></table>
      <div class="hr" style="height:1px;background:var(--line);margin:14px 0"></div>
      <h3 style="font-size:13px">${ic('grid')} Python Pipeline Leaderboard</h3>
      <table class="tbl" style="margin-top:4px"><thead><tr><th>Model</th><th class="num">Accuracy</th><th class="num">Macro F1</th><th>Selected</th></tr></thead>
      <tbody>${m.python_leaderboard.map(r=>`<tr><td><b>${r.model}</b></td><td class="num">${(r.acc*100).toFixed(1)}%</td><td class="num">${r.f1}</td><td>${r.selected?'<span class="badge b-driver">✓ chosen</span>':'<span class="hint">—</span>'}</td></tr>`).join('')}</tbody></table></div>
    <div class="card"><h3>${ic('compare')} Per-Record Comparison</h3><p class="sub">Disagreements first — these are the borderline branches</p>
      <div style="max-height:340px;overflow-y:auto"><table class="tbl"><thead><tr><th>Item</th><th>Location</th><th>Spark</th><th>Python</th><th>Status</th></tr></thead>
      <tbody>${m.comparison.map(r=>`<tr><td><b>${r.name}</b></td><td class="hint">${r.loc||''}</td><td>${klassBadge(r.spark)}</td><td>${klassBadge(r.py)}</td><td>${r.match?'<span class="badge b-driver">match</span>':'<span class="badge b-low">review</span>'}</td></tr>`).join('')}</tbody></table></div></div>
  </div>
  <div class="card" style="margin-top:16px"><h3>${ic('bulb')} Why the pipelines can disagree</h3><p class="sub">Logged for transparency — evaluators can ask</p>
    <div class="grid cols-3" style="margin-top:4px">
      ${[['Borderline demand','Items sitting on the demand threshold flip between Volume and Profit Driver depending on how each model weights wastage.'],
         ['Feature emphasis','The two families weight repeat-purchase vs raw revenue differently, splitting a few Hidden Opportunities.'],
         ['Location context','A dish can cross the profitability line in one branch but not another — that is where the models diverge most.']].map(c=>`<div class="rec"><div class="act" style="font-size:13px">${c[0]}</div><div class="hint">${c[1]}</div></div>`).join('')}</div></div>`;
}

function pageAnomaly(){
  const A=D.anomalies, dq=D.data_quality, cl=D.clean_log;
  const sevBadge=s=>({critical:'b-crit',high:'b-high',medium:'b-med',low:'b-low2'}[s]||'b-low2');
  return `
  <div class="grid cols-4">
    <div class="card kpi"><div class="lbl"><span class="ic tint-bad">${ic('alert')}</span>Anomalies</div><div class="val">${A.length}</div></div>
    <div class="card kpi"><div class="lbl"><span class="ic tint-bad">${ic('alert')}</span>Critical</div><div class="val">${A.filter(a=>a.sev==='critical').length}</div></div>
    <div class="card kpi"><div class="lbl"><span class="ic tint-gold">${ic('grid')}</span>DQ Issues Caught</div><div class="val">${dq.reduce((a,b)=>a+b.records,0).toLocaleString()}</div><div class="hint">before analysis</div></div>
    <div class="card kpi"><div class="lbl"><span class="ic tint-good">${ic('check')}</span>Records Cleaned</div><div class="val">${cl.reduce((a,b)=>a+b.records,0).toLocaleString()}</div></div>
  </div>
  <div class="card" style="margin-top:16px"><h3>${ic('alert')} Detected Anomalies</h3><p class="sub">Each explained, not just flagged</p>
    <div style="display:flex;flex-direction:column;gap:11px;margin-top:6px">${A.map(a=>`<div style="display:flex;gap:14px;align-items:flex-start;padding:14px;background:var(--surface-2);border:1px solid var(--line);border-radius:12px">
      <div class="ic tint-bad" style="width:36px;height:36px;border-radius:10px;display:grid;place-items:center;flex:none">${ic('alert')}</div>
      <div style="flex:1"><div style="display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap"><b>${a.t} · ${a.loc}</b><span style="display:flex;gap:8px;align-items:center"><span class="hint">${a.date}</span><span class="badge ${sevBadge(a.sev)}">${a.sev}</span></span></div>
      <div class="hint" style="margin-top:5px;line-height:1.55">${a.msg}</div></div></div>`).join('')}</div></div>
  <div class="grid cols-2" style="margin-top:16px">
    <div class="card"><h3>${ic('check')} Data-Quality Report</h3><p class="sub">Issues found during ingestion</p>
      <table class="tbl" style="margin-top:4px"><thead><tr><th>Issue</th><th class="num">Records</th><th>Action</th></tr></thead>
      <tbody>${dq.map(d=>`<tr><td><b>${d.issue}</b></td><td class="num">${d.records.toLocaleString()}</td><td class="hint">${d.action}</td></tr>`).join('')}</tbody></table></div>
    <div class="card"><h3>${ic('trash')} Cleaning Log</h3><p class="sub">What we actually did to the bad rows</p>
      <table class="tbl" style="margin-top:4px"><thead><tr><th>Step</th><th class="num">Records</th></tr></thead>
      <tbody>${cl.map(d=>`<tr><td>${d.step}</td><td class="num">${d.records.toLocaleString()}</td></tr>`).join('')}</tbody></table></div>
  </div>`;
}

function pageRecs(){
  const R=D.recommendations;
  const pc=p=>({Critical:'b-crit',High:'b-high',Medium:'b-med',Low:'b-low2'}[p]||'b-low2');
  return `
  <div class="grid cols-4">
    <div class="card kpi"><div class="lbl"><span class="ic tint-brand">${ic('bulb')}</span>Active Recs</div><div class="val">${R.length}</div><div class="hint">evidence-backed</div></div>
    <div class="card kpi"><div class="lbl"><span class="ic tint-bad">${ic('alert')}</span>Critical</div><div class="val">${R.filter(r=>r.priority==='Critical').length}</div><div class="hint">act this week</div></div>
    <div class="card kpi"><div class="lbl"><span class="ic tint-good">${ic('trend')}</span>High Priority</div><div class="val">${R.filter(r=>r.priority==='High').length}</div></div>
    <div class="card kpi"><div class="lbl"><span class="ic tint-gold">${ic('grid')}</span>Medium</div><div class="val">${R.filter(r=>r.priority==='Medium').length}</div></div>
  </div>
  <div class="grid cols-2" style="margin-top:16px">${R.map(r=>`<div class="card rec">
    <div class="top"><span class="act">${r.action}</span><span class="badge ${pc(r.priority)}">${r.priority}</span></div>
    <div class="hint" style="font-weight:700;color:var(--ink-2)">Why:</div>
    <ul class="why">${r.why.map(w=>`<li>${ic('check')} ${w}</li>`).join('')}</ul>
    <div class="impact"><span>▶ ${r.do}</span><b style="color:var(--good)">${r.impact}</b></div></div>`).join('')}</div>
  <div class="note">${ic('alert')} Every recommendation is derived from the pipeline's own computed features and shows its evidence. No black-box external decision API is used.</div>`;
}

function pageWhatif(){
  const opts=D.menu.map(m=>`<option value="${m.id}">${m.name}</option>`).join('');
  return `
  <div class="card"><h3>${ic('sliders')} What-If Scenario Lab</h3>
    <p class="sub">Simulate pricing, discount and prep changes on one item. Results are model estimates, not actuals.</p>
    <div class="grid cols-2" style="margin-top:8px;align-items:start"><div>
      <div class="sel" style="width:100%;margin-bottom:18px"><label>Item</label><select id="wiItem" style="flex:1">${opts}</select></div>
      <div class="slider-row"><label>Price change</label><input type="range" id="wiPrice" min="-30" max="30" value="0"><output id="wiPriceOut">0%</output></div>
      <div class="slider-row"><label>Discount</label><input type="range" id="wiDisc" min="0" max="50" value="0"><output id="wiDiscOut">0%</output></div>
      <div class="slider-row"><label>Prep quantity</label><input type="range" id="wiPrep" min="-40" max="40" value="0"><output id="wiPrepOut">0%</output></div>
      <div class="slider-row"><label>Promotion push</label><input type="range" id="wiPromo" min="0" max="100" value="0"><output id="wiPromoOut">0%</output></div>
      <button class="btn" id="wiReset" style="margin-top:6px">Reset scenario</button>
    </div><div>
      <div class="impact-grid" id="wiOut"></div>
      <div class="note">${ic('alert')} Estimates use price elasticity, current margin and demand baselines — directional guidance, not guarantees.</div>
    </div></div></div>
  <div class="card" style="margin-top:16px"><h3>${ic('grid')} Scenario vs Baseline</h3><p class="sub">Projected weekly figures at current settings</p><div id="wiChart"></div></div>`;
}

/* =========================================================================
   ROUTER + wiring
   ========================================================================= */
/* ---- Reports & Export (SRS steps 49 + 50) ------------------------------- */
function pageReports(){
  const canExport=PERMS.includes('export');
  return `
  <div class="card">
    <div class="hd"><div><h3>${ic('download')} Reports</h3>
      <p class="sub"><b>View</b> any report as a table right here${canExport?', or download it as <b>CSV</b> / <b>Excel</b>.':'. Downloading needs export access (Manager/Admin) — as an Analyst you can still open and read every report.'}</p></div></div>
    <div id="reportGrid" class="report-grid"><div class="muted">Loading report catalogue…</div></div>
  </div>`;
}
function downloadReport(key,fmt){ window.open('download/'+key+(fmt==='xlsx'?'?fmt=xlsx':''),'_blank'); }
window.downloadReport=downloadReport;

/* open a processed report as an Excel-like table in a modal. available to EVERY
   logged-in role (Analysts included) — reading data ≠ exporting it. */
function viewReport(key){
  const modal=document.getElementById('xlModal');
  const scroll=document.getElementById('xlScroll');
  const titleEl=document.getElementById('xlTitle');
  const metaEl=document.getElementById('xlMeta');
  modal.hidden=false; document.body.classList.add('modal-open');
  titleEl.textContent='Loading…'; metaEl.textContent=''; scroll.innerHTML='<div class="muted" style="padding:20px">Loading…</div>';
  // bail out with a clear message if the server can't be reached (e.g. it was
  // restarted) instead of spinning on "Loading…" forever.
  const ctrl=new AbortController(); const timer=setTimeout(()=>ctrl.abort(),8000);
  fetch('api/report/'+key,{signal:ctrl.signal}).then(r=>{clearTimeout(timer);if(!r.ok)throw new Error(r.status);return r.json();}).then(d=>{
    titleEl.textContent=d.title;
    metaEl.textContent=`${d.columns.length} columns · ${d.total.toLocaleString()} rows${d.truncated?` (showing first ${d.rows.length.toLocaleString()})`:''}`;
    const isNum=v=>v!=='' && v!=null && !isNaN(v);
    const head='<thead><tr><th class="xl-rn">#</th>'+d.columns.map(c=>`<th>${c}</th>`).join('')+'</tr></thead>';
    const body='<tbody>'+d.rows.map((row,i)=>`<tr><td class="xl-rn">${i+1}</td>`+
      row.map(cell=>`<td class="${isNum(cell)?'num':''}">${cell===''?'<span class="muted">—</span>':cell}</td>`).join('')+'</tr>').join('')+'</tbody>';
    scroll.innerHTML=`<table class="xl-table">${head}${body}</table>`;
  }).catch(()=>{clearTimeout(timer);scroll.innerHTML='<div class="muted" style="padding:20px">Could not load this report — the server may have restarted. Refresh the page and try again.</div>';});
}
window.viewReport=viewReport;
function closeXl(){document.getElementById('xlModal').hidden=true;document.body.classList.remove('modal-open');}

/* ---- live filtering ----------------------------------------------------- */
function collectFilters(){
  const g=id=>{const e=document.getElementById(id);return e?e.value.trim():'';};
  return {date_from:g('f_date_from'),date_to:g('f_date_to'),location:g('f_location'),
    category:g('f_category'),item:g('f_item'),segment:g('f_segment'),channel:g('f_channel'),
    promotion:g('f_promotion'),klass:g('f_klass'),price_min:g('f_price_min'),price_max:g('f_price_max'),
    rating_min:g('f_rating_min'),waste_min:g('f_waste_min'),waste_max:g('f_waste_max')};
}
function countActive(f){let n=0;for(const k in f){const v=f[k];if(v&&v!=='all')n++;}return n;}
async function applyFilters(){
  const f=collectFilters(), n=countActive(f);
  const btn=document.getElementById('fbApply'); btn.disabled=true; btn.textContent='Applying…';
  try{
    const res=await fetch('api/filter',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(f)});
    const data=await res.json();
    setData(Object.assign({},BASE,data));           // overlay recomputed fields
    document.getElementById('fCount').textContent=n?('· '+n):'';
    const m=data.meta||{};
    document.getElementById('fbResult').innerHTML = m.empty?'<b>No matching orders</b>':
      `Matched <b>${knum(m.orders)}</b> orders · <b>${knum(m.lines)}</b> lines · <b>${knum(m.customers)}</b> customers · <b>${m.items}</b> items`;
    document.querySelector('.main').classList.toggle('is-filtered',n>0);
    go(current);
  }catch(e){document.getElementById('fbResult').textContent='Filter failed';}
  btn.disabled=false; btn.textContent='Apply filters';
}
function resetFilters(){
  ['f_date_from','f_date_to','f_price_min','f_price_max','f_waste_min','f_waste_max'].forEach(id=>{const e=document.getElementById(id);if(e)e.value='';});
  document.getElementById('f_rating_min').value='';
  ['f_location','f_category','f_item','f_segment','f_channel','f_promotion','f_klass'].forEach(id=>{const e=document.getElementById(id);if(e)e.value='all';});
  setData(BASE);
  document.getElementById('fCount').textContent='';
  document.getElementById('fbResult').textContent='';
  document.querySelector('.main').classList.remove('is-filtered');
  go(current);
}
async function initFilters(){
  try{
    const o=await (await fetch('api/filter/options')).json();
    const fill=(id,arr,valFn,txtFn)=>{const s=document.getElementById(id);if(!s)return;
      arr.forEach(x=>{const op=document.createElement('option');op.value=valFn(x);op.textContent=txtFn(x);s.appendChild(op);});};
    fill('f_location',o.locations,x=>x,x=>x);
    fill('f_category',o.categories,x=>x,x=>x);
    fill('f_channel',o.channels,x=>x,x=>x);
    fill('f_promotion',o.promotions,x=>x,x=>x);
    fill('f_klass',o.classes,x=>x,x=>x);
    fill('f_segment',o.segments,x=>x,x=>x);
    fill('f_item',o.items,x=>x.id,x=>x.name);
  }catch(e){/* leave selects minimal if options fail */}
  const fb=document.getElementById('filterBtn');
  if(fb)fb.addEventListener('click',()=>{const bar=document.getElementById('filterbar');bar.toggleAttribute('hidden');fb.classList.toggle('on',!bar.hasAttribute('hidden'));});
  const ap=document.getElementById('fbApply'); if(ap)ap.addEventListener('click',applyFilters);
  const rs=document.getElementById('fbReset'); if(rs)rs.addEventListener('click',resetFilters);
}

const PAGES={
  home:{fn:pageHome,title:'Home',sub:'Your restaurant at a glance',icon:'grid',grp:'Overview'},
  exec:{fn:pageExec,title:'Executive Dashboard',sub:'Restaurant-wide performance at a glance',icon:'grid',grp:'Overview'},
  menu:{fn:pageMenu,title:'Menu Intelligence',sub:'Item performance, classification & tricky cases',icon:'utensils',grp:'Overview'},
  customer:{fn:pageCustomer,title:'Customers & RFM',sub:'Segments, loyalty and churn risk',icon:'users',grp:'Overview'},
  wastage:{fn:pageWastage,title:'Wastage Intelligence',sub:'Cost, hot spots and risk predictions',icon:'trash',grp:'Operations'},
  forecast:{fn:pageForecast,title:'Demand Forecast',sub:'Time-aware forecasting with honest error metrics',icon:'trend',grp:'Operations'},
  pricing:{fn:pagePricing,title:'Pricing & Promotions',sub:'Elasticity, sensitivity and promo traps',icon:'tag',grp:'Operations'},
  basket:{fn:pageBasket,title:'Market Basket',sub:'What sells together — and what to bundle',icon:'basket',grp:'Operations'},
  location:{fn:pageLocation,title:'Multi-Location',sub:'Branch-by-branch comparison',icon:'pin',grp:'Operations'},
  dual:{fn:pageDual,title:'Dual-Pipeline Intelligence',sub:'Spark MLlib vs Python — independent & compared',icon:'compare',grp:'Intelligence'},
  anomaly:{fn:pageAnomaly,title:'Anomalies & Data Quality',sub:'Unusual events, explained',icon:'alert',grp:'Intelligence'},
  recs:{fn:pageRecs,title:'Recommendations',sub:'Evidence-backed actions, prioritised by impact',icon:'bulb',grp:'Intelligence'},
  whatif:{fn:pageWhatif,title:'What-If Lab',sub:'Simulate changes before you commit',icon:'sliders',grp:'Intelligence',need:'export'},
  reports:{fn:pageReports,title:'Reports & Export',sub:'Download any analysis as CSV or Excel',icon:'download',grp:'Data'},
};
let current='exec';

// a page is visible only if the role holds the permission it needs (if any).
// this is what makes the roles physically different sidebars, not just labels.
function canSee(p){return !p.need || PERMS.includes(p.need);}

function buildSidebar(){
  const nav=document.getElementById('nav');
  let html='',lastGrp='';
  for(const [key,p] of Object.entries(PAGES)){
    if(!canSee(p))continue;
    if(p.grp!==lastGrp){html+=`<div class="grp">${p.grp}</div>`;lastGrp=p.grp;}
    html+=`<a data-page="${key}" class="${key==='home'?'on':''}">${ic(p.icon)} ${p.title}</a>`;
  }
  nav.innerHTML=html;
  nav.addEventListener('click',e=>{const a=e.target.closest('a[data-page]');if(a)go(a.dataset.page);});
}

function go(page){
  // roles can't reach a page they aren't allowed to see, even via a stray link
  if(!PAGES[page]||!canSee(PAGES[page]))page='exec';
  current=page;const meta=PAGES[page];
  document.getElementById('pageTitle').innerHTML=meta.title;
  document.getElementById('pageSub').innerHTML=meta.sub;
  document.querySelectorAll('#nav a').forEach(a=>a.classList.toggle('on',a.dataset.page===page));
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('on'));
  const el=document.getElementById('page-'+page);
  el.innerHTML=meta.fn();el.classList.add('on');
  wirePage(page);
  window.scrollTo({top:0,behavior:'smooth'});
  if(window.innerWidth<=900)document.getElementById('side').classList.remove('open');
}

function wirePage(page){
  if(page==='menu'){
    const fw=document.getElementById('menuFilter');
    fw.addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;
      fw.querySelectorAll('button').forEach(x=>x.classList.remove('on'));b.classList.add('on');
      const k=b.dataset.k;const list=k==='all'?D.menu:D.menu.filter(m=>m.klass===k);
      document.querySelector('#menuTable tbody').innerHTML=menuRows(list);});
    let dir={};
    document.querySelectorAll('#menuTable th').forEach(th=>th.addEventListener('click',()=>{
      const key=th.dataset.s;dir[key]=!dir[key];
      const sorted=[...D.menu].sort((a,b)=>{const x=a[key],y=b[key];return (typeof x==='number'?x-y:(''+x).localeCompare(''+y))*(dir[key]?1:-1);});
      document.querySelector('#menuTable tbody').innerHTML=menuRows(sorted);}));
  }
  if(page==='whatif')wireWhatIf();
  if(page==='reports'){
    const grid=document.getElementById('reportGrid');
    fetch('api/reports').then(r=>r.json()).then(list=>{
      const canExport=PERMS.includes('export');
      grid.innerHTML=list.map(r=>`<div class="rep-card ${r.available?'':'off'}">
        <div class="rep-t">${r.title}</div>
        <div class="rep-b">${r.available?
          `<button class="btn sm view" onclick="viewReport('${r.key}')">${ic('grid')} View</button>`+
          (canExport?
            `<button class="btn sm" onclick="downloadReport('${r.key}','csv')">${ic('download')} CSV</button>
             <button class="btn sm" onclick="downloadReport('${r.key}','xlsx')">${ic('download')} Excel</button>`
            :`<span class="muted">download needs export access</span>`)
          :`<span class="muted">not generated</span>`}</div>
      </div>`).join('');
    }).catch(()=>{grid.innerHTML='<div class="muted">Could not load report catalogue.</div>';});
  }
}

/* what-if maths - simple honest elasticity model, baseline pulled from real data */
function wireWhatIf(){
  const $=id=>document.getElementById(id);
  const weeks=(D.period_days||120)/7;
  function recompute(){
    const item=D.menu.find(m=>m.id===$('wiItem').value)||D.menu[0];
    const dPrice=+$('wiPrice').value,disc=+$('wiDisc').value,dPrep=+$('wiPrep').value,promo=+$('wiPromo').value;
    $('wiPriceOut').textContent=(dPrice>0?'+':'')+dPrice+'%';$('wiDiscOut').textContent=disc+'%';
    $('wiPrepOut').textContent=(dPrep>0?'+':'')+dPrep+'%';$('wiPromoOut').textContent=promo+'%';
    const baseQty=item.qty/weeks, basePrice=item.price, baseCost=item.cost;
    const baseRev=baseQty*basePrice, baseProfit=baseQty*(basePrice-baseCost);
    const baseWaste=baseQty*(item.wastage/100)*baseCost;
    const netPrice=dPrice-disc;
    let qtyMult=1+(-1.1*netPrice/100)+promo/100*0.45;qtyMult=Math.max(0.1,qtyMult);
    const newPrice=basePrice*(1+dPrice/100)*(1-disc/100), newQty=baseQty*qtyMult;
    const newRev=newQty*newPrice, newProfit=newQty*(newPrice-baseCost);
    const prepQty=baseQty*(1+dPrep/100), overPrep=Math.max(0,prepQty-newQty);
    const newWaste=(overPrep+newQty*(item.wastage/100)*0.4)*baseCost;
    const cell=(l,v,base,fmt,goodUp=true)=>{const d=base===0?0:Math.round((v-base)/base*100);const cls=d===0?'flat':((d>0)===goodUp?'up':'down');return `<div class="impact-cell"><div class="l">${l}</div><div class="v">${fmt(v)}</div><div class="d ${cls}">${d>0?'▲ +':d<0?'▼ ':''}${d}% vs base</div></div>`;};
    $('wiOut').innerHTML=cell('Weekly Revenue',newRev,baseRev,kmoney)+cell('Weekly Profit',newProfit,baseProfit,kmoney)+
      cell('Units Sold',newQty,baseQty,v=>Math.round(v))+cell('Wastage Cost',newWaste,baseWaste,kmoney,false)+
      cell('Effective Price',newPrice,basePrice,money)+cell('Margin',(newPrice-baseCost)/newPrice*100,(basePrice-baseCost)/basePrice*100,v=>v.toFixed(0)+'%');
    $('wiChart').innerHTML=barChart([{label:'Revenue (base)',value:baseRev,color:cvar('--line')},{label:'Revenue (new)',value:newRev,color:cvar('--brand')},{label:'Profit (base)',value:baseProfit,color:cvar('--line')},{label:'Profit (new)',value:newProfit,color:cvar('--good')}],{h:220,fmt:kmoney,l:48});
  }
  ['wiItem','wiPrice','wiDisc','wiPrep','wiPromo'].forEach(id=>$(id).addEventListener('input',recompute));
  $('wiReset').addEventListener('click',()=>{['wiPrice','wiDisc','wiPrep','wiPromo'].forEach(id=>$(id).value=0);recompute();});
  recompute();
}

/* theme toggle */
document.getElementById('themeBtn').addEventListener('click',()=>{
  const root=document.documentElement, dark=root.getAttribute('data-theme')==='dark';
  root.setAttribute('data-theme',dark?'light':'dark');
  document.getElementById('themeBtn').innerHTML=ic(dark?'moon':'sun');
  go(current);
});
document.getElementById('burger').addEventListener('click',()=>document.getElementById('side').classList.toggle('open'));



/* export: download the processed report for the current view from the server.
   the button only exists for roles with the export permission (Manager/Admin). */
const exportBtn=document.getElementById('exportBtn');
if(exportBtn){exportBtn.addEventListener('click',()=>{
  // quick-export the report that matches the current view; otherwise send the
  // user to the Reports tab where all 12 are available as CSV or Excel.
  const map={exec:'profitability',menu:'menu_performance',customer:'customer_segments',
    wastage:'wastage_by_item',forecast:'demand_forecast',pricing:'price_sensitivity',
    basket:'market_basket_rules',location:'location_performance',dual:'model_comparison',
    anomaly:'anomalies',recs:'recommendations'};
  const rep=map[current];
  if(rep){window.open('download/'+rep,'_blank');}
  else{go('reports');}
});}

/* ---- Excel-like report modal close wiring ------------------------------- */
(function(){
  const modal=document.getElementById('xlModal');
  const btn=document.getElementById('xlClose');
  if(btn)btn.addEventListener('click',closeXl);
  if(modal)modal.addEventListener('click',e=>{if(e.target===modal)closeXl();});
  addEventListener('keydown',e=>{if(e.key==='Escape'){closeXl();const cb=document.getElementById('chatBox');if(cb)cb.hidden=true;}});
})();

/* ---- chatbot: fully-functional data assistant --------------------------- */
(function(){
  const fab=document.getElementById('chatFab');
  const box=document.getElementById('chatBox');
  const log=document.getElementById('chatLog');
  const form=document.getElementById('chatForm');
  const text=document.getElementById('chatText');
  const chips=document.getElementById('chatChips');
  if(!fab||!box)return;
  let greeted=false;
  function bubble(who,msg){
    const b=document.createElement('div');
    b.className='chat-msg '+who;
    b.innerHTML=msg;
    log.appendChild(b); log.scrollTop=log.scrollHeight;
    return b;
  }
  function open(){
    box.hidden=false; fab.classList.add('on'); text.focus();
    if(!greeted){greeted=true;bubble('bot',"Hi! I'm your Data Pulse assistant. Ask me about revenue, your top item, wastage, locations, customer segments, the forecast or what to do next.");}
  }
  function toggle(){ box.hidden?open():(box.hidden=true,fab.classList.remove('on')); }
  fab.addEventListener('click',toggle);
  document.getElementById('chatClose').addEventListener('click',()=>{box.hidden=true;fab.classList.remove('on');});
  async function send(q){
    if(!q)return;
    bubble('me',q.replace(/</g,'&lt;'));
    text.value='';
    const typing=bubble('bot','<span class="typing"><i></i><i></i><i></i></span>');
    try{
      const r=await fetch('api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:q})});
      const d=await r.json();
      typing.textContent=d.reply||'…';
    }catch(e){ typing.textContent='Sorry — I couldn\'t reach the data just now.'; }
    log.scrollTop=log.scrollHeight;
  }
  form.addEventListener('submit',e=>{e.preventDefault();send(text.value.trim());});
  chips.addEventListener('click',e=>{const b=e.target.closest('button[data-q]');if(b)send(b.dataset.q);});
})();

/* tooltip */
const tt=document.getElementById('tooltip');
document.addEventListener('mouseover',e=>{const t=e.target.closest('[data-tip]');if(t){tt.textContent=t.getAttribute('data-tip');tt.style.opacity=1;}});
document.addEventListener('mousemove',e=>{if(tt.style.opacity==='1'){tt.style.left=e.clientX+'px';tt.style.top=e.clientY+'px';}});
document.addEventListener('mouseout',e=>{if(e.target.closest('[data-tip]'))tt.style.opacity=0;});

/* boot */
buildSidebar();
initFilters();
// sync theme button glyph with whatever theme the page loaded in (dark by default)
document.getElementById('themeBtn').innerHTML=ic(document.documentElement.getAttribute('data-theme')==='dark'?'sun':'moon');
if(!D.kpis){document.getElementById('pageSub').textContent='No data - run the pipeline first (python -m src.pipeline)';}
go('home');

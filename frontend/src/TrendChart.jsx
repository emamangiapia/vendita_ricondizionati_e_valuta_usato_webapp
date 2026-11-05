import React, {useMemo,useState} from 'react';
import {buildTrendSeries,formatAxisDate,formatExtractionDate,formatStorage} from './trendData.js';

const currency = value => new Intl.NumberFormat('it-IT',{style:'currency',currency:'EUR'}).format(value);
const BOX={left:76,right:18,top:22,bottom:58,width:720,height:300};
const COLORS=['#4d7609','#ad4400','#1456a0','#8a347a','#00766e','#a02f35','#694fc1','#755100'];
const DASHES=['','8 4','3 3','10 4 2 4'];

export default function TrendChart({rows,allColors}) {
  const series=useMemo(()=>buildTrendSeries(rows),[rows]);
  const [active,setActive]=useState(null);
  const points=series.flatMap(s=>s.points);
  if (!points.length) return null;
  const first=Math.min(...points.map(p=>p.time)),last=Math.max(...points.map(p=>p.time));
  const min=Math.min(...points.map(p=>p.value)),max=Math.max(...points.map(p=>p.value));
  const padding=Math.max((max-min)*.12,1);
  const low=Math.max(0,min-padding),high=max+padding;
  const width=BOX.width-BOX.left-BOX.right,height=BOX.height-BOX.top-BOX.bottom;
  const x=t=>first===last?BOX.left+width/2:BOX.left+(t-first)/(last-first)*width;
  const y=p=>BOX.top+(high-p)/(high-low)*height;
  const tickCount=first===last?1:5;
  const ticks=Array.from({length:tickCount},(_,i)=>tickCount===1?first:first+(last-first)*i/(tickCount-1));
  const values=Array.from({length:4},(_,i)=>low+(high-low)*i/3);
  const selected=active===null?null:series.find(s=>s.storage===active.storage);
  const chosen=selected?.points.find(p=>p.date===active?.date);
  return <section className="trend-section"><h3>Andamento nel tempo</h3>
    <p className="muted">{allColors?'Media dei colori disponibili per ogni memoria e ogni estrazione.':'Prezzo del colore selezionato per ogni memoria ed estrazione.'} Passa sui punti o selezionali per i dettagli.</p>
    <ul className="trend-legend" aria-label="Legenda memorie">{series.map((s,i)=><li key={s.storage}><svg width="30" height="14" aria-hidden="true"><line x1="1" y1="7" x2="29" y2="7" stroke={COLORS[i%COLORS.length]} strokeWidth="3" strokeDasharray={DASHES[i%DASHES.length]}/></svg><span>{formatStorage(s.storage)}</span></li>)}</ul>
    <div className="trend-frame" onMouseLeave={()=>setActive(null)}><div className="trend-scroll"><div className="trend-chart-canvas">
      <svg viewBox={`0 0 ${BOX.width} ${BOX.height}`} role="group" aria-label="Grafico interattivo dei prezzi per memoria">
        {values.map(v=><g key={v}><line x1={BOX.left} x2={BOX.width-BOX.right} y1={y(v)} y2={y(v)} className="trend-grid"/><text x={BOX.left-10} y={y(v)+4} textAnchor="end" className="trend-axis">{currency(v)}</text></g>)}
        <line x1={BOX.left} x2={BOX.width-BOX.right} y1={BOX.top+height} y2={BOX.top+height} className="trend-baseline"/>
        {ticks.map((t,i)=><g key={i}><line x1={x(t)} x2={x(t)} y1={BOX.top+height} y2={BOX.top+height+5} className="trend-baseline"/><text x={x(t)} y={BOX.top+height+21} textAnchor={i===0?'start':i===ticks.length-1?'end':'middle'} className="trend-axis">{formatAxisDate(t)}</text></g>)}
        <text x={BOX.left+width/2} y={BOX.height-8} textAnchor="middle" className="trend-axis">Data di estrazione</text>
        {series.map((s,i)=><path key={s.storage} d={s.points.map((p,j)=>`${j?'L':'M'} ${x(p.time)} ${y(p.value)}`).join(' ')} className="trend-line" style={{stroke:COLORS[i%COLORS.length]}} strokeDasharray={DASHES[i%DASHES.length]}/>)}
        {series.flatMap((s,i)=>s.points.map(p=><g key={`${s.storage}:${p.date}`} tabIndex="0" role="button" aria-label={`${formatStorage(s.storage)}, ${formatExtractionDate(p.time)}, ${allColors?'prezzo medio':'prezzo'} ${currency(p.value)}${p.files.length?', file '+p.files.join(', '):''}`} onFocus={()=>setActive({storage:s.storage,date:p.date})} onBlur={()=>setActive(null)} onMouseEnter={()=>setActive({storage:s.storage,date:p.date})} onClick={()=>setActive({storage:s.storage,date:p.date})}>
          <circle cx={x(p.time)} cy={y(p.value)} r="12" fill="transparent"/><circle cx={x(p.time)} cy={y(p.value)} r={active?.storage===s.storage&&active?.date===p.date?6:4} className="trend-dot" style={{fill:COLORS[i%COLORS.length]}} pointerEvents="none"/>
        </g>))}
      </svg>
      {chosen && <div className="trend-tooltip" role="status" style={{'--tip-x':`${100*x(chosen.time)/BOX.width}%`,top:`${100*y(chosen.value)/BOX.height}%`}}>
        <strong>{formatStorage(selected.storage)} · {allColors?'Prezzo medio':'Prezzo'}: {currency(chosen.value)}</strong><span>{formatExtractionDate(chosen.time)}</span>
        {allColors&&<span>{chosen.count} {chosen.count===1?'valore disponibile':'valori disponibili'}</span>}
        {chosen.files.length>0&&<span>File: {chosen.files.join(', ')}</span>}
      </div>}
    </div></div></div>
  </section>;
}

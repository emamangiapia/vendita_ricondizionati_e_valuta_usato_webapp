import React, {useMemo,useState} from 'react';
import {buildTrend,formatAxisDate,formatExtractionDate} from './trendData.js';

const currency = value => new Intl.NumberFormat('it-IT',{style:'currency',currency:'EUR'}).format(value);
const BOX={left:76,right:18,top:22,bottom:58,width:720,height:300};

export default function TrendChart({rows,allColors}) {
  const points=useMemo(()=>buildTrend(rows),[rows]);
  const [active,setActive]=useState(null);
  if (!points.length) return null;
  const first=points[0].time,last=points.at(-1).time;
  const min=Math.min(...points.map(p=>p.value)),max=Math.max(...points.map(p=>p.value));
  const padding=Math.max((max-min)*.12,1);
  const low=Math.max(0,min-padding), high=max+padding;
  const width=BOX.width-BOX.left-BOX.right,height=BOX.height-BOX.top-BOX.bottom;
  const x=t=>first===last?BOX.left+width/2:BOX.left+(t-first)/(last-first)*width;
  const y=p=>BOX.top+(high-p)/(high-low)*height;
  const tickCount=first===last?1:5;
  const ticks=Array.from({length:tickCount},(_,i)=>tickCount===1?first:first+(last-first)*i/(tickCount-1));
  const values=Array.from({length:4},(_,i)=>low+(high-low)*i/3);
  const path=points.map((p,i)=>`${i?'L':'M'} ${x(p.time)} ${y(p.value)}`).join(' ');
  const chosen=active===null?null:points[active];
  return <section className="trend-section"><h3>Andamento nel tempo</h3>
    <p className="muted">{allColors?'Media dei colori disponibili per ogni estrazione.':'Prezzo del colore selezionato per ogni estrazione.'} Passa sui punti o selezionali per i dettagli.</p>
    <div className="trend-frame" onMouseLeave={()=>setActive(null)}><div className="trend-scroll"><div className="trend-chart-canvas">
      <svg viewBox={`0 0 ${BOX.width} ${BOX.height}`} role="group" aria-label="Grafico interattivo dell’andamento dei prezzi">
        {values.map(v=><g key={v}><line x1={BOX.left} x2={BOX.width-BOX.right} y1={y(v)} y2={y(v)} className="trend-grid"/><text x={BOX.left-10} y={y(v)+4} textAnchor="end" className="trend-axis">{currency(v)}</text></g>)}
        <line x1={BOX.left} x2={BOX.width-BOX.right} y1={BOX.top+height} y2={BOX.top+height} className="trend-baseline"/>
        {ticks.map((t,i)=><g key={i}><line x1={x(t)} x2={x(t)} y1={BOX.top+height} y2={BOX.top+height+5} className="trend-baseline"/><text x={x(t)} y={BOX.top+height+21} textAnchor={i===0?'start':i===ticks.length-1?'end':'middle'} className="trend-axis">{formatAxisDate(t)}</text></g>)}
        <text x={BOX.left+width/2} y={BOX.height-8} textAnchor="middle" className="trend-axis">Data di estrazione</text>
        <path d={path} className="trend-line"/>
        {points.map((p,i)=><g key={p.date} tabIndex="0" role="button" aria-label={`${formatExtractionDate(p.time)}, ${allColors?'prezzo medio':'prezzo'} ${currency(p.value)}${p.files.length?', file '+p.files.join(', '):''}`} onFocus={()=>setActive(i)} onBlur={()=>setActive(null)} onMouseEnter={()=>setActive(i)} onClick={()=>setActive(i)}>
          <circle cx={x(p.time)} cy={y(p.value)} r="12" fill="transparent"/><circle cx={x(p.time)} cy={y(p.value)} r={active===i?6:4} className="trend-dot" pointerEvents="none"/>
        </g>)}
      </svg>
      {chosen && <div className="trend-tooltip" role="status" style={{'--tip-x':`${100*x(chosen.time)/BOX.width}%`,top:`${100*y(chosen.value)/BOX.height}%`}}>
        <strong>{allColors?'Prezzo medio':'Prezzo'}: {currency(chosen.value)}</strong><span>{formatExtractionDate(chosen.time)}</span>
        {allColors&&<span>{chosen.count} {chosen.count===1?'valore disponibile':'valori disponibili'}</span>}
        {chosen.files.length>0&&<span>File: {chosen.files.join(', ')}</span>}
      </div>}
    </div></div></div>
  </section>;
}

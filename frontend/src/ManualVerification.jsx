import React,{useEffect,useRef,useState} from 'react';

export default function ManualVerification({job,running,request}) {
 const [view,setView]=useState(null),[error,setError]=useState('');
 const chain=useRef(Promise.resolve()),lastMove=useRef(0),pressed=useRef(false);
 useEffect(()=>{
  setView(null);setError('');if(!running)return;
  let active=true,timer;
  async function update(){try{const data=await request('/jobs/'+job+'/challenge');if(active){setView(data);setError('')}}catch(e){if(active)setError(e.message)}finally{if(active)timer=setTimeout(update,700)}}
  update();return()=>{active=false;clearTimeout(timer)};
 },[job,running]);
 function send(event){chain.current=chain.current.then(()=>request('/jobs/'+job+'/challenge',{method:'POST',body:JSON.stringify(event)})).catch(e=>setError(e.message))}
 function pointer(e,type){
  e.preventDefault();
  if(type==='down'){pressed.current=true;e.currentTarget.setPointerCapture(e.pointerId);e.currentTarget.focus()}
  if(type==='move'){if(!pressed.current||Date.now()-lastMove.current<80)return;lastMove.current=Date.now()}
  const rect=e.currentTarget.getBoundingClientRect();
  send({type,x:Math.max(0,Math.min(1,(e.clientX-rect.left)/rect.width)),y:Math.max(0,Math.min(1,(e.clientY-rect.top)/rect.height))});
  if(type==='up')pressed.current=false;
 }
 if(!running||!view?.active)return null;
 return <section className="manual-verification"><h3>Verifica richiesta</h3><p>Risolvi la verifica qui sotto. Puoi cliccare o trascinare gli elementi, anche dal telefono. Quando hai finito, premi Continua.</p>
  <img src={'data:image/jpeg;base64,'+view.frame} alt="Browser dello scraper in attesa di verifica" draggable={false} tabIndex={0}
   style={{display:'block',width:'100%',touchAction:'none',border:'1px solid #ccc'}}
   onPointerDown={e=>pointer(e,'down')} onPointerMove={e=>pointer(e,'move')} onPointerUp={e=>pointer(e,'up')} onPointerCancel={e=>pointer(e,'up')}
   onKeyDown={e=>{const key=e.key===' '?'Space':e.key;if(['Tab','Enter','Space','ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Backspace'].includes(key)){e.preventDefault();send({type:'key',key})}}}/>
  {error&&<p role="alert">{error}</p>}<button onClick={()=>send({type:'continue'})}>Verifica completata · Continua</button>
 </section>;
}

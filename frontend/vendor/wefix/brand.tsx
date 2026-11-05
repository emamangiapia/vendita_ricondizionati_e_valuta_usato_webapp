import type {HTMLAttributes} from 'react';
import {Wrench} from 'lucide-react';
export function BrandMark({className='',...props}:HTMLAttributes<HTMLSpanElement>){
 return <span className={'wfx-brand-mark '+className} aria-hidden="true" {...props}><Wrench size={20}/></span>;
}
/** Logotipo semplificato solo per UI; per brand ufficiale utilizzare assets/wefix-logo.svg. */
export function BrandLogo({className='',...props}:HTMLAttributes<HTMLSpanElement>){
 return <span className={'wfx-brand-logo '+className} {...props}><BrandMark/><span>WeFix<span className="wfx-logo-dot">.it</span></span></span>;
}
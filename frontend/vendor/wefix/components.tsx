import {forwardRef,useId,useContext,createContext,type ReactNode,type HTMLAttributes,
type ButtonHTMLAttributes,type InputHTMLAttributes,type SelectHTMLAttributes,
type TextareaHTMLAttributes,type ComponentPropsWithoutRef} from 'react';
import * as DialogPrimitive from '@radix-ui/react-dialog';
import * as TabsPrimitive from '@radix-ui/react-tabs';
import {AlertCircle,CheckCircle2,Info,X,Inbox,LoaderCircle} from 'lucide-react';

const cx=(...values:(string|undefined|false|null)[])=>values.filter(Boolean).join(' ');
const ThemeContext=createContext<'light'|'dark'>('light');
export interface ThemeProviderProps extends HTMLAttributes<HTMLDivElement>{theme?:'light'|'dark';children:ReactNode}
export function ThemeProvider({theme='light',className,children,...props}:ThemeProviderProps){
 return <ThemeContext.Provider value={theme}><div {...props} className={cx('wfx-root',className)} data-wfx-theme={theme}>{children}</div></ThemeContext.Provider>;
}
export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement>{
 variant?:'primary'|'commerce'|'outline'|'ghost'|'danger';size?:'sm'|'md'|'lg';
 loading?:boolean;leadingIcon?:ReactNode;trailingIcon?:ReactNode
}
export const Button=forwardRef<HTMLButtonElement,ButtonProps>(function Button({variant='primary',size='md',loading=false,
leadingIcon,trailingIcon,className,children,disabled,type='button',...props},ref){
 return <button ref={ref} {...props} type={type} disabled={disabled||loading}
 aria-busy={loading||undefined} className={cx('wfx-button','wfx-button--'+variant,'wfx-button--'+size,className)}>
 {loading?<LoaderCircle size={16} className="wfx-spin" aria-hidden="true"/>:leadingIcon}<span>{children}</span>{trailingIcon}</button>;
});
export const Card=forwardRef<HTMLDivElement,HTMLAttributes<HTMLDivElement>>(function Card({className,...props},ref){
 return <div {...props} ref={ref} className={cx('wfx-card',className)}/>;
});
export function CardHeader({className,...props}:HTMLAttributes<HTMLDivElement>){return <div {...props} className={cx('wfx-card-header',className)}/>;}
export function CardBody({className,...props}:HTMLAttributes<HTMLDivElement>){return <div {...props} className={cx('wfx-card-body',className)}/>;}
export function CardFooter({className,...props}:HTMLAttributes<HTMLDivElement>){return <div {...props} className={cx('wfx-card-footer',className)}/>;}
export interface BadgeProps extends HTMLAttributes<HTMLSpanElement>{tone?:'neutral'|'success'|'warning'|'danger'|'info';children:ReactNode}
export function Badge({tone='neutral',className,...props}:BadgeProps){
 return <span {...props} className={cx('wfx-badge','wfx-badge--'+tone,className)}/>;
}
export interface TextFieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>,'size'>{label:string;hint?:string;error?:string;inputSize?:'sm'|'md'}
export const TextField=forwardRef<HTMLInputElement,TextFieldProps>(function TextField({label,hint,error,id,className,required,inputSize='md',...props},ref){
 const generatedId=useId();const fid=id??generatedId;const helpId=fid+'-help';
 return <div className={cx('wfx-field',className)}><label htmlFor={fid} className="wfx-label">{label}{required&&' *'}</label>
 <input {...props} ref={ref} id={fid} required={required} className={cx('wfx-input','wfx-input--'+inputSize,error&&'wfx-input--error')}
 aria-invalid={!!error||undefined} aria-describedby={[props['aria-describedby'], hint||error?helpId:undefined].filter(Boolean).join(' ')||undefined}/>
 {(hint||error)&&<small id={helpId} className={cx('wfx-help',error&&'wfx-help--error')}>{error||hint}</small>}</div>;
});
export interface SelectFieldProps extends SelectHTMLAttributes<HTMLSelectElement>{label:string;hint?:string;error?:string;options:{value:string;label:string;disabled?:boolean}[];placeholder?:string}
export const SelectField=forwardRef<HTMLSelectElement,SelectFieldProps>(function SelectField({label,hint,error,options,placeholder,id,className,required,...props},ref){
 const generatedId=useId();const fid=id??generatedId;const helpId=fid+'-help';
 return <div className={cx('wfx-field',className)}><label htmlFor={fid} className="wfx-label">{label}{required&&' *'}</label>
 <select {...props} ref={ref} id={fid} required={required} className={cx('wfx-select',error&&'wfx-input--error')}
 aria-invalid={!!error||undefined} aria-describedby={[props['aria-describedby'], hint||error?helpId:undefined].filter(Boolean).join(' ')||undefined}>
 {placeholder&&<option value="">{placeholder}</option>}{options.map(o=><option key={o.value} value={o.value} disabled={o.disabled}>{o.label}</option>)}
 </select>{(hint||error)&&<small id={helpId} className={cx('wfx-help',error&&'wfx-help--error')}>{error||hint}</small>}</div>;
});
export interface TextareaFieldProps extends TextareaHTMLAttributes<HTMLTextAreaElement>{label:string;hint?:string;error?:string}
export const TextareaField=forwardRef<HTMLTextAreaElement,TextareaFieldProps>(function TextareaField({label,hint,error,id,className,required,...props},ref){
 const generatedId=useId();const fid=id??generatedId;const helpId=fid+'-help';
 return <div className={cx('wfx-field',className)}><label htmlFor={fid} className="wfx-label">{label}{required&&' *'}</label>
 <textarea {...props} ref={ref} id={fid} required={required} className={cx('wfx-textarea',error&&'wfx-input--error')}
 aria-invalid={!!error||undefined} aria-describedby={[props['aria-describedby'], hint||error?helpId:undefined].filter(Boolean).join(' ')||undefined}/>
 {(hint||error)&&<small id={helpId} className={cx('wfx-help',error&&'wfx-help--error')}>{error||hint}</small>}</div>;
});
export interface CheckboxFieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>,'type'>{label:string;hint?:string}
export const CheckboxField=forwardRef<HTMLInputElement,CheckboxFieldProps>(function CheckboxField({label,hint,id,className,...props},ref){
 const generatedId=useId();const fid=id??generatedId;return <div className={cx('wfx-check-wrap',className)}>
 <input {...props} ref={ref} id={fid} type="checkbox" className="wfx-checkbox" aria-describedby={[props['aria-describedby'],hint?fid+'-hint':undefined].filter(Boolean).join(' ')||undefined}/>
 <div><label htmlFor={fid} className="wfx-check-label">{label}</label>{hint&&<small id={fid+'-hint'} className="wfx-help">{hint}</small>}</div></div>;
});
export interface AlertProps extends HTMLAttributes<HTMLDivElement>{tone?:'info'|'success'|'warning'|'danger';title?:string;children:ReactNode}
const alerts={info:Info,success:CheckCircle2,warning:AlertCircle,danger:AlertCircle};
export function Alert({tone='info',title,children,className,...props}:AlertProps){const Icon=alerts[tone];return <div {...props} role={tone==='danger'?'alert':'status'} className={cx('wfx-alert','wfx-alert--'+tone,className)}><Icon size={19} aria-hidden="true"/><div>{title&&<strong>{title}</strong>}<div>{children}</div></div></div>;}
export interface StatCardProps extends HTMLAttributes<HTMLDivElement>{label:string;value:ReactNode;change?:string;icon?:ReactNode}
export function StatCard({label,value,change,icon,className,...props}:StatCardProps){return <Card {...props} className={cx('wfx-stat',className)}>
 <div className="wfx-stat-top"><span>{label}</span>{icon}</div><div className="wfx-stat-value">{value}</div>{change&&<small>{change}</small>}</Card>;}
export interface EmptyStateProps extends HTMLAttributes<HTMLDivElement>{title:string;description?:string;action?:ReactNode;icon?:ReactNode}
export function EmptyState({title,description,action,icon,className,...props}:EmptyStateProps){return <div {...props} className={cx('wfx-empty',className)}>
 <span className="wfx-empty-icon">{icon??<Inbox size={30}/>}</span><h3>{title}</h3>{description&&<p>{description}</p>}{action}</div>;}
export function Skeleton({width='100%',height=18,className,style,...props}:HTMLAttributes<HTMLDivElement>&{width?:number|string;height?:number|string}){return <div {...props} aria-hidden="true" className={cx('wfx-skeleton',className)} style={{width,height,...style}}/>;}
export interface DataTableColumn<Row>{key:string;header:string;render:(row:Row)=>ReactNode;numeric?:boolean}
export function DataTable<Row>({columns,rows,getRowKey,caption,empty='Nessun risultato'}:{
 columns:DataTableColumn<Row>[];rows:Row[];getRowKey:(r:Row)=>string;caption?:string;empty?:string
}){return <div className="wfx-table-scroll" role="region" aria-label={caption??'Tabella dati'} tabIndex={0}><table className="wfx-table">
 {caption&&<caption>{caption}</caption>}<thead><tr>{columns.map(c=><th key={c.key} scope="col" className={c.numeric?'wfx-number':''}>{c.header}</th>)}</tr></thead>
 <tbody>{rows.length?rows.map(r=><tr key={getRowKey(r)}>{columns.map(c=><td key={c.key} className={c.numeric?'wfx-number':''}>{c.render(r)}</td>)}</tr>):<tr><td colSpan={columns.length}>{empty}</td></tr>}</tbody></table></div>;}
export interface SidebarNavItem{id:string;label:string;href:string;icon?:ReactNode}
export function SidebarNav({items,activeId,ariaLabel='Navigazione principale'}:{items:SidebarNavItem[];activeId?:string;ariaLabel?:string}){return <nav className="wfx-sidebar-nav" aria-label={ariaLabel}>{items.map(i=><a key={i.id} href={i.href} aria-current={activeId===i.id?'page':undefined} className={cx('wfx-nav-link',activeId===i.id&&'wfx-nav-link--active')}>{i.icon}<span>{i.label}</span></a>)}</nav>;}
export function AppShell({header,sidebar,children,className}:{header:ReactNode;sidebar?:ReactNode;children:ReactNode;className?:string}){return <div className={cx('wfx-appshell',className)}><header className="wfx-appshell-header">{header}</header><div className={cx('wfx-appshell-layout',!sidebar&&'wfx-no-sidebar')}>{sidebar&&<aside className="wfx-appshell-sidebar">{sidebar}</aside>}<main className="wfx-appshell-main">{children}</main></div></div>;}
export interface DialogProps extends ComponentPropsWithoutRef<typeof DialogPrimitive.Root>{title:string;description?:string;trigger?:ReactNode;children:ReactNode;footer?:ReactNode}
export function Dialog({title,description,trigger,children,footer,...props}:DialogProps){const theme=useContext(ThemeContext);return <DialogPrimitive.Root {...props}>
 {trigger&&<DialogPrimitive.Trigger asChild>{trigger}</DialogPrimitive.Trigger>}
 <DialogPrimitive.Portal><DialogPrimitive.Overlay className="wfx-dialog-overlay"/>
 <DialogPrimitive.Content className="wfx-root wfx-dialog" data-wfx-theme={theme}>
 <div className="wfx-dialog-head"><DialogPrimitive.Title>{title}</DialogPrimitive.Title><DialogPrimitive.Close className="wfx-dialog-close" aria-label="Chiudi"><X size={19}/></DialogPrimitive.Close></div>
 <DialogPrimitive.Description className={description?'wfx-dialog-description':'wfx-visually-hidden'}>{description??title}</DialogPrimitive.Description>
 <div className="wfx-dialog-content">{children}</div>{footer&&<div className="wfx-dialog-footer">{footer}</div>}
 </DialogPrimitive.Content></DialogPrimitive.Portal></DialogPrimitive.Root>;}
export const Tabs=TabsPrimitive.Root;
export function TabsList({className,...props}:ComponentPropsWithoutRef<typeof TabsPrimitive.List>){return <TabsPrimitive.List {...props} className={cx('wfx-tabs-list',className)}/>;}
export function TabsTrigger({className,...props}:ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>){return <TabsPrimitive.Trigger {...props} className={cx('wfx-tabs-trigger',className)}/>;}
export function TabsContent({className,...props}:ComponentPropsWithoutRef<typeof TabsPrimitive.Content>){return <TabsPrimitive.Content {...props} className={cx('wfx-tabs-content',className)}/>;}
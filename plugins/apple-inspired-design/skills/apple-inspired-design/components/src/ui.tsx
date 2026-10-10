import * as React from 'react';
import clsx from 'clsx';

// Utility-class components: use a Tailwind build that scans these files.
const focus = 'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ui-accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--ui-bg)]';

export type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'ghost'; size?: 'sm' | 'md' };
export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(function Button({variant='primary', size='md', className, type='button', ...props}, ref) {
  const variants = {primary:'bg-[var(--ui-accent)] text-[var(--ui-on-accent)] hover:opacity-90',secondary:'bg-[var(--ui-surface)] border border-[var(--ui-border)] text-[var(--ui-text)] hover:bg-[var(--ui-bg)]',ghost:'text-[var(--ui-text)] hover:bg-[var(--ui-bg)]'};
  return <button ref={ref} type={type} className={clsx('inline-flex items-center justify-center rounded-[var(--ui-radius-md)] font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50',focus, size==='sm'?'min-h-9 px-3 text-sm':'min-h-11 px-4 text-base',variants[variant],className)} {...props}/>;
});

export const Card = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(function Card({className,...props},ref) {return <div ref={ref} className={clsx('rounded-[var(--ui-radius-lg)] border border-[var(--ui-border)] bg-[var(--ui-surface)] p-5 text-[var(--ui-text)] shadow-sm',className)} {...props}/>});

export type FieldProps = React.InputHTMLAttributes<HTMLInputElement> & {label: string; hint?: string; error?: string};
export const TextField = React.forwardRef<HTMLInputElement,FieldProps>(function TextField({label,hint,error,id,className,...props},ref){
  const generated = React.useId(); const fieldId=id??generated; const desc=[hint?`${fieldId}-hint`:null,error?`${fieldId}-error`:null].filter(Boolean).join(' ')||undefined;
  return <div className="flex flex-col gap-1.5 text-[var(--ui-text)]"><label htmlFor={fieldId} className="text-sm font-medium">{label}</label><input {...props} ref={ref} id={fieldId} aria-invalid={error?true:undefined} aria-describedby={desc} className={clsx('min-h-11 w-full rounded-[var(--ui-radius-md)] border border-[var(--ui-border)] bg-[var(--ui-surface)] px-3 text-base text-[var(--ui-text)] placeholder:text-[var(--ui-muted)] disabled:opacity-50',focus,error&&'border-red-600',className)}/>{hint&&<p id={`${fieldId}-hint`} className="text-sm text-[var(--ui-muted)]">{hint}</p>}{error&&<p id={`${fieldId}-error`} className="text-sm text-red-700 dark:text-red-400" role="alert">{error}</p>}</div>;
});

export type BadgeProps = React.HTMLAttributes<HTMLSpanElement> & {tone?:'neutral'|'success'|'warning'};
export function Badge({tone='neutral',className,...props}:BadgeProps){const tones={neutral:'bg-[var(--ui-bg)] text-[var(--ui-text)]',success:'bg-green-100 text-green-900 dark:bg-green-950 dark:text-green-200',warning:'bg-amber-100 text-amber-950 dark:bg-amber-950 dark:text-amber-200'};return <span className={clsx('inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium',tones[tone],className)} {...props}/>}

export type StackProps = React.HTMLAttributes<HTMLDivElement> & {gap?:'sm'|'md'|'lg';direction?:'row'|'col'};
export function Stack({gap='md',direction='col',className,...props}:StackProps){return <div className={clsx('flex',direction==='row'?'flex-row flex-wrap items-center':'flex-col',{'sm':'gap-2','md':'gap-4','lg':'gap-6'}[gap],className)} {...props}/>}

export function Container({className,...props}:React.HTMLAttributes<HTMLElement>){return <main className={clsx('mx-auto w-full max-w-6xl px-4 py-8 sm:px-6 lg:px-8',className)} {...props}/>}

export type DialogProps = {open:boolean; onClose:()=>void; title:string; children:React.ReactNode; description?:string};
export function Dialog({open,onClose,title,description,children}:DialogProps){
  const titleId=React.useId(), descId=React.useId(),dialogRef=React.useRef<HTMLDivElement>(null),closeRef=React.useRef<HTMLButtonElement>(null);
  React.useEffect(()=>{if(!open)return;const previous=document.activeElement as HTMLElement|null;closeRef.current?.focus();const key=(e:KeyboardEvent)=>{if(e.key==='Escape')onClose();if(e.key==='Tab'){const elements=dialogRef.current?.querySelectorAll<HTMLElement>('a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])');if(!elements?.length){e.preventDefault();return;}const first=elements[0],last=elements[elements.length-1];if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus()}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus()}}};document.addEventListener('keydown',key);return()=>{document.removeEventListener('keydown',key);previous?.focus()}},[open,onClose]);
  React.useEffect(()=>{if(!open)return;const prior=document.body.style.overflow;document.body.style.overflow='hidden';return()=>{document.body.style.overflow=prior}},[open]);
  if(!open)return null;
  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onMouseDown={e=>{if(e.target===e.currentTarget)onClose()}}><div ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby={titleId} aria-describedby={description?descId:undefined} className="w-full max-w-lg rounded-[var(--ui-radius-lg)] bg-[var(--ui-surface)] p-6 text-[var(--ui-text)] shadow-xl"><div className="flex items-start justify-between gap-3"><h2 id={titleId} className="text-xl font-semibold">{title}</h2><button ref={closeRef} onClick={onClose} aria-label="Close dialog" className={clsx('rounded-lg px-3 py-2 text-xl',focus)}>×</button></div>{description&&<p id={descId} className="mt-2 text-sm text-[var(--ui-muted)]">{description}</p>}<div className="mt-4">{children}</div></div></div>
}

import { ReactNode } from "react";

type SectionCardProps = {
  title?: string;
  subtitle?: string;
  rightSlot?: ReactNode;
  children: ReactNode;
  className?: string;
};

export function SectionCard({ title, subtitle, rightSlot, children, className = "" }: SectionCardProps) {
  return (
    <section
      className={`rounded-2xl border border-white/10 bg-slate-900/70 p-5 shadow-[0_8px_30px_rgba(8,18,35,0.35)] backdrop-blur ${className}`.trim()}
    >
      {(title || subtitle || rightSlot) && (
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            {title ? <h2 className="text-base font-semibold text-slate-100">{title}</h2> : null}
            {subtitle ? <p className="mt-1 text-xs text-slate-400">{subtitle}</p> : null}
          </div>
          {rightSlot}
        </div>
      )}
      {children}
    </section>
  );
}

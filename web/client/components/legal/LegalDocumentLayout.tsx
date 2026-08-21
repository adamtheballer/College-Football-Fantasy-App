import { useEffect, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { PublicLegalLinks } from "@/components/legal/PublicLegalLinks";

type LegalDocumentLayoutProps = {
  title: string;
  description: string;
  children: ReactNode;
};

const LAST_UPDATED = "August 20, 2026";

export function LegalDocumentLayout({ title, description, children }: LegalDocumentLayoutProps) {
  useEffect(() => {
    document.title = `${title} | College Football Fantasy`;
    let descriptionElement = document.querySelector<HTMLMetaElement>('meta[name="description"]');
    if (!descriptionElement) {
      descriptionElement = document.createElement("meta");
      descriptionElement.name = "description";
      document.head.appendChild(descriptionElement);
    }
    descriptionElement.content = description;
  }, [description, title]);

  return (
    <div className="min-h-screen bg-cfb-canvas text-cfb-text-primary print:bg-white print:text-black">
      <header className="border-b border-cfb-border-subtle print:border-slate-300">
        <div className="mx-auto flex w-full max-w-5xl items-center justify-between gap-4 px-5 py-5 sm:px-8">
          <Link
            to="/"
            className="font-ui text-sm font-black uppercase tracking-[0.12em] text-cfb-text-primary transition-colors hover:text-cfb-brand print:text-black"
          >
            College Football Fantasy
          </Link>
          <Link
            to="/"
            className="text-sm font-semibold text-cfb-text-secondary transition-colors hover:text-cfb-text-primary print:text-slate-700"
          >
            Back to College Football Fantasy
          </Link>
        </div>
      </header>

      <main className="mx-auto w-full max-w-4xl px-5 py-10 sm:px-8 sm:py-14">
        <article className="mx-auto max-w-3xl">
          <header className="border-b border-cfb-border-subtle pb-8 print:border-slate-300">
            <p className="font-ui text-xs font-black uppercase tracking-[0.18em] text-cfb-brand print:text-slate-700">
              College Football Fantasy
            </p>
            <h1 className="mt-3 text-4xl font-bold tracking-[-0.03em] text-cfb-text-primary sm:text-5xl print:text-black">
              {title}
            </h1>
            <p className="mt-4 text-base leading-7 text-cfb-text-secondary print:text-slate-700">Last updated: {LAST_UPDATED}</p>
            <div className="mt-6 text-sm font-semibold text-cfb-text-secondary print:text-slate-700">
              <PublicLegalLinks className="justify-start" />
            </div>
          </header>

          <div className="space-y-9 py-9 text-base leading-7 text-cfb-text-secondary print:text-slate-800">
            {children}
          </div>
        </article>
      </main>

      <footer className="border-t border-cfb-border-subtle print:border-slate-300">
        <div className="mx-auto flex w-full max-w-5xl flex-col gap-3 px-5 py-6 text-sm text-cfb-text-muted sm:flex-row sm:items-center sm:justify-between sm:px-8 print:text-slate-700">
          <p>© 2026 College Football Fantasy</p>
          <PublicLegalLinks />
        </div>
      </footer>
    </div>
  );
}

export function LegalSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section aria-labelledby={`legal-${title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`}>
      <h2
        id={`legal-${title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`}
        className="font-ui text-xl font-black uppercase tracking-[0.06em] text-cfb-text-primary print:text-black"
      >
        {title}
      </h2>
      <div className="mt-3 space-y-4">{children}</div>
    </section>
  );
}

export function LegalList({ children }: { children: ReactNode }) {
  return <ul className="list-disc space-y-2 pl-5 marker:text-cfb-brand print:marker:text-slate-700">{children}</ul>;
}

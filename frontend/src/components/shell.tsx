'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import './shell.css';
const pages = [
  ['/', 'Refine'],
  ['/knowledge', 'Knowledge'],
  ['/activity', 'Activity'],
  ['/settings', 'Settings'],
];
export function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const current =
    pages.find(([href]) => (href === '/' ? path === '/' : path.startsWith(href)))?.[1] || 'Refine';
  return (
    <div className="shell">
      <aside className="sidebar">
        <Link href="/" className="brand" aria-label="Prompt Enhance home">
          <b>pe.</b>
          <span>
            Prompt{' '}
            <br />
            Enhance
          </span>
        </Link>
        <nav aria-label="Main navigation">
          {pages.map(([href, label], index) => (
            <Link
              href={href}
              key={href}
              aria-current={current === label ? 'page' : undefined}
              className={`nav-item ${current === label ? 'active' : ''}`}
            >
              <span className="num">0{index + 1}</span>
              {label}
            </Link>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <span className="workspace-dot" />
          Personal<span className="version">V 0.1</span>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <span>
            Prompt Enhance <span className="slash">/</span>
            {current}
          </span>
        </header>
        <main id="main-content">{children}</main>
      </div>
    </div>
  );
}

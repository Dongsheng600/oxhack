import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
export function cn(...inputs: Parameters<typeof clsx>) {
  return twMerge(clsx(...inputs));
}
export function Button({
  className,
  primary,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { primary?: boolean }) {
  return <button type="button" className={cn(primary && 'primary', className)} {...props} />;
}
export function Pill({
  children,
  error = false,
  green = false,
}: {
  children: React.ReactNode;
  error?: boolean;
  green?: boolean;
}) {
  return (
    <span className={cn('pill', error && 'error', green && 'green')}>
      {green && <span className="dot" />}
      {children}
    </span>
  );
}
export function Heading({
  children,
  action,
}: {
  children: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className="page-heading">
      <h1>{children}</h1>
      {action}
    </div>
  );
}
export function Panel({
  title,
  meta,
  children,
  className,
}: {
  title?: string;
  meta?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={cn('panel', className)}>
      {title && (
        <div className="panel-head">
          <h2 className="eyebrow">{title}</h2>
          {meta}
        </div>
      )}
      {children}
    </section>
  );
}
export function Tags({ tags }: { tags: string[] }) {
  return (
    <div className="tag-list">
      {tags.map((tag) => (
        <span className="tag" key={tag}>
          {tag}
        </span>
      ))}
    </div>
  );
}
export function ErrorState({ message, retry }: { message: string; retry?: () => void }) {
  return (
    <div className="error-state" role="alert">
      <p>{message}</p>
      {retry && <Button onClick={retry}>Retry</Button>}
    </div>
  );
}
export function Loading({ children = 'Loading…' }: { children?: React.ReactNode }) {
  return (
    <div className="no-results" role="status">
      {children}
    </div>
  );
}
export function Footer({ left, right }: { left: React.ReactNode; right?: React.ReactNode }) {
  return (
    <div className="footer-line">
      <span>{left}</span>
      <span>{right}</span>
    </div>
  );
}

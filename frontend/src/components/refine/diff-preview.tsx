import { Fragment } from 'react';
import { validateEdits } from '@/lib/edits';
import type { Edit } from '@/lib/types';
export function DiffPreview({
  prompt,
  revision,
  edits,
}: {
  prompt: string;
  revision: number;
  edits: Edit[];
}) {
  const sorted = validateEdits(prompt, edits);
  return (
    <div className="diff-content">
      <div className="diff-block">
        <div className="diff-label">Original · Revision {revision}</div>
        {prompt}
      </div>
      <div className="diff-block diff-divider">
        <div className="diff-label">Proposed</div>
        {sorted.map((edit, index) => (
          <Fragment key={index}>
            {prompt.slice(index ? sorted[index - 1].end : 0, edit.start)}
            {edit.end > edit.start && (
              <div className="diff-remove">
                <b>− Removed</b>
                {prompt.slice(edit.start, edit.end)}
              </div>
            )}
            {edit.text && (
              <div className="diff-add">
                <b>+ Added</b>
                {edit.text}
              </div>
            )}
          </Fragment>
        ))}
        {prompt.slice(sorted.at(-1)!.end)}
      </div>
    </div>
  );
}

'use client';
import { useState, useSyncExternalStore } from 'react';
import { useTheme } from 'next-themes';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { api, errorMessage } from '@/lib/api';
import type { ModelRole, Settings as SettingsData } from '@/lib/types';
import { Button, ErrorState, Heading, Loading, Panel, Pill } from '@/components/ui';
import '../knowledge/knowledge.css';
const subscribeHydration = () => () => {};
const roles: ModelRole[] = ['extraction', 'relevance', 'generation', 'summary'];
function Models({ data }: { data: SettingsData }) {
  const client = useQueryClient(),
    [models, setModels] = useState(data.models);
  const save = useMutation({
    mutationFn: () =>
      api<SettingsData>('/settings', {
        method: 'PATCH',
        body: JSON.stringify({
          models: Object.fromEntries(roles.map((role) => [role, models[role]])),
        }),
      }),
    onSuccess: (value) => {
      client.setQueryData(['settings'], value);
      setModels(value.models);
      toast.success('Model settings saved');
    },
  });
  return (
    <Panel title="Models">
      <form
        onSubmit={(event) => {
          event.preventDefault();
          save.mutate();
        }}
      >
        {roles.map((role) => (
          <div className="setting-row" key={role}>
            <label htmlFor={`model-${role}`} className="capitalize">
              {role}
            </label>
            <input
              id={`model-${role}`}
              required
              value={models[role]}
              disabled={save.isPending}
              onChange={(event) => setModels({ ...models, [role]: event.target.value })}
            />
          </div>
        ))}
        <div className="setting-row">
          <span>
            Embedding<small>{data.embedding_dimensions} dimensions · Read only</small>
          </span>
          <span className="mono break-all">{data.models.embedding}</span>
        </div>
        {save.isError && <ErrorState message={errorMessage(save.error)} />}
        <div className="panel-body">
          <Button
            primary
            type="submit"
            disabled={
              save.isPending ||
              !roles.every((role) => models[role].trim()) ||
              roles.every((role) => models[role] === data.models[role])
            }
          >
            {save.isPending ? 'Saving…' : 'Save models'}
          </Button>
        </div>
      </form>
    </Panel>
  );
}
export function Settings() {
  const { theme, setTheme } = useTheme(),
    mounted = useSyncExternalStore(
      subscribeHydration,
      () => true,
      () => false,
    );
  const query = useQuery({
      queryKey: ['settings'],
      queryFn: ({ signal }) => api<SettingsData>('/settings', { signal }),
    }),
    data = query.data;
  return (
    <>
      <Heading>Settings</Heading>
      <div className="settings-grid">
        <div className="stack">
          <Panel title="Appearance">
            <div className="setting-row">
              <label htmlFor="theme">Theme</label>
              <select
                id="theme"
                value={mounted ? theme : 'system'}
                onChange={(event) => setTheme(event.target.value)}
              >
                <option value="light">Light</option>
                <option value="dark">Dark</option>
                <option value="system">System</option>
              </select>
            </div>
          </Panel>
          {query.isPending ? (
            <Loading />
          ) : query.isError ? (
            <ErrorState message={errorMessage(query.error)} retry={() => void query.refetch()} />
          ) : (
            data && (
              <>
                <Panel title="Providers">
                  {(
                    [
                      ['gemini', 'Gemini', 'Tags · embeddings · relevance · generation'],
                      ['database', 'Tiger Data', 'Knowledge · vectors · events'],
                      ['snowflake', 'Snowflake', 'Outcome classifier'],
                    ] as const
                  ).map(([key, name, description]) => (
                    <div className="setting-row" key={key}>
                      <div>
                        {name}
                        <small>{description}</small>
                      </div>
                      <span className="provider-status">
                        {data.providers[key].configured
                          ? data.providers[key].status
                          : 'Not configured'}
                      </span>
                    </div>
                  ))}
                </Panel>
                <Panel title="Logging" meta={<Pill green>Approved</Pill>}>
                  <div className="setting-row">
                    <span>API & AI calls</span>
                    <strong>
                      {data.logging.mode === 'metadata_only' ? 'Metadata only' : data.logging.mode}
                    </strong>
                  </div>
                  <div className="setting-row">
                    <span>Retention</span>
                    <strong>{data.logging.retention_days} days</strong>
                  </div>
                  <div className="setting-row">
                    <span>Payloads & credentials</span>
                    <strong>{data.logging.payloads ? 'Enabled' : 'Excluded'}</strong>
                  </div>
                </Panel>
                <Models data={data} />
              </>
            )
          )}
        </div>
        <div className="stack">
          <Panel title="Codex integration">
            <div className="panel-body">
              <dl className="settings-note">
                <dt>Editor</dt>
                <dd>Separate refinement panel</dd>
                <dt>Handoff</dt>
                <dd>Copy prompt</dd>
                <dt>Composer access</dt>
                <dd>Not verified</dd>
                <dt>Plugin transport</dt>
                <dd>MCP · Separate server</dd>
              </dl>
            </div>
          </Panel>
          {data && (
            <Panel title="Outcome classifier" meta={<Pill>{data.classifier.status}</Pill>}>
              <div className="panel-body facts">
                <div className="fact">
                  <span>Labeled outcomes</span>
                  <span className="mono">{data.classifier.labeled_outcomes}</span>
                </div>
                <div className="fact">
                  <span>Model version</span>
                  <span>{data.classifier.model_version || '—'}</span>
                </div>
              </div>
            </Panel>
          )}
        </div>
      </div>
    </>
  );
}

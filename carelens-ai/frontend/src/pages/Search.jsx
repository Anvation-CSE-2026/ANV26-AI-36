import { useCallback, useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../api/client.js';
import { Async, Chip, EmptyState, Field, PageHeader, SelectField } from '../components/ui.jsx';
import { formatDate, useResource } from '../hooks.js';
import { T } from '../components/T.jsx';
import { tr } from '../i18n.js';

const TYPES = { document: 'Document', medicine: 'Medicine', timeline: 'Timeline', health: 'Health' };

export default function Search() {
  const [params, setParams] = useSearchParams();
  const q = params.get('q') ?? '';
  const type = params.get('type') ?? '';
  const [text, setText] = useState(q);
  useEffect(() => setText(q), [q]);
  const loader = useCallback(() => (q.trim().length > 1 ? api.search(q, type) : Promise.resolve({ items: [] })), [q, type]);
  const res = useResource(loader);
  const items = res.data?.items ?? [];
  const set = (patch) => { const n = new URLSearchParams(params); Object.entries(patch).forEach(([k, v]) => (v ? n.set(k, v) : n.delete(k))); setParams(n); };
  return (
    <>
      <PageHeader title={tr("Search")}><T>Find documents, medicines, timeline events and health information — yours, and what family members have shared with you.</T></PageHeader>
      <form className="search-row" onSubmit={(e) => { e.preventDefault(); set({ q: text.trim() }); }}>
        <Field label={tr("Search")} value={text} onChange={(e) => setText(e.target.value)} autoFocus />
        <SelectField label={tr("Type")} value={type} onChange={(e) => set({ type: e.target.value })}><option value=""><T>Everything</T></option>{Object.entries(TYPES).map(([k, v]) => <option key={k} value={k}>{v}s</option>)}</SelectField>
      </form>
      {q.trim().length < 2 ? <div className="card"><EmptyState compact title={tr("Type at least two letters to search.")} /></div> : (
        <Async res={res} isEmpty={items.length === 0} empty={<div className="card"><EmptyState compact icon="search" title={tr("No results")}>Nothing matched “{q}”.</EmptyState></div>}>
          <div className="card"><ul className="docs">{items.map((r) => (
            <li key={`${r.type}-${r.id}-${r.link}`} className="doc-row"><div className="doc-body"><p className="doc-name"><Link to={r.link}>{r.title}</Link></p>
              {r.snippet && <p className="muted doc-meta">{r.snippet}</p>}</div>
              <Chip>{TYPES[r.type]}</Chip>{r.member !== 'You' && <Chip tone="ok">From {r.member}</Chip>}{r.date && <span className="muted doc-meta">{formatDate(r.date)}</span>}</li>))}</ul></div>
        </Async>
      )}
    </>
  );
}

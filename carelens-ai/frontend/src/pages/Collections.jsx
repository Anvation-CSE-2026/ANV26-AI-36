import { Link } from 'react-router-dom';
import { api } from '../api/client.js';
import { AddDocumentButton, DocumentList } from '../components/Documents.jsx';
import { Async, Chip, EmptyState, PageHeader } from '../components/ui.jsx';
import { formatDate, usePolling, useResource } from '../hooks.js';
import { T } from '../components/T.jsx';
import { tr } from '../i18n.js';

export function Documents() {
  const res = useResource(api.documents);
  const items = res.data?.items ?? [];
  usePolling(items.some((d) => ['uploaded', 'processing'].includes(d.processing_status)), res.reload);
  return (
    <>
      <div className="page-head">
        <div><h1 className="h1"><T>Documents</T></h1><p className="lede"><T>Your medical papers, read and organised. Private to you unless you share them.</T></p></div>
        {res.status === 'ready' && items.length > 0 && <AddDocumentButton onUploaded={res.reload} />}
      </div>
      <div className="card">
        <Async res={res} isEmpty={items.length === 0} empty={
          <EmptyState icon="file" title={tr("No documents yet.")} action={<AddDocumentButton onUploaded={res.reload} />}><T>PDF, JPG or PNG, up to 10 MB. Only you can see what you add.</T></EmptyState>}>
          <DocumentList items={items} onChanged={res.reload} />
        </Async>
      </div>
    </>
  );
}

const FLAG = { below: ['Below printed range', 'warn'], above: ['Above printed range', 'warn'], within: ['Within printed range', 'ok'] };

export function Knowledge() {
  const res = useResource(api.knowledge);
  const items = res.data?.items ?? [];
  const groups = Object.values(items.reduce((acc, r) => {
    (acc[r.document_id] ??= { id: r.document_id, filename: r.filename, date: r.uploaded_at, rows: [] }).rows.push(r);
    return acc;
  }, {}));
  return (
    <>
      <PageHeader title={tr("Key results")}><T>Values found in your documents, exactly as printed.</T></PageHeader>
      <Async res={res} isEmpty={items.length === 0} empty={<div className="card"><EmptyState icon="book" title={tr("Your important information will appear here.")}><T>Results are listed once a document has been read.</T></EmptyState></div>}>
        <div className="stack-lg">
          {groups.map((g) => (
            <section key={g.id} className="card">
              <div className="section-head"><h2 className="h3"><Link to={`/documents/${g.id}`}>{g.filename}</Link></h2><span className="muted push">{formatDate(g.date)}</span></div>
              <FindingsTable rows={g.rows} />
            </section>
          ))}
        </div>
      </Async>
    </>
  );
}

export function FindingsTable({ rows }) {
  return (
    <div className="table-wrap">
      <table className="table">
        <thead><tr><th><T>Test</T></th><th><T>Result</T></th><th><T>Printed range</T></th><th /></tr></thead>
        <tbody>{rows.map((r, i) => (
          <tr key={r.id ?? i}>
            <td>{r.label}</td><td>{r.value} {r.unit}</td><td className="muted">{r.reference_range ?? '—'}</td>
            <td>{r.flag && <Chip tone={FLAG[r.flag][1]}>{FLAG[r.flag][0]}</Chip>}</td>
          </tr>
        ))}</tbody>
      </table>
    </div>
  );
}

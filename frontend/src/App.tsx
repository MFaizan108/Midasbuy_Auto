import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  BrowserRouter,
  Link,
  Route,
  Routes,
  useParams,
} from 'react-router-dom';
import {
  Activity,
  Settings,
  Users,
  History,
  ScrollText,
  Zap,
  Plus,
  Search,
} from 'lucide-react';
import { api, API } from './services/api';
import './style.css';

type Account = {
  id: number;
  display_name: string;
  status?: string;
  login_status?: string;
  browser_running?: boolean;
  enabled?: boolean;
  total_runs: number;
  successful_runs: number;
  failed_runs: number;
  last_error?: string;
};

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="app">
      <aside>
        <div className="brand">
          <div className="logo">M</div>
          <div>
            <b>MIDASBUY</b>
            <span>Local Automation</span>
          </div>
        </div>

        <nav>
          {[
            ['/dashboard', Activity, 'Dashboard'],
            ['/accounts', Users, 'Accounts'],
            ['/tasks', Zap, 'Tasks'],
            ['/history', History, 'History'],
            ['/logs', ScrollText, 'Logs'],
            ['/settings', Settings, 'Settings'],
          ].map(([to, I, l]: any) => (
            <Link key={to} to={to}>
              <I size={18} />
              {l}
            </Link>
          ))}
        </nav>

        <div className="local">
          <span className="dot"></span>
          Local System Online
        </div>
      </aside>

      <main>{children}</main>
    </div>
  );
}

const Badge = ({ s = 'UNKNOWN' }: { s?: string | null }) => {
  const safeStatus = String(s || 'UNKNOWN');

  const labels: { [key: string]: string } = {
    READY: 'Authenticated',
    AUTHENTICATING: 'Awaiting user login',
    NOT_AUTHENTICATED: 'Not authenticated',
    RE_LOGIN_REQUIRED: 'Login required',
    WAITING_FOR_USER: 'Awaiting user login',
    UNKNOWN: 'Unknown',
  };

  return (
    <span className={'badge ' + safeStatus.toLowerCase()}>
      {labels[safeStatus] || safeStatus.replace(/_/g, ' ')}
    </span>
  );
};

function Dashboard() {
  const [acc, setAcc] = useState<Account[]>([]);
  const [link, setLink] = useState('');
  const [sel, setSel] = useState<number[]>([]);
  const [task, setTask] = useState<any>(null);
  const [events, setEvents] = useState<any[]>([]);
  const [selectionMode, setSelectionMode] = useState(false);

  useEffect(() => {
    api.accounts().then(setAcc);
  }, []);

  const ready = acc.filter(
    (a) => a.status === 'READY' && a.login_status === 'CONNECTED' && a.enabled
  );

  const linkEvents = events.filter((e) => e.type === 'link');
  const progress = events.find((e) => e.type === 'progress');

  function toggle(id: number) {
    setSel((current) =>
      current.includes(id)
        ? current.filter((accountId) => accountId !== id)
        : [...current, id]
    );
  }

  async function run() {
    const t = await api.createTask(link, sel);
    setTask(t);
    setEvents([]);

    const es = new EventSource(`${API}/tasks/${t.id}/events`);

    es.onmessage = (e) =>
      setEvents((x) => [JSON.parse(e.data), ...x].slice(0, 100));
  }

  return (
    <>
      <Header title="Midasbuy Automation" sub="Local • Connected" />

      <div className="stats">
        <Card k="Total Accounts" v={acc.length} />
        <Card k="Ready Accounts" v={ready.length} />
        <Card k="Running Tasks" v={task ? 1 : 0} />
        <Card
          k="Success Rate"
          v={
            (
              (acc.reduce((s, a) => s + a.successful_runs, 0) /
                Math.max(1, acc.reduce((s, a) => s + a.total_runs, 0))) *
              100
            ).toFixed(0) + '%'
          }
        />
      </div>

      <section className="hero">
        <h2>Help & Draw Control Center</h2>

        <label>Automation Link</label>
        <input
          value={link}
          onChange={(e) => setLink(e.target.value)}
          placeholder="Paste Midasbuy link here..."
        />

        <div className="panel">
          <h3>Authenticated Accounts</h3>

          {selectionMode &&
            ready.map((account) => (
              <label
                key={account.id}
                className="row"
                style={{ justifyContent: 'flex-start', minHeight: 36 }}
              >
                <input
                  type="checkbox"
                  checked={sel.includes(account.id)}
                  onChange={() => toggle(account.id)}
                />
                <span>Account {String(account.id).padStart(3, '0')}</span>
                <Badge s={account.status} />
              </label>
            ))}

          {!selectionMode && (
            <p>{ready.length} authenticated accounts available</p>
          )}

          {!ready.length && <p>No authenticated accounts available</p>}
        </div>

        <div className="row">
          <button onClick={() => setSel(ready.map((a) => a.id))}>
            Select Ready
          </button>
          <button onClick={() => setSelectionMode(true)}>Select Accounts</button>
          <button onClick={() => setSel([])}>Clear</button>
          <b>{sel.length} accounts selected</b>
        </div>

        <button className="cta" onClick={run} disabled={!link || !sel.length}>
          HELP & DRAW
        </button>
      </section>

      {task && (
        <section className="panel">
          <h3>Batch Progress</h3>

          <p>
            {progress?.success || 0} successful, {progress?.failed || 0} failed,{' '}
            {progress?.progress || 0}% complete
          </p>

          <div className="bar">
            <i style={{ width: (progress?.progress || 0) + '%' }} />
          </div>

          {linkEvents.map((event, i) => (
            <p key={event.link_id || i}>
              Account {event.account_id}: {event.status}
              {event.error ? ' • ' + event.error : ''}
            </p>
          ))}

          {events.find((e) => e.type === 'task') && (
            <p>
              Final batch status:{' '}
              {events.find((e) => e.type === 'task').status}
            </p>
          )}
        </section>
      )}
    </>
  );
}

function Card(p: any) {
  return (
    <div className="card">
      <span>{p.k}</span>
      <strong>{p.v}</strong>
    </div>
  );
}

function Header(p: any) {
  return (
    <header>
      <div>
        <h1>{p.title}</h1>
        <p>{p.sub}</p>
      </div>

      <button>System Status</button>
    </header>
  );
}

function Accounts() {
  const [a, setA] = useState<Account[]>([]);
  const [q, setQ] = useState('');

  const load = () => {
    api.accounts().then(setA);
  };

  useEffect(() => {
    load();
  }, []);

  const list = a.filter((x) =>
    (
      (x.display_name || '') +
      x.id +
      (x.status || '')
    )
      .toLowerCase()
      .includes(q.toLowerCase())
  );

  return (
    <>
      <Header title="Accounts" sub="Persistent isolated browser sessions" />

      <div className="toolbar">
        <div className="search">
          <Search size={16} />
          <input
            placeholder="Search accounts"
            onChange={(e) => setQ(e.target.value)}
          />
        </div>

        <button
          className="primary"
          onClick={async () => {
            await api.addAccount('Midasbuy Account');
            load();
          }}
        >
          <Plus size={16} />
          Add Account
        </button>
      </div>

      <div className="table">
        {list.map((x) => (
          <div key={x.id} className="tr">
            <b>account_{String(x.id).padStart(3, '0')}</b>
            <span>{x.display_name}</span>
            <Badge s={x.status} />
            <span>{x.total_runs} runs</span>

            <button
              onClick={async () => {
                await api.login(x.id);
                load();
              }}
            >
              Login
            </button>

            <button
              onClick={async () => {
                await api.test(x.id);
                load();
              }}
            >
              Test
            </button>
          </div>
        ))}
      </div>

      {!list.length && (
        <div className="empty">
          No accounts yet
          <br />
          <button onClick={() => api.addAccount('Midasbuy Account').then(load)}>
            + Add Account
          </button>
        </div>
      )}
    </>
  );
}

function Tasks() {
  const [t, setT] = useState<any[]>([]);

  useEffect(() => {
    api.tasks().then(setT);
  }, []);

  const activeTasks = t.filter((x) =>
    ['QUEUED', 'RUNNING', 'PAUSED'].includes(x.status)
  );

  const completedTasks = t.filter((x) =>
    ['COMPLETED', 'FAILED', 'CANCELLED'].includes(x.status)
  );

  return (
    <>
      <Header title="Tasks" sub="Active & queued tasks" />

      <div className="table">
        {activeTasks.map((x) => (
          <Link key={x.id} className="tr" to={'/tasks/' + x.id}>
            <b>Task #{x.id}</b>
            <span>{x.link}</span>
            <Badge s={x.status} />
            <span>
              {x.success_count}/{x.total_count} success
            </span>
          </Link>
        ))}
      </div>

      {completedTasks.length > 0 && (
        <>
          <h3 style={{ marginTop: 24, marginBottom: 12 }}>Completed Tasks</h3>

          <div className="table">
            {completedTasks.map((x) => (
              <Link key={x.id} className="tr" to={'/tasks/' + x.id}>
                <b>Task #{x.id}</b>
                <span>{x.link}</span>
                <Badge s={x.status} />
                <span>
                  {x.success_count}/{x.total_count} success
                </span>
              </Link>
            ))}
          </div>
        </>
      )}
    </>
  );
}

function TaskDetail() {
  const { id } = useParams();
  const [t, setT] = useState<any>();

  useEffect(() => {
    api.task(id!).then(setT);
  }, [id]);

  return (
    <>
      <Header title={'Task #' + id} sub="Account-level results" />

      {t && (
        <div className="panel">
          <div className="task-stats">
            <div className="stat">
              <span className="label">Total Accounts</span>
              <strong>{t.task.total_count}</strong>
            </div>

            <div className="stat">
              <span className="label">Successful</span>
              <strong style={{ color: '#22c55e' }}>
                {t.task.success_count}
              </strong>
            </div>

            <div className="stat">
              <span className="label">Failed</span>
              <strong style={{ color: '#ef4444' }}>
                {t.task.failure_count}
              </strong>
            </div>

            <div className="stat">
              <span className="label">Progress</span>
              <strong>{t.task.progress}%</strong>
            </div>
          </div>

          <div className="bar">
            <i style={{ width: t.task.progress + '%' }} />
          </div>

          <div className="task-accounts">
            <h4>Account Results</h4>

            {t.accounts?.map((acc: any) => (
              <div key={acc.account_id} className="account-row">
                <span>Account {String(acc.account_id).padStart(3, '0')}</span>
                <Badge s={acc.status} />
                <span>{acc.error || ''}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}

function Logs() {
  const [l, setL] = useState<any[]>([]);
  const [filter, setFilter] = useState('all');
  const [autoRefresh, setAutoRefresh] = useState(true);

  useEffect(() => {
    api.logs().then(setL);
  }, []);

  useEffect(() => {
    if (!autoRefresh) return;

    const id = setInterval(() => api.logs().then(setL), 5000);

    return () => clearInterval(id);
  }, [autoRefresh]);

  const filtered = l.filter(
    (x) =>
      filter === 'all' ||
      String(x.level || '').toUpperCase() === filter.toUpperCase()
  );

  return (
    <>
      <Header title="Logs" sub="Operational events" />

      <div className="toolbar">
        <select value={filter} onChange={(e) => setFilter(e.target.value)}>
          <option value="all">All Levels</option>
          <option value="info">INFO</option>
          <option value="warning">WARNING</option>
          <option value="error">ERROR</option>
          <option value="debug">DEBUG</option>
        </select>

        <label>
          <input
            type="checkbox"
            checked={autoRefresh}
            onChange={(e) => setAutoRefresh(e.target.checked)}
          />{' '}
          Auto-refresh (5s)
        </label>

        <button onClick={() => api.logs().then(setL)}>Refresh Now</button>
      </div>

      <div className="panel">
        {filtered.map((x, index) => (
          <p
            key={x.id || index}
            style={{
              margin: 8,
              padding: 8,
              background: '#1e1e1e',
              borderRadius: 4,
            }}
          >
            <Badge s={x.level} /> {x.message || ''}
          </p>
        ))}
      </div>

      {!filtered.length && <div className="empty">No logs found</div>}
    </>
  );
}

function SettingsPage() {
  const [s, setS] = useState<any>();
  const [draft, setDraft] = useState<any>();
  const [saving, setSaving] = useState(false);
  const [accounts, setAccounts] = useState<any[]>([]);
  const [showDeleteModal, setShowDeleteModal] = useState<{
    id: number;
    name: string;
  } | null>(null);
  const [loading, setLoading] = useState(false);
  const [toasts, setToasts] = useState<{ id: number; text: string; type?: string }[]>([]);

  const showToast = (text: string, type = 'info') => {
    const id = Date.now() + Math.floor(Math.random() * 1000);
    setToasts((t: any) => [...t, { id, text, type }]);
    setTimeout(() => setToasts((t) => t.filter((x: any) => x.id !== id)), 4000);
  };

  useEffect(() => {
    api.settings().then((cfg) => {
      setS(cfg);
      setDraft(cfg);
    });
  }, []);

  useEffect(() => {
    api.accounts().then(setAccounts);
  }, []);

  const handleDelete = async (id: number) => {
    setLoading(true);
    try {
      await api.j(`/accounts/${id}`, { method: 'DELETE' });
      // Refresh accounts to reflect server state and ensure UI consistency
      setAccounts(await api.accounts());
      setShowDeleteModal(null);
    } catch (err) {
      console.error(err);
      showToast('Failed to delete account', 'error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Header title="Settings" sub="Configuration & Account Management" />

      <section className="panel" style={{ marginBottom: 24 }}>
        <h3>Automation Settings</h3>

        {/* Use a draft object so changes aren't sent immediately — user can confirm */}
        <div className="settings-grid">
          <div className="setting-item">
            <label>Concurrency (Parallel Workers)</label>
            <input
              type="number"
              min={1}
              max={200}
              value={draft?.concurrency ?? s?.concurrency ?? 3}
              onChange={(e) =>
                setDraft({ ...draft, concurrency: Math.max(1, parseInt(e.target.value || '1')) })
              }
            />
            <input
              type="range"
              min={1}
              max={200}
              value={draft?.concurrency ?? s?.concurrency ?? 3}
              onChange={(e) => setDraft({ ...draft, concurrency: parseInt(e.target.value || '1') })}
              style={{ width: '100%' }}
            />
            <small>Number of accounts to process simultaneously</small>
          </div>

          <div className="setting-item">
            <label>Mock Mode</label>
            <select
              value={(draft?.mock_mode ?? s?.mock_mode) === 'true' ? 'true' : 'false'}
              onChange={(e) => setDraft({ ...draft, mock_mode: e.target.value === 'true' })}
            >
              <option value="false">Disabled (Real Automation)</option>
              <option value="true">Enabled (Testing)</option>
            </select>
            <small>Run without actual browser automation</small>
          </div>

          <div className="setting-item">
            <label>Default Timeout (seconds)</label>
            <input
              type="number"
              min={10}
              max={300}
              value={draft?.timeout ?? s?.timeout ?? 60}
              onChange={(e) => setDraft({ ...draft, timeout: Math.max(10, parseInt(e.target.value || '10')) })}
            />
            <small>Maximum wait time for page operations</small>
          </div>

          <div className="setting-item">
            <label>Retry Attempts</label>
            <input
              type="number"
              min={0}
              max={5}
              value={draft?.retries ?? s?.retries ?? 2}
              onChange={(e) => setDraft({ ...draft, retries: Math.max(0, parseInt(e.target.value || '0')) })}
            />
            <small>Number of retries for failed operations</small>
          </div>

          <div className="setting-item">
            <label>Headless Browser</label>
            <select
              value={(draft?.headless ?? s?.headless) === 'true' ? 'true' : 'false'}
              onChange={(e) => setDraft({ ...draft, headless: e.target.value === 'true' })}
            >
              <option value="false">Visible Browser</option>
              <option value="true">Headless (Faster)</option>
            </select>
            <small>Run browser without visible UI</small>
          </div>

          <div className="setting-item">
            <label>Log Level</label>
            <select
              value={draft?.log_level ?? s?.log_level ?? 'info'}
              onChange={(e) => setDraft({ ...draft, log_level: e.target.value })}
            >
              <option value="debug">DEBUG</option>
              <option value="info">INFO</option>
              <option value="warning">WARNING</option>
              <option value="error">ERROR</option>
            </select>
            <small>Minimum log level to record</small>
          </div>
        </div>

        <div style={{ marginTop: 12, display: 'flex', gap: 8 }}>
          <button
            onClick={() => {
              setDraft(s);
            }}
            disabled={!s || saving}
          >
            Cancel
          </button>

          <button
            className="primary"
            onClick={async () => {
              setSaving(true);
              try {
                await api.putSettings(draft || s);
                setS(draft || s);
                showToast('Settings saved', 'success');
              } catch (err) {
                console.error(err);
                showToast('Failed to save settings', 'error');
              } finally {
                setSaving(false);
              }
            }}
            disabled={saving || JSON.stringify(draft) === JSON.stringify(s)}
          >
            {saving ? 'Saving...' : 'Confirm'}
          </button>
        </div>
      </section>

      <section className="panel">
        <h3>Account Management</h3>

        <div className="toolbar">
          <button
            className="primary"
            onClick={async () => {
              await api.addAccount('Midasbuy Account');
              setAccounts(await api.accounts());
            }}
          >
            <Plus size={16} />
            Add Account
          </button>
        </div>

        <div className="table">
          {accounts.map((acc) => (
            <div key={acc.id} className="tr">
              <b>account_{String(acc.id).padStart(3, '0')}</b>
              <span>{acc.display_name}</span>
              <Badge s={acc.status} />
              <span>
                {acc.total_runs} runs ({acc.successful_runs}✓ {acc.failed_runs}✗)
              </span>
              <span>{acc.enabled ? 'Enabled' : 'Disabled'}</span>

              <button
                onClick={() =>
                  setShowDeleteModal({
                    id: acc.id,
                    name: acc.display_name,
                  })
                }
                style={{
                  background: '#ef4444',
                  color: 'white',
                  border: 'none',
                  padding: '6px 12px',
                  borderRadius: 4,
                  cursor: 'pointer',
                  opacity: loading ? 0.5 : 1,
                }}
                disabled={loading}
              >
                Delete
              </button>
            </div>
          ))}
        </div>

        {!accounts.length && (
          <div className="empty">
            No accounts yet
            <br />
            <button
              onClick={async () => {
                await api.addAccount('Midasbuy Account');
                setAccounts(await api.accounts());
              }}
            >
              + Add Account
            </button>
          </div>
        )}
      </section>

      {showDeleteModal && (
        <div
          className="modal-overlay"
          onClick={() => setShowDeleteModal(null)}
        >
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <Zap size={24} style={{ color: '#ef4444' }} />
              <h3>Delete Account</h3>
            </div>

            <p>
              Are you sure you want to delete{' '}
              <strong>{showDeleteModal.name}</strong> Account{' '}
              <strong>{String(showDeleteModal.id).padStart(3, '0')}</strong>?
            </p>

            <p style={{ color: '#888', fontSize: 14, marginTop: 8 }}>
              This action cannot be undone. The account&apos;s browser profile,
              login session, and all history will be permanently removed.
            </p>

            <div className="modal-actions">
              <button onClick={() => setShowDeleteModal(null)}>Cancel</button>

              <button
                className="danger"
                onClick={() => handleDelete(showDeleteModal.id)}
                disabled={loading}
              >
                {loading ? 'Deleting...' : 'Delete Permanently'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Toasts */}
      <div className="toast-container">
        {toasts.map((t) => (
          <div key={t.id} className={"toast " + (t.type || 'info')}>
            {t.text}
          </div>
        ))}
      </div>
    </>
  );
}

function App() {
  return (
    <BrowserRouter>
      <Shell>
        <Routes>
          <Route path="*" element={<Dashboard />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/accounts" element={<Accounts />} />
          <Route path="/tasks" element={<Tasks />} />
          <Route path="/tasks/:id" element={<TaskDetail />} />
          <Route path="/history" element={<Tasks />} />
          <Route path="/logs" element={<Logs />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </Shell>
    </BrowserRouter>
  );
}

createRoot(document.getElementById('root')!).render(<App />);
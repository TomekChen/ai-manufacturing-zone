import React, { useState, useEffect, useCallback } from 'react';
import ReactDOM from 'react-dom/client';
import './style.css';
import ArchitectureDiagram from './ArchitectureDiagram';
import KnowledgeQA from './KnowledgeQA';
import LinkFooter from './LinkFooter';
import AdminKB from './AdminKB';
import AdminLinks from './AdminLinks';
import AdminAnalytics from './AdminAnalytics';
import AdminEval from './AdminEval';
import AdminPRD from './AdminPRD';

const API_BASE = '/api';

/* ===== SVG 图标组件 ===== */
const Icon = ({ d, size = 22, color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
    stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d={d} />
  </svg>
);

const ICONS = {
  plus: 'M12 5v14M5 12h14',
  edit: 'M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10',
  trash: 'M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.018-.4-1.505-1.17-1.505H11.28c-.77 0-1.17.487-1.17 1.505V5.79m7.5 0L14.74 9M18 5.79L6 5.79m6 9.19v6',
  close: 'M6 18L18 6M6 6l12 12',
  settings: 'M9.594 3.94c.09-.542-.433-.957-.877-.745L6.47 3.84c-.436-.18-.863.194-.793.655l.36 2.554a.93.93 0 01-.563.9l-2.012.83a.938.938 0 00-.46 1.287l1.32 2.29c.222.384.674.534 1.073.36l2.154-.916c.17-.073.36.008.454.197l.002.003c.272.58.64 1.115 1.09 1.59.146.154.15.397.01.557l-1.52 1.762a.94.94 0 00.12 1.36l2.29 1.32c.384.222.87.117 1.112-.246l.996-1.61c.11-.178.35-.25.544-.167l.005.002c.58.27 1.2.457 1.855.557.21.032.383.186.427.395l.36 2.193c.074.45.5.777.955.706l2.55-.405c.455-.072.77-.49.707-.955l-.405-2.55a.666.666 0 01.395-.427c.655-.1 1.275-.288 1.855-.557.195-.083.435-.011.544.167l.996 1.61c.242.363.728.468 1.112.246l2.29-1.32a.94.94 0 00.12-1.36l-1.52-1.762a.48.48 0 01.01-.557 6.58 6.58 0 001.09-1.59.455.455 0 01.454-.197l2.154.916c.4.173.85.023 1.073-.36l1.32-2.29a.938.938 0 00-.46-1.287l-2.012-.83a.93.93 0 01-.563-.9l.36-2.554c.07-.46-.357-.835-.793-.655L18.11 3.195c-.444-.212-.967.203-.877.745l.5 3.007a.49.49 0 01-.154.472A6.7 6.7 0 0112 12a6.7 6.7 0 01-5.58-2.58.49.49 0 01-.154-.472l.5-3.007z',
  heart: 'M21 8.25c0-2.485-2.099-4.5-4.688-4.5-1.936 0-3.598 1.126-4.312 2.733-.714-1.607-2.376-2.733-4.313-2.733C5.1 3.75 3 5.765 3 8.25c0 7.22 9 12 9 12s9-4.78 9-12z',
  login: 'M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15m3 0l3-3m0 0l-3-3m3 3H9',
  logout: 'M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15M12 12h9m0 0l-3-3m3 3l-3 3',
};

/* 主题色：兼容旧的命名色（blue…）与新的十六进制色，统一转成 hex 供 CSS 变量使用 */
const NAMED_COLORS = {
  blue: '#3b82f6', green: '#22c55e', purple: '#a855f7',
  orange: '#f97316', cyan: '#22d3ee', pink: '#ec4899',
};
function toHex(color) {
  if (!color) return NAMED_COLORS.blue;
  if (color.startsWith('#')) return color;
  return NAMED_COLORS[color] || NAMED_COLORS.blue;
}
// 由主色生成柔和背景（叠加透明度）
function withAlpha(hex, alpha) {
  const h = toHex(hex).replace('#', '');
  const r = parseInt(h.slice(0, 2), 16), g = parseInt(h.slice(2, 4), 16), b = parseInt(h.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

const AGENTS_FALLBACK = [
  {
    emoji: '🔧', color: 'blue', name: '设备医生', role: '预测性维护智能体',
    desc: '7×24 小时监测设备健康状态，通过振动频谱分析和温度趋势预测，提前发现潜在故障。',
    caps: ['振动频谱实时分析', '故障预警提前 7-30 天', '自动生成维护工单', '备件库存智能建议'],
  },
  {
    emoji: '🔍', color: 'green', name: '质量鹰眼', role: 'AI 质检智能体',
    desc: '基于深度学习的视觉检测系统，支持多种缺陷类型的实时识别与分类。',
    caps: ['检测精度 ≥ 99.5%', '支持 20+ 缺陷类型', '毫秒级响应速度', '缺陷趋势统计分析'],
  },
  {
    emoji: '📋', color: 'purple', name: '排产大师', role: '智能排程智能体',
    desc: '多约束优化排产引擎，在交期、产能、物料、成本之间找到最优平衡点。',
    caps: ['排产效率提升 10 倍', '支持 50+ 约束条件', '动态插单快速响应', '产能利用率提升 15%'],
  },
  {
    emoji: '🛡️', color: 'orange', name: '安全卫士', role: '安全监控智能体',
    desc: '融合视频 AI 与 IoT 传感器数据，实时监测人员行为、环境参数和设备状态。',
    caps: ['违规行为实时告警', '环境参数越线预警', '应急预案自动触发', '安全报表自动生成'],
  },
  {
    emoji: '📊', color: 'cyan', name: '数据炼金师', role: '数据分析智能体',
    desc: '打通 ERP、MES、SCADA 等系统数据壁垒，提供全局数据视图和智能洞察。',
    caps: ['多源数据自动融合', '自然语言查询分析', '异常模式自动发现', '管理驾驶舱实时看板'],
  },
  {
    emoji: '⚡', color: 'pink', name: '能效管家', role: '能源优化智能体',
    desc: '实时追踪能耗数据，识别浪费模式，自动调节设备运行参数实现节能降耗。',
    caps: ['能耗降低 20-35%', '峰谷用电智能调度', '碳排放实时核算', '节能方案自动推荐'],
  },
];

/* ===== 数据请求封装 ===== */
async function readError(res) {
  const text = await res.text();
  // 优先尝试解析 JSON 错误
  try {
    const json = JSON.parse(text);
    if (json.error) return json.error;
    if (json.message) return json.message;
  } catch {}
  // 如果返回的是 HTML，提取 <title> 或前段文本，避免显示整个 HTML
  if (text.trim().startsWith('<')) {
    const title = text.match(/<title>([^<]*)<\/title>/i);
    if (title) return title[1].trim();
    return `请求失败（HTTP ${res.status}）`;
  }
  return text || `请求失败（HTTP ${res.status}）`;
}
async function apiGet(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}
async function apiPost(path, body, token) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}${path}`, { method: 'POST', headers, body: JSON.stringify(body) });
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}
async function apiDelete(path, token) {
  const headers = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}${path}`, { method: 'DELETE', headers });
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}
async function apiUpload(file, token) {
  const formData = new FormData();
  formData.append('file', file);
  const headers = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}/admin/upload`, { method: 'POST', headers, body: formData });
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

/* ===== 管理员登录弹窗 ===== */
function AdminLoginModal({ onClose, onLogin }) {
  const [account, setAccount] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true); setError('');
    try {
      const data = await apiPost('/admin/login', { account, password });
      if (data.token) {
        localStorage.setItem('admin_token', data.token);
        onLogin(data.token);
        onClose();
      }
    } catch (err) {
      setError('账号或密码错误');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>管理员入口</h3>
          <button className="icon-btn" onClick={onClose}><Icon d={ICONS.close} size={18} /></button>
        </div>
        <form onSubmit={handleSubmit} className="admin-form">
          <label>账号</label>
          <input type="text" value={account} onChange={(e) => setAccount(e.target.value)} placeholder="请输入管理员账号" required />
          <label>密码</label>
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="请输入管理员密码" required />
          {error && <div className="form-error">{error}</div>}
          <button type="submit" className="btn btn-primary" disabled={loading}>
            {loading ? '登录中...' : '登录'}
          </button>
        </form>
      </div>
    </div>
  );
}

/* ===== 探测结果徽标 ===== */
function ProbeBadge({ res }) {
  const ok = res.alive;
  const detail = ok
    ? (res.status ? `在线 · HTTP ${res.status}` : '在线 · 可达')
    : (res.error || '不可达');
  return (
    <span className={`probe-badge ${ok ? 'ok' : 'fail'}`} title={res.url || ''}>
      <span className="probe-dot"></span>{detail}
    </span>
  );
}

/* ===== 项目管理弹窗 ===== */
function ProjectEditorModal({ project, token, onClose, onSave }) {
  const [name, setName] = useState(project?.name || '');
  const [role, setRole] = useState(project?.role || '');
  const [desc, setDesc] = useState(project?.desc || '');
  const [url, setUrl] = useState(project?.url || '');
  const [heartbeatUrl, setHeartbeatUrl] = useState(project?.heartbeatUrl || '');
  const [image, setImage] = useState(project?.image || '');
  const [preview, setPreview] = useState(project?.image || '');
  const [caps, setCaps] = useState(project?.caps?.join('\n') || '');
  const [color, setColor] = useState(project?.color || 'blue');
  const [uploading, setUploading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState('');
  const [probing, setProbing] = useState(false);
  const [probeResult, setProbeResult] = useState(null); // {target, alive, status, error}

  const handleProbe = async (target) => {
    const u = (target === 'heartbeat' ? (heartbeatUrl || url) : url).trim();
    if (!u) { setProbeResult({ target, alive: false, error: '请先填写地址' }); return; }
    setProbing(true); setProbeResult(null);
    try {
      const res = await apiPost('/admin/probe', { url: u }, token);
      setProbeResult({ target, url: u, ...res });
    } catch (err) {
      setProbeResult({ target, url: u, alive: false, error: err?.message || '探测失败' });
    } finally {
      setProbing(false);
    }
  };

  const handleFileChange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    if (!file.type.startsWith('image/')) {
      alert('请选择图片文件');
      return;
    }
    setPreview(URL.createObjectURL(file));
    setUploading(true);
    try {
      const data = await apiUpload(file, token);
      setImage(data.url);
    } catch (err) {
      alert('图片上传失败：' + err.message);
    } finally {
      setUploading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (uploading) {
      setFormError('图片正在上传中，请稍后再保存');
      return;
    }
    setSaving(true);
    setFormError('');
    try {
      await onSave({
        id: project?.id,
        name,
        role,
        desc,
        url,
        heartbeatUrl,
        image,
        caps: caps.split('\n').map(s => s.trim()).filter(Boolean),
        color,
      });
    } catch (err) {
      setFormError(typeof err === 'string' ? err : (err?.message || '保存失败'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal modal-lg" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>{project ? '编辑项目' : '新增项目'}</h3>
          <button className="icon-btn" onClick={onClose}><Icon d={ICONS.close} size={18} /></button>
        </div>
        <form onSubmit={handleSubmit} className="admin-form">
          <label>项目名称</label>
          <input type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="如：设备医生" required />
          <label>角色/副标题</label>
          <input type="text" value={role} onChange={(e) => setRole(e.target.value)} placeholder="如：预测性维护智能体" required />
          <label>项目介绍</label>
          <textarea value={desc} onChange={(e) => setDesc(e.target.value)} rows={3} placeholder="请输入项目简介" required />
          <label>访问地址（用户点击跳转的地址）</label>
          <input type="url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="如 http://180.127.11.169:21886/" required />
          <div className="field-actions">
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => handleProbe('url')} disabled={probing}>
              <Icon d={ICONS.heart} size={14} /> {probing ? '测试中...' : '测试访问地址连通'}
            </button>
            {probeResult && probeResult.target === 'url' && <ProbeBadge res={probeResult} />}
          </div>
          <label>心跳检测地址（服务器内部探测用）</label>
          <input type="url" value={heartbeatUrl} onChange={(e) => setHeartbeatUrl(e.target.value)} placeholder="本服务器上的项目请填内网地址，如 http://127.0.0.1:8804/；留空则用访问地址探测" />
          <p className="field-hint">
            心跳由服务器本机发起。若项目就部署在本服务器，用外网地址（如 180.127.11.169:21xxx）会因无法回环而误报"离线"，请填该服务的内网地址 <code>http://127.0.0.1:内部端口/</code>。
          </p>
          <div className="field-actions">
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => handleProbe('heartbeat')} disabled={probing}>
              <Icon d={ICONS.heart} size={14} /> {probing ? '测试中...' : '测试心跳地址连通'}
            </button>
            {probeResult && probeResult.target === 'heartbeat' && <ProbeBadge res={probeResult} />}
          </div>
          <label>项目图片</label>
          <div className="image-upload">
            <input id="project-image" type="file" accept="image/*" onChange={handleFileChange} />
            <label htmlFor="project-image" className="image-upload-area">
              {preview ? (
                <img src={preview} alt="预览" className="image-preview" />
              ) : (
                <div className="image-upload-placeholder">
                  <Icon d={ICONS.plus} size={28} />
                  <span>点击或拖拽上传图片</span>
                  <small>支持 JPG、PNG、GIF、WebP，最大 5MB</small>
                </div>
              )}
            </label>
            {uploading && <div className="image-upload-hint">上传中...</div>}
            {image && !uploading && <div className="image-upload-hint">已上传，保存后生效</div>}
          </div>
          <label>能力要点（每行一条）</label>
          <textarea value={caps} onChange={(e) => setCaps(e.target.value)} rows={3} placeholder="每行一条能力" />
          <label>主题色（用于卡片顶部色条、头像、访问按钮配色）</label>
          <div className="color-picker-row">
            <input type="color" value={toHex(color)} onChange={(e) => setColor(e.target.value)} className="color-swatch" />
            <input type="text" value={color} onChange={(e) => setColor(e.target.value)} placeholder="#3b82f6 或命名色" className="color-text" />
            <span className="color-preview-name">{toHex(color)}</span>
          </div>
          {formError && <div className="form-error">{formError}</div>}
          <div className="modal-actions">
            <button type="button" className="btn btn-ghost" onClick={onClose} disabled={saving}>取消</button>
            <button type="submit" className="btn btn-primary" disabled={uploading || saving}>{uploading ? '上传中...' : (saving ? '保存中...' : '保存')}</button>
          </div>
        </form>
      </div>
    </div>
  );
}

/* ===== 管理员面板 ===== */
function AdminPanel({ config, projects, token, onClose, onChange, onAddProject, onEditProject }) {
  const [activeTab, setActiveTab] = useState('projects');
  const [localConfig, setLocalConfig] = useState(config || {});

  useEffect(() => { setLocalConfig(config || {}); }, [config]);

  const deleteProject = async (id) => {
    if (!confirm('确定删除该项目吗？')) return;
    try {
      await apiDelete(`/admin/projects/${id}`, token);
      onChange();
    } catch (err) {
      alert('删除失败：' + err.message);
    }
  };

  const saveConfig = async () => {
    try {
      await apiPost('/admin/config', localConfig, token);
      onChange();
      alert('配置已保存');
    } catch (err) {
      alert('保存失败：' + err.message);
    }
  };

  const resetConfig = async () => {
    if (!confirm('确定恢复默认外观配置吗？当前的站点标题、主色调、背景色都会被重置。')) return;
    try {
      const def = await apiPost('/admin/config/reset', {}, token);
      setLocalConfig(def || {});
      onChange();
      alert('已恢复默认外观配置');
    } catch (err) {
      alert('恢复失败：' + err.message);
    }
  };

  const triggerHeartbeat = async () => {
    try {
      await apiPost('/admin/heartbeat', {}, token);
      onChange();
      alert('心跳检测已触发');
    } catch (err) {
      alert('触发失败：' + err.message);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal modal-xl" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>管理员控制台</h3>
          <button className="icon-btn" onClick={onClose}><Icon d={ICONS.close} size={18} /></button>
        </div>
        <div className="admin-tabs">
          <button className={activeTab === 'projects' ? 'active' : ''} onClick={() => setActiveTab('projects')}>项目管理</button>
          <button className={activeTab === 'kb' ? 'active' : ''} onClick={() => setActiveTab('kb')}>知识库管理</button>
          <button className={activeTab === 'analytics' ? 'active' : ''} onClick={() => setActiveTab('analytics')}>问答分析</button>
          <button className={activeTab === 'eval' ? 'active' : ''} onClick={() => setActiveTab('eval')}>评测</button>
          <button className={activeTab === 'prd' ? 'active' : ''} onClick={() => setActiveTab('prd')}>PRD 生成</button>
          <button className={activeTab === 'links' ? 'active' : ''} onClick={() => setActiveTab('links')}>友情链接</button>
          <button className={activeTab === 'config' ? 'active' : ''} onClick={() => setActiveTab('config')}>外观配置</button>
        </div>
        <div className="admin-body">
          {activeTab === 'projects' && (
            <>
              <div className="admin-toolbar">
                <button className="btn btn-primary" onClick={onAddProject}>
                  <Icon d={ICONS.plus} size={16} /> 新增项目
                </button>
                <button className="btn btn-ghost" onClick={triggerHeartbeat}>
                  <Icon d={ICONS.heart} size={16} /> 立即心跳检测
                </button>
              </div>
              <div className="admin-table-wrap">
                <table className="admin-table">
                  <thead>
                    <tr><th>名称</th><th>地址</th><th>状态</th><th>操作</th></tr>
                  </thead>
                  <tbody>
                    {(projects || []).map(p => (
                      <tr key={p.id}>
                        <td><strong>{p.name}</strong><div className="muted">{p.role}</div></td>
                        <td className="muted" style={{maxWidth:260,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{p.url}</td>
                        <td>
                          <span className={`status-pill ${p.alive ? 'online' : 'offline'}`}>
                            {p.alive ? '运行中' : '离线'}
                          </span>
                        </td>
                        <td>
                          <button className="icon-btn" onClick={() => onEditProject(p)} title="编辑"><Icon d={ICONS.edit} size={16} /></button>
                          <button className="icon-btn" onClick={() => deleteProject(p.id)} title="删除"><Icon d={ICONS.trash} size={16} /></button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
          {activeTab === 'kb' && <AdminKB token={token} />}
          {activeTab === 'analytics' && <AdminAnalytics token={token} />}
          {activeTab === 'eval' && <AdminEval token={token} />}
          {activeTab === 'prd' && <AdminPRD token={token} />}
          {activeTab === 'links' && <AdminLinks token={token} />}
          {activeTab === 'config' && (
            <div className="admin-form">
              <label>站点标题</label>
              <input type="text" value={localConfig.title || ''} onChange={(e) => setLocalConfig({...localConfig, title: e.target.value})} />
              <label>主色调</label>
              <div className="color-picker-row">
                <input type="color" value={toHex(localConfig.accent)} onChange={(e) => setLocalConfig({...localConfig, accent: e.target.value})} className="color-swatch" />
                <input type="text" value={localConfig.accent || ''} onChange={(e) => setLocalConfig({...localConfig, accent: e.target.value})} placeholder="#3b82f6" className="color-text" />
              </div>
              <label>画布背景色</label>
              <div className="color-picker-row">
                <input type="color" value={toHex(localConfig.canvas)} onChange={(e) => setLocalConfig({...localConfig, canvas: e.target.value})} className="color-swatch" />
                <input type="text" value={localConfig.canvas || ''} onChange={(e) => setLocalConfig({...localConfig, canvas: e.target.value})} placeholder="#0b0b0f" className="color-text" />
              </div>
              <div className="modal-actions">
                <button className="btn btn-ghost" onClick={resetConfig}>恢复默认</button>
                <button className="btn btn-primary" onClick={saveConfig}>保存外观配置</button>
              </div>
              <p className="field-hint">改坏了外观？点「恢复默认」一键还原内置的站点标题、主色调（#3b82f6）与背景色（#0b0b0f）。</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ===== 主应用 ===== */
function App() {
  const [isAdmin, setIsAdmin] = useState(false);
  const [showLogin, setShowLogin] = useState(false);
  const [showAdmin, setShowAdmin] = useState(false);
  const [token, setToken] = useState(localStorage.getItem('admin_token') || '');
  const [config, setConfig] = useState(null);
  const [projects, setProjects] = useState([]);
  const [loaded, setLoaded] = useState(false);
  const [editorProject, setEditorProject] = useState(null); // null | {} | project

  const fetchData = useCallback(async () => {
    try {
      const [cfg, projs] = await Promise.all([apiGet('/config'), apiGet('/projects')]);
      setConfig(cfg);
      setProjects(projs);
    } catch (err) {
      console.error(err);
      setConfig({});
      setProjects([]);
    } finally {
      setLoaded(true);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const iv = setInterval(fetchData, 30000);
    return () => clearInterval(iv);
  }, [fetchData]);

  useEffect(() => {
    if (token) {
      // 简单验证 token 是否有效
      fetch(`${API_BASE}/admin/projects`, { headers: { Authorization: `Bearer ${token}` } })
        .then(r => { if (r.ok) setIsAdmin(true); else localStorage.removeItem('admin_token'); })
        .catch(() => {});
    }
  }, [token]);

  useEffect(() => {
    if (config?.accent) {
      document.documentElement.style.setProperty('--accent', config.accent);
      document.documentElement.style.setProperty('--accent-deep', adjustColor(config.accent, -20));
      document.documentElement.style.setProperty('--accent-soft', config.accent + '1f');
      document.documentElement.style.setProperty('--accent-glow', config.accent + '40');
    }
    if (config?.canvas) {
      document.documentElement.style.setProperty('--canvas', config.canvas);
    }
  }, [config]);

  const handleLogout = () => {
    localStorage.removeItem('admin_token');
    setToken(''); setIsAdmin(false); setShowAdmin(false);
  };

  const saveProject = async (proj) => {
    await apiPost('/admin/projects', proj, token);
    setEditorProject(null);
    fetchData();
  };

  const deleteProject = async (id) => {
    if (!confirm('确定删除该项目吗？')) return;
    try {
      await apiDelete(`/admin/projects/${id}`, token);
      fetchData();
    } catch (err) {
      alert('删除失败：' + (err?.message || '未知错误'));
    }
  };

  const displayTitle = config?.title || '智能制造专区';
  const displayAgents = projects?.length > 0 ? projects : AGENTS_FALLBACK;

  if (!loaded) return <div className="loading">加载中...</div>;

  return (
    <div className="page">
      <nav className="navbar">
        <div className="container">
          <div className="nav-logo">
            <div className="nav-logo-icon">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 002 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z" />
                <path d="M7.5 4.21l4.5 2.6 4.5-2.6M7.5 19.79V14.6L3 12M21 12l-4.5 2.6v5.19M3.27 6.96L12 12.01l8.73-5.05M12 22.08V12" />
              </svg>
            </div>
            {displayTitle}
          </div>
          <ul className="nav-links">
            <li><a href="#architecture">架构图</a></li>
            <li><a href="#agents">项目矩阵</a></li>
            <li><a href="#qa">知识问答</a></li>
          </ul>
          <div className="nav-actions">
            {isAdmin ? (
              <>
                <button className="btn btn-ghost btn-sm" onClick={() => setShowAdmin(true)}><Icon d={ICONS.settings} size={14} /> 管理</button>
                <button className="btn btn-ghost btn-sm" onClick={handleLogout}><Icon d={ICONS.logout} size={14} /> 退出</button>
              </>
            ) : (
              <button className="btn btn-ghost btn-sm" onClick={() => setShowLogin(true)}><Icon d={ICONS.login} size={14} /> 管理员</button>
            )}
          </div>
        </div>
      </nav>

      <ArchitectureDiagram />

      <section className="section agents-section" id="agents">
        <div className="container">
          <div className="section-header">
            <div className="section-tag"><span className="section-tag-line"></span>项目矩阵<span className="section-tag-line"></span></div>
            <h2 className="section-title">{projects?.length > 0 ? '接入的项目' : '六大专业智能体'}</h2>
            <p className="section-desc">
              {projects?.length > 0 ? '管理员可动态维护项目，系统实时心跳检测运行状态' : '每个智能体专注一个制造场景，协同工作覆盖工厂全链路'}
            </p>
          </div>
          <div className="agents-grid">
            {displayAgents.map((a, i) => {
              const pc = toHex(a.color);
              return (
              <div className="agent-card" key={a.id || i} style={{ '--proj-color': pc, '--proj-soft': withAlpha(pc, 0.14), '--proj-glow': withAlpha(pc, 0.35) }}>
                <div className="agent-image-wrap">
                  {a.image ? (
                    <img src={a.image} alt={a.name} className="agent-image" />
                  ) : (
                    <div className="agent-image agent-image-fallback" style={{ background: `linear-gradient(135deg, ${withAlpha(pc, 0.55)}, ${pc})` }}>
                      <span>{a.emoji || '🤖'}</span>
                    </div>
                  )}
                  {isAdmin && a.id && (
                    <div className="agent-card-actions">
                      <button className="agent-card-action" onClick={() => { setShowAdmin(false); setEditorProject(a); }} title="编辑"><Icon d={ICONS.edit} size={14} /></button>
                      <button className="agent-card-action danger" onClick={() => deleteProject(a.id)} title="删除"><Icon d={ICONS.trash} size={14} /></button>
                    </div>
                  )}
                </div>
                <div className="agent-header">
                  <div className="agent-avatar" style={{ background: `linear-gradient(135deg, ${withAlpha(pc, 0.55)}, ${pc})` }}>
                    {a.image ? <img src={a.image} alt={a.name} /> : <span>{a.emoji || '🤖'}</span>}
                  </div>
                  <div>
                    <div className="agent-name">{a.name}</div>
                    <div className="agent-role">{a.role}</div>
                  </div>
                </div>
                <p className="agent-desc">{a.desc}</p>
                {Array.isArray(a.caps) && a.caps.length > 0 && (
                  <ul className="agent-capabilities">
                    {a.caps.map((c, j) => <li key={j}>{c}</li>)}
                  </ul>
                )}
                <div className="agent-footer">
                  <div className={`agent-status ${a.alive ? 'online' : 'offline'}`}>
                    <span className="agent-status-dot"></span>
                    {a.alive ? '运行中' : '离线'}
                  </div>
                  {a.url && (
                    <a className="agent-link" href={a.url} target="_blank" rel="noreferrer">访问项目 →</a>
                  )}
                </div>
              </div>
              );
            })}
            {isAdmin && (
              <button className="agent-card agent-add-card" onClick={() => setEditorProject({})}>
                <div className="agent-add-inner">
                  <div className="agent-add-icon"><Icon d={ICONS.plus} size={40} /></div>
                  <div className="agent-add-title">添加项目</div>
                  <div className="agent-add-desc">上传图片、填写信息并接入新项目</div>
                </div>
              </button>
            )}
          </div>
        </div>
      </section>

      <KnowledgeQA />

      <footer className="footer">
        <LinkFooter isAdmin={isAdmin} token={token} />
        <div className="container">
          <div className="footer-bottom">
            <p>&copy; 2026 {displayTitle} 版权所有</p>
            <p>AI 驱动 · 智造未来</p>
          </div>
        </div>
      </footer>

      {showLogin && <AdminLoginModal onClose={() => setShowLogin(false)} onLogin={(t) => { setToken(t); setIsAdmin(true); }} />}
      {showAdmin && (
        <AdminPanel
          config={config}
          projects={projects}
          token={token}
          onClose={() => setShowAdmin(false)}
          onChange={fetchData}
          onAddProject={() => { setShowAdmin(false); setEditorProject({}); }}
          onEditProject={(p) => { setShowAdmin(false); setEditorProject(p); }}
        />
      )}
      {editorProject !== null && (
        <ProjectEditorModal
          project={editorProject.id ? editorProject : null}
          token={token}
          onClose={() => setEditorProject(null)}
          onSave={saveProject}
        />
      )}
    </div>
  );
}

// 简单颜色变暗辅助
function adjustColor(hex, amount) {
  const num = parseInt(hex.replace('#', ''), 16);
  const r = Math.max(0, Math.min(255, (num >> 16) + amount));
  const g = Math.max(0, Math.min(255, ((num >> 8) & 0x00FF) + amount));
  const b = Math.max(0, Math.min(255, (num & 0x0000FF) + amount));
  return `#${((r << 16) | (g << 8) | b).toString(16).padStart(6, '0')}`;
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);

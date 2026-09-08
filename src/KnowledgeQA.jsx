import React, { useState, useRef, useEffect, useCallback } from 'react';
import renderMarkdown from './markdown';

const API_BASE = '/api';
const STORE_KEY = 'kb_chats_v1';
const ACTIVE_KEY = 'kb_chat_active_v1';
const HISTORY_MAX = 12; // 与后端 config.HISTORY_MAX 对齐，只带最近若干条

const INTENT_LABEL = { knowledge: '知识问答', smalltalk: '闲聊', offtopic: '超出范围' };

async function readError(res) {
  const text = await res.text();
  try {
    const json = JSON.parse(text);
    if (json.error) return json.error;
    if (json.message) return json.message;
  } catch {}
  return text || `请求失败（HTTP ${res.status}）`;
}

const uid = () => (Date.now().toString(36) + Math.random().toString(36).slice(2, 8));
const newChat = () => ({ id: uid(), title: '新对话', createdAt: Date.now(), messages: [] });

function loadChats() {
  try {
    const raw = localStorage.getItem(STORE_KEY);
    const arr = raw ? JSON.parse(raw) : null;
    if (Array.isArray(arr) && arr.length) return arr;
  } catch {}
  return [newChat()];
}
function saveChats(chats) {
  try { localStorage.setItem(STORE_KEY, JSON.stringify(chats)); } catch {}
}

/* ===== 首页「知识库问答」：多会话侧栏 + 意图路由 + 多轮上下文 + 公开上传 ===== */
export default function KnowledgeQA() {
  const [chats, setChats] = useState(loadChats);
  const [activeId, setActiveId] = useState(() => localStorage.getItem(ACTIVE_KEY) || '');
  const [question, setQuestion] = useState('');
  const [asking, setAsking] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const listRef = useRef(null);
  const fileRef = useRef(null);

  // 保证 activeId 一定指向某个存在的会话
  const active = chats.find((c) => c.id === activeId) || chats[0];
  useEffect(() => {
    if (!chats.find((c) => c.id === activeId) && chats[0]) setActiveId(chats[0].id);
  }, [chats, activeId]);
  useEffect(() => { saveChats(chats); }, [chats]);
  useEffect(() => { try { localStorage.setItem(ACTIVE_KEY, activeId); } catch {} }, [activeId]);
  useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [active?.messages?.length, asking]);

  const messages = active?.messages || [];

  const patchActive = useCallback((updater) => {
    setChats((prev) => prev.map((c) => (c.id === active.id ? updater(c) : c)));
  }, [active?.id]);

  const newConversation = () => {
    const c = newChat();
    setChats((prev) => [c, ...prev]);
    setActiveId(c.id);
    setSidebarOpen(false);
  };

  const deleteConversation = (id, e) => {
    e.stopPropagation();
    if (!window.confirm('确定删除这个会话？删除后不可恢复。')) return;
    setChats((prev) => {
      const next = prev.filter((c) => c.id !== id);
      return next.length ? next : [newChat()];
    });
    if (id === active.id) {
      const rest = chats.filter((c) => c.id !== id);
      setActiveId(rest[0] ? rest[0].id : '');
    }
  };

  const ask = async (e) => {
    e.preventDefault();
    const q = question.trim();
    if (!q || asking) return;
    // 组装多轮历史（当前会话已有的问答，映射成 {role, content}，仅取最近若干条）
    const history = messages
      .filter((m) => !m.error && (m.role === 'user' || m.role === 'assistant'))
      .map((m) => ({ role: m.role, content: m.text }))
      .slice(-HISTORY_MAX);

    setQuestion('');
    setAsking(true);
    setSidebarOpen(false);
    patchActive((c) => ({
      ...c,
      title: c.messages.length === 0 ? q.slice(0, 20) : c.title,
      messages: [...c.messages, { role: 'user', text: q }],
    }));
    try {
      const res = await fetch(`${API_BASE}/kb/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        // conversation_id：门户用它在 WeKnora 侧续同一个会话（多轮上下文，W3）
        body: JSON.stringify({ question: q, history, conversation_id: active.id }),
      });
      if (!res.ok) throw new Error(await readError(res));
      const data = await res.json();
      patchActive((c) => ({
        ...c,
        messages: [...c.messages, {
          role: 'assistant', text: data.answer, sources: data.sources || [],
          ask_id: data.ask_id, intent: data.intent, feedback: null,
        }],
      }));
    } catch (err) {
      patchActive((c) => ({
        ...c,
        messages: [...c.messages, { role: 'assistant', error: true, text: err?.message || '问答失败，请稍后再试' }],
      }));
    } finally {
      setAsking(false);
    }
  };

  const sendFeedback = async (index, rating) => {
    const msg = messages[index];
    if (!msg || msg.feedback || !msg.ask_id) return;
    patchActive((c) => ({
      ...c,
      messages: c.messages.map((x, i) => (i === index ? { ...x, feedback: rating } : x)),
    }));
    try {
      await fetch(`${API_BASE}/kb/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ask_id: msg.ask_id, rating }),
      });
    } catch { /* 静默 */ }
  };

  const upload = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    const ext = (file.name.split('.').pop() || '').toLowerCase();
    if (!['txt', 'md', 'pdf'].includes(ext)) {
      setUploadMsg({ ok: false, text: '仅支持 TXT / Markdown / PDF 文件' });
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setUploadMsg({ ok: false, text: '文件超过 10MB 限制' });
      return;
    }
    setUploading(true);
    setUploadMsg(null);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await fetch(`${API_BASE}/kb/upload`, { method: 'POST', body: fd });
      if (!res.ok) throw new Error(await readError(res));
      const data = await res.json();
      setUploadMsg({ ok: true, text: data.message || '上传成功，等待管理员审核' });
    } catch (err) {
      setUploadMsg({ ok: false, text: err?.message || '上传失败' });
    } finally {
      setUploading(false);
    }
  };

  return (
    <section className="section qa-section" id="qa">
      <div className="container">
        <div className="section-header">
          <div className="section-tag"><span className="section-tag-line"></span>知识库问答<span className="section-tag-line"></span></div>
          <h2 className="section-title">智能制造知识库</h2>
          <p className="section-desc">
            基于行业公开资料与用户共建内容，AI 检索知识库后回答，支持多轮追问。也欢迎上传行业资料，审核通过后共同丰富知识库。
          </p>
        </div>

        <div className={`qa-layout ${sidebarOpen ? 'sidebar-open' : ''}`}>
          {/* 会话侧栏 */}
          <aside className="qa-sidebar">
            <button className="qa-newchat" onClick={newConversation}>＋ 新对话</button>
            <div className="qa-chatlist">
              {chats.map((c) => (
                <div
                  key={c.id}
                  className={c.id === active.id ? 'qa-chat active' : 'qa-chat'}
                  onClick={() => { setActiveId(c.id); setSidebarOpen(false); }}
                >
                  <span className="qa-chat-title" title={c.title}>{c.title}</span>
                  <button className="qa-chat-del" title="删除会话" onClick={(e) => deleteConversation(c.id, e)}>×</button>
                </div>
              ))}
            </div>
          </aside>

          {/* 对话区 */}
          <div className="qa-card">
            <div className="qa-mobile-bar">
              <button className="qa-sidebar-toggle" onClick={() => setSidebarOpen((v) => !v)}>☰ 会话</button>
              <button className="qa-newchat qa-newchat-inline" onClick={newConversation}>＋ 新对话</button>
            </div>

            <div className="qa-messages" ref={listRef}>
              {messages.length === 0 && (
                <div className="qa-empty">
                  <div className="qa-empty-icon">💬</div>
                  <p>向知识库提问，例如：</p>
                  <div className="qa-suggestions">
                    {['什么是智能制造？', '中小企业如何开始数字化转型？', '预测性维护有什么好处？'].map((s) => (
                      <button key={s} className="qa-suggestion" onClick={() => setQuestion(s)}>{s}</button>
                    ))}
                  </div>
                </div>
              )}
              {messages.map((msg, i) => (
                <div key={i} className={`qa-msg ${msg.role}`}>
                  <div className={`qa-bubble ${msg.error ? 'qa-bubble-error' : ''}`}>
                    {msg.role === 'assistant' && !msg.error ? (
                      <div className="qa-answer-content" dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.text) }} />
                    ) : (
                      msg.text
                    )}
                    {msg.role === 'assistant' && !msg.error && msg.intent && (
                      <div className="qa-intent-tag">{INTENT_LABEL[msg.intent] || msg.intent}</div>
                    )}
                    {msg.role === 'assistant' && msg.sources && msg.sources.length > 0 && (
                      <div className="qa-sources">
                        <div className="qa-sources-title">参考来源</div>
                        {msg.sources.map((s, j) => (
                          <div className="qa-source" key={j}>
                            <span className="qa-source-num">{j + 1}</span>
                            {s.url ? (
                              <a href={s.url} target="_blank" rel="noreferrer" className="qa-source-name" title={s.snippet || s.title}>{s.title || s.url}</a>
                            ) : (
                              <span className="qa-source-name" title={s.snippet || s.title}>{s.title}</span>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                    {msg.role === 'assistant' && !msg.error && msg.ask_id && (
                      <div className="qa-feedback">
                        {msg.feedback ? (
                          <span className="qa-feedback-done">感谢你的反馈</span>
                        ) : (
                          <>
                            <span className="qa-feedback-tip">这个回答有帮助吗？</span>
                            <button className="qa-feedback-btn" title="有帮助" onClick={() => sendFeedback(i, 'up')}>👍</button>
                            <button className="qa-feedback-btn" title="没帮助" onClick={() => sendFeedback(i, 'down')}>👎</button>
                          </>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              ))}
              {asking && (
                <div className="qa-msg assistant">
                  <div className="qa-bubble qa-typing">正在理解问题并检索知识库<span className="dot-flashing"></span></div>
                </div>
              )}
            </div>

            <form className="qa-input-row" onSubmit={ask}>
              <input
                type="text"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="输入你的问题，可结合上文继续追问…"
                maxLength={500}
                disabled={asking}
              />
              <button type="submit" className="btn btn-primary" disabled={asking || !question.trim()}>
                {asking ? '回答中…' : '提问'}
              </button>
              <button
                type="button"
                className="btn btn-ghost qa-upload-btn"
                onClick={() => fileRef.current?.click()}
                disabled={uploading}
                title="上传行业资料（TXT/MD/PDF，审核后入库）"
              >
                {uploading ? '上传中…' : '＋ 上传资料'}
              </button>
              <input ref={fileRef} type="file" accept=".txt,.md,.pdf" onChange={upload} hidden />
            </form>
            {uploadMsg && (
              <div className={`qa-upload-msg ${uploadMsg.ok ? 'ok' : 'err'}`}>{uploadMsg.text}</div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

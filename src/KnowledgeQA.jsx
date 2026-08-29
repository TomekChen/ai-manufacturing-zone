import React, { useState, useRef, useEffect } from 'react';

const API_BASE = '/api';

async function readError(res) {
  const text = await res.text();
  try {
    const json = JSON.parse(text);
    if (json.error) return json.error;
    if (json.message) return json.message;
  } catch {}
  return text || `请求失败（HTTP ${res.status}）`;
}

/* ===== 首页「知识库问答」模块：访客提问 + 公开上传 ===== */
export default function KnowledgeQA() {
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState([]); // {role:'user'|'assistant', text, sources?, error?}
  const [asking, setAsking] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState(null); // {ok, text}
  const listRef = useRef(null);
  const fileRef = useRef(null);

  useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [messages, asking]);

  const ask = async (e) => {
    e.preventDefault();
    const q = question.trim();
    if (!q || asking) return;
    setQuestion('');
    setMessages((m) => [...m, { role: 'user', text: q }]);
    setAsking(true);
    try {
      const res = await fetch(`${API_BASE}/kb/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q }),
      });
      if (!res.ok) throw new Error(await readError(res));
      const data = await res.json();
      setMessages((m) => [...m, { role: 'assistant', text: data.answer, sources: data.sources || [] }]);
    } catch (err) {
      setMessages((m) => [...m, { role: 'assistant', error: true, text: err?.message || '问答失败，请稍后再试' }]);
    } finally {
      setAsking(false);
    }
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
          <div className="section-tag"><span className="section-tag-line"></span>知识库问答<span className="section-tag-line"></span>
          </div>
          <h2 className="section-title">智能制造知识库</h2>
          <p className="section-desc">
            基于行业公开资料与用户共建内容，AI 检索知识库后回答。也欢迎上传行业资料，审核通过后共同丰富知识库。
          </p>
        </div>

        <div className="qa-card">
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
                  {msg.text}
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
                </div>
              </div>
            ))}
            {asking && (
              <div className="qa-msg assistant">
                <div className="qa-bubble qa-typing">正在检索知识库并思考<span className="dot-flashing"></span></div>
              </div>
            )}
          </div>

          <form className="qa-input-row" onSubmit={ask}>
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="输入你的问题，AI 将基于知识库回答…"
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
    </section>
  );
}

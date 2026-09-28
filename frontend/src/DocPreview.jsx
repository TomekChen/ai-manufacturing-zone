import React, { useState } from 'react';

const TYPE_LABEL = { upload: '用户上传', url: 'URL 采集', link: '友情链接采集' };
const STATUS_LABEL = { pending: '待审核', approved: '已入库', rejected: '已拒绝', processing: '解析中', completed: '已完成', failed: '解析失败' };
const STATUS_CLASS = { pending: 'status-pill pending', approved: 'status-pill online', rejected: 'status-pill offline', processing: 'status-pill pending', completed: 'status-pill online', failed: 'status-pill offline' };

const PREVIEW_LEN = 240;

export default function DocPreview({ doc, onClose }) {
  const [expanded, setExpanded] = useState({});
  if (!doc) return null;

  const toggleChunk = (idx) => setExpanded((e) => ({ ...e, [idx]: !e[idx] }));

  return (
    <div className="doc-preview-overlay" onClick={onClose}>
      <div className="doc-preview-panel" onClick={(e) => e.stopPropagation()}>
        <div className="doc-preview-header">
          <div>
            <h3 className="doc-preview-title">{doc.title || '（无标题）'}</h3>
            <div className="doc-preview-meta">
              {doc.url && (
                <a href={doc.url} target="_blank" rel="noreferrer" className="doc-preview-url" title={doc.url}>
                  {doc.url}
                </a>
              )}
              <span className={STATUS_CLASS[doc.status] || 'status-pill'}>{STATUS_LABEL[doc.status] || doc.status}</span>
              {doc.type && <span className="muted">{TYPE_LABEL[doc.type] || doc.type}</span>}
              {doc.chars != null && <span className="muted">{doc.chars} 字</span>}
              <span className="muted">{doc.chunk_count || (doc.chunks && doc.chunks.length) || 0} 个知识块</span>
              {doc.created_at && <span className="muted">{(doc.created_at).slice(0, 16).replace('T', ' ')}</span>}
            </div>
          </div>
          <button className="btn btn-ghost btn-sm" onClick={onClose}>关闭</button>
        </div>

        <div className="doc-preview-chunks">
          <div className="doc-preview-chunks-head">分块预览（共 {doc.chunks?.length || 0} 块）</div>
          {(doc.chunks || []).map((ch, idx) => {
            const text = ch.text || '';
            const isLong = text.length > PREVIEW_LEN;
            const showFull = expanded[idx] || !isLong;
            const display = showFull ? text : text.slice(0, PREVIEW_LEN) + '…';
            return (
              <div className="doc-preview-chunk" key={idx}>
                <div className="doc-preview-chunk-head">
                  <span className="doc-preview-chunk-num">块 {idx + 1}</span>
                  <span className="muted doc-preview-chunk-len">{text.length} 字</span>
                </div>
                <div className="doc-preview-chunk-text">{display}</div>
                {isLong && (
                  <button className="btn btn-ghost btn-xs doc-preview-expand" onClick={() => toggleChunk(idx)}>
                    {showFull ? '收起' : '展开'}
                  </button>
                )}
              </div>
            );
          })}
          {!(doc.chunks && doc.chunks.length) && (
            <div className="muted">暂无分块内容</div>
          )}
        </div>
      </div>
    </div>
  );
}

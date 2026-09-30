# -*- coding: utf-8 -*-
"""批量采集公开语料进知识库（走管理 API，引擎开启时自动进 WeKnora 问答链路）。
幂等：已提交 URL 记入 /app/data/corpus_ingested.json，重跑自动跳过。"""
import hashlib, json, os, sys, time
import urllib.request

BASE = "http://127.0.0.1:8804"
LEDGER = "/app/data/corpus_ingested.json"
URLS = json.load(open("os.path.join(os.path.dirname(os.path.abspath(__file__)), "urls.json")", encoding="utf-8"))

tok_src = os.environ["ADMIN_ACCOUNT"] + os.environ["ADMIN_PASSWORD"] + os.environ["SECRET_KEY"]
TOKEN = hashlib.sha256((tok_src + os.environ["SECRET_KEY"]).encode()).hexdigest()[:32]

done = set()
if os.path.exists(LEDGER):
    done = {r["url"] for r in json.load(open(LEDGER, encoding="utf-8"))}

ok, fail, skipped = [], [], []
for item in URLS:
    url = item["url"]
    if url in done:
        skipped.append(item["title"])
        print("SKIP  %s" % item["title"])
        continue
    body = json.dumps({"url": url}).encode()
    req = urllib.request.Request(
        BASE + "/api/admin/kb/crawl", data=body, method="POST",
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + TOKEN})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            out = json.loads(resp.read().decode())
        ok.append({"title": item["title"], "group": item["group"],
                   "doc_id": out.get("doc", {}).get("id"),
                   "parse_status": out.get("doc", {}).get("parse_status")})
        print("OK    %s -> id=%s %s" % (item["title"], out.get("doc", {}).get("id"),
                                        out.get("doc", {}).get("parse_status")))
    except Exception as e:
        detail = e.read().decode()[:160] if hasattr(e, "read") else str(e)
        fail.append({"title": item["title"], "url": url, "error": detail[:120]})
        print("FAIL  %s : %s" % (item["title"], detail[:120]))
    time.sleep(3)

done |= {r["url"] for r in ok}
ledger = [r for r in URLS if r["url"] in done]
json.dump(ledger, open(LEDGER, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("==== submitted %d / fail %d / skipped %d ====" % (len(ok), len(fail), len(skipped)))
if fail:
    json.dump(fail, open("/tmp/corpus_fail.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
sys.exit(1 if fail else 0)

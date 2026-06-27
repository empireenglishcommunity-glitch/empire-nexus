// Local smoke test: mocks Telegram + Gemini + Workers AI + KV and drives the Worker
// through the full flow. Run: node linkedin-engine/_test.mjs   (dev aid; safe to delete.)

const ADMIN = "999";

// ---- in-memory KV ----
const store = new Map();
const KV = {
  async get(k, t) { const v = store.get(k); if (v === undefined) return null; return t === "json" ? JSON.parse(v) : v; },
  async put(k, v) { store.set(k, v); },
  async delete(k) { store.delete(k); },
};
// ---- mock Workers AI binding (Phase 2) ----
const AI = { async run() { return { image: "iVBORw0KGgo=" }; } }; // valid base64 stub
const env = { KV, AI, TELEGRAM_TOKEN: "T", ADMIN_CHAT_ID: ADMIN, GEMINI_API_KEY: "G" };

// ---- captured Telegram calls + mocked HTTP ----
const tgCalls = [];
let midSeq = 100;
globalThis.fetch = async (url, opts) => {
  const u = String(url);
  if (u.includes("api.telegram.org")) {
    const method = u.split("/").pop().split("?")[0];
    const isForm = opts && opts.body && typeof opts.body !== "string";
    const body = isForm ? { _form: true } : (opts && opts.body ? JSON.parse(opts.body) : {});
    tgCalls.push({ method, body });
    const message_id = method === "sendMessage" ? ++midSeq : (body.message_id || midSeq);
    return new Response(JSON.stringify({ ok: true, result: { message_id } }), { status: 200 });
  }
  if (u.includes("generativelanguage.googleapis.com")) {
    const json = {
      hooks: ["HOOK A — stop scrolling.", "HOOK B — the real reason.", "HOOK C — nobody tells you this."],
      body: "Line one.\nLine two.\nThis is the AI-generated body.",
      hashtags: ["#Test", "#Brand", "#Voice"],
      image_prompt: "a golden door opening to a city",
      comments: ["What would you add?", "Agree or disagree?", "What's your take?"],
    };
    return new Response(JSON.stringify({ candidates: [{ content: { parts: [{ text: JSON.stringify(json) }] } }] }), { status: 200 });
  }
  return new Response("{}", { status: 200 });
};

const worker = (await import("./worker.js")).default;
const update = (obj) => new Request("https://x/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(obj) });
const msg = (text) => update({ message: { from: { id: Number(ADMIN) }, chat: { id: Number(ADMIN) }, text } });
const cb = (data, mid) => update({ callback_query: { id: "c", from: { id: Number(ADMIN) }, data, message: { message_id: mid, chat: { id: Number(ADMIN) } } } });
const ok = (c, m) => { console.log((c ? "✅" : "❌") + " " + m); if (!c) process.exitCode = 1; };

// 1) /new -> draft (7 buttons) + auto image (sendPhoto)
tgCalls.length = 0;
await worker.fetch(msg("/new"), env);
const draftMsg = tgCalls.find(c => c.method === "sendMessage" && c.body.reply_markup && c.body.reply_markup.inline_keyboard);
ok(!!draftMsg, "draft message delivered");
const btnCount = draftMsg ? draftMsg.body.reply_markup.inline_keyboard.flat().length : 0;
ok(btnCount === 7, `draft has 7 buttons incl. image+carousel (got ${btnCount})`);
ok(/HOOK A/.test(draftMsg.body.text), "draft uses AI hook A first");
ok(tgCalls.some(c => c.method === "sendPhoto"), "Phase 2: auto image (sendPhoto) sent");
const draftMid = midSeq;
ok(store.has("draft:" + draftMid), "draft persisted in KV");

// 2) Other hook -> hook B
tgCalls.length = 0;
await worker.fetch(cb("lp:hk", draftMid), env);
ok(tgCalls.find(c => c.method === "editMessageText" && /HOOK B/.test(c.body.text)), "Other hook rotates to hook B");

// 3) New image button -> sendPhoto
tgCalls.length = 0;
await worker.fetch(cb("lp:img", draftMid), env);
ok(tgCalls.some(c => c.method === "sendPhoto"), "Phase 2: 'New image' button sends a photo");

// 4) Approve -> queue + copy block + comment seeder + stats
tgCalls.length = 0;
await worker.fetch(cb("lp:ap", draftMid), env);
const approved = tgCalls.find(c => c.method === "editMessageText");
ok(approved && /APPROVED/.test(approved.body.text), "Approve shows APPROVED copy block");
ok(approved && /First-comment ideas/.test(approved.body.text), "Phase 5: comment seeder shown on approve");
const q = JSON.parse(store.get("queue") || "[]");
ok(q.length === 1, "approved post saved to queue");
const stats = JSON.parse(store.get("stats") || "{}");
ok(Object.values(stats).some(s => s.approved === 1), "Phase 5: approval recorded in stats");

// 5) /export dumps the queue
tgCalls.length = 0;
await worker.fetch(msg("/export"), env);
ok(tgCalls.some(c => /1\/1/.test(c.body.text || "")), "Phase 4: /export dumps approved posts");

// 6) Idea inbox: plain text saved, then consumed by next /new
tgCalls.length = 0;
await worker.fetch(msg("a contrarian take on saving money in your 20s"), env);
ok(tgCalls.some(c => /Idea saved/.test(c.body.text || "")), "Phase 5: idea inbox saves freeform text");
ok((JSON.parse(store.get("ideas") || "[]")).length === 1, "idea stored in KV");
tgCalls.length = 0;
await worker.fetch(msg("/new"), env);
ok(tgCalls.some(c => /your idea/.test((c.body && c.body.text) || "")), "Phase 5: next /new consumes the saved idea");
ok((JSON.parse(store.get("ideas") || "[]")).length === 0, "idea consumed from KV");

// 7) Carousel generates self-contained slides (v3.0 — no external dependency)
tgCalls.length = 0;
await worker.fetch(cb("lp:car", midSeq), env);
ok(tgCalls.some(c => /CAROUSEL SLIDES|SLIDE \d/.test(c.body.text || "")), "Phase 3: self-contained carousel generates slides as text");

// 8) Non-admin ignored
tgCalls.length = 0;
await worker.fetch(update({ message: { from: { id: 1 }, chat: { id: 1 }, text: "/new" } }), env);
ok(tgCalls.length === 0, "non-admin messages are ignored");

console.log("\nDone.");

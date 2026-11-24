// 前端：只讀取 data/*.json 顯示，不做任何計算以外的事
const $ = id => document.getElementById(id);
const fmt = (v, d = 0) => v == null || isNaN(v) ? '—' : Number(v).toLocaleString('zh-TW', {minimumFractionDigits: d, maximumFractionDigits: d});
const money = v => (v > 0 ? '+' : v < 0 ? '−' : '') + '$' + fmt(Math.abs(v));
const cls = v => v > 0 ? 'pos' : v < 0 ? 'neg' : '';
const TYP = {P: 'Buy Put', C: 'Buy Call'};
const ST = {pending: '待進場', open: '持倉中', settled: '已結算', skipped: '未成交', merged: '併入'};
const WK = {up: '上揚 ▲', down: '下彎 ▼', flat: '持平'};

async function getJSON(p, dflt) {
  try { const r = await fetch(`${p}?t=${Date.now()}`); return r.ok ? await r.json() : dflt; } catch { return dflt; }
}

function nextWeekday(d) {
  const x = new Date(d + 'T00:00:00Z');
  do x.setUTCDate(x.getUTCDate() + 1); while ([0, 6].includes(x.getUTCDay()));
  return x.toISOString().slice(0, 10);
}
function targetWed(d) {
  const x = new Date(d + 'T00:00:00Z'); let k = (3 - x.getUTCDay() + 7) % 7 || 7;
  x.setUTCDate(x.getUTCDate() + k); return x.toISOString().slice(0, 10);
}

function stats(a) {
  if (!a.length) return {n: 0, tot: 0, win: 0, pf: null, mdd: 0, avg: 0};
  let g = 0, l = 0, eq = 0, pk = 0, dd = 0;
  [...a].sort((x, y) => x.entry < y.entry ? -1 : 1).forEach(t => {
    t.pnl > 0 ? g += t.pnl : l -= t.pnl; eq += t.pnl; pk = Math.max(pk, eq); dd = Math.min(dd, eq - pk);
  });
  return {n: a.length, tot: g - l, win: a.filter(t => t.pnl > 0).length / a.length * 100, pf: l ? g / l : null, mdd: dd, avg: (g - l) / a.length};
}

function renderToday(S, T) {
  const fx = S.fx, wk = S.week;
  const box = $('sigbox');
  if (!fx) { box.innerHTML = '等待第一次後端更新'; box.className = 'sigbox'; }
  else if (fx.signal) {
    box.className = 'sigbox ' + fx.signal;
    const e = nextWeekday(fx.date);
    box.innerHTML = `${TYP[fx.signal]} × ${S.params?.lots ?? 2} 口<small>訊號日 ${fx.date}｜預計 ${e} 開盤進場，${targetWed(e)} 到期合約，價平價外一檔</small>`;
  } else {
    box.className = 'sigbox';
    box.innerHTML = `今日無訊號<small>資料日 ${fx.date}</small>`;
  }
  if (!fx) return;
  const lv = [];
  if (wk?.dir === 'up') lv.push(`<div>Put 觸發收盤</div><div>≥ ${fmt(fx.put_level, 3)}（週線上揚，RSI&gt;80 即觸發）</div>`);
  if (wk?.dir === 'down') lv.push(`<div>Call 觸發收盤</div><div>≤ ${fmt(fx.call_level, 3)}（週線下彎，RSI&lt;20 即觸發）</div>`);
  if (wk && wk.dir !== 'up' && wk.dir !== 'down') lv.push('<div>觸發</div><div>本週週線持平，無訊號</div>');
  $('fxkv').innerHTML = `
    <div>美元/台幣</div><div>${fmt(fx.close, 3)}（${fx.date}）</div>
    <div>日線 RSI(6)</div><div><b class="${fx.rsi > 80 ? 'pos' : fx.rsi < 20 ? 'neg' : ''}">${fmt(fx.rsi, 2)}</b>　前一日 ${fmt(fx.rsi_prev, 2)}</div>
    <div>上週週線 RSI(6)</div><div>${fmt(wk?.rsi, 2)} vs ${fmt(wk?.rsi_prev, 2)}　<b>${WK[wk?.dir] ?? '—'}</b>（週結束 ${wk?.end ?? '—'}）</div>
    ${lv.join('')}`;
}

function renderPositions(T) {
  const live = T.filter(t => t.status === 'pending' || t.status === 'open');
  if (!live.length) { $('positions').innerHTML = '<div class="empty">目前沒有待進場或持倉中的部位</div>'; return; }
  $('positions').innerHTML = `<table><tr><th>狀態</th><th>方向</th><th>訊號日</th><th>進場</th><th>合約</th><th>履約價</th><th>權利金</th><th>到期</th></tr>` +
    live.map(t => {
      const e = t.entry || nextWeekday(t.sig) + '（預計）';
      return `<tr><td><span class="st ${t.status}">${ST[t.status]}</span></td><td><span class="tag ${t.typ}">${t.typ}</span></td><td>${t.sig}</td><td>${e}</td>
      <td>${t.code ?? '—'}</td><td>${t.strike ? fmt(t.strike) : '價外一檔'}</td><td>${t.prem != null ? fmt(t.prem, 1) : '—'}</td><td>${t.wed || targetWed(t.entry || nextWeekday(t.sig))}</td></tr>`;
    }).join('') + '</table>';
}

function renderKpis(D) {
  const s = stats(D), is = stats(D.filter(t => t.entry < '2025')), oos = stats(D.filter(t => t.entry >= '2025'));
  const k = [['總損益', `<span class="${cls(s.tot)}">${money(s.tot)}</span>`], ['交易筆數', fmt(s.n)], ['勝率', fmt(s.win, 1) + '%'],
    ['獲利因子', fmt(s.pf, 2)], ['最大回撤', `<span class="neg">${money(s.mdd)}</span>`], ['每筆平均', `<span class="${cls(s.avg)}">${money(s.avg)}</span>`]];
  $('kpis').innerHTML = k.map(([l, v]) => `<div class="kpi"><div class="l">${l}</div><div class="v">${v}</div></div>`).join('');
  const row = (n, a) => `<tr><td>${n}</td><td>${a.n}</td><td>${fmt(a.win, 1)}%</td><td class="${cls(a.tot)}">${money(a.tot)}</td><td>${fmt(a.pf, 2)}</td><td>${money(a.mdd)}</td></tr>`;
  $('split').innerHTML = `<table><tr><th></th><th>筆數</th><th>勝率</th><th>損益</th><th>PF</th><th>MDD</th></tr>` +
    row('樣本內 2021–24', is) + row('樣本外 2025–', oos) + row('Buy Put', stats(D.filter(t => t.typ === 'P'))) + row('Buy Call', stats(D.filter(t => t.typ === 'C'))) + '</table>';
  const ys = [...new Set(D.map(t => t.entry.slice(0, 4)))].sort();
  $('years').innerHTML = `<table><tr><th>年度</th><th>筆數</th><th>勝率</th><th>損益</th><th>PF</th><th>MDD</th></tr>` +
    ys.map(y => row(y, stats(D.filter(t => t.entry.startsWith(y))))).join('') + '</table>';
}

function renderTrades(T) {
  const f = $('flt').value;
  const a = T.filter(t => t.status !== 'merged').filter(t => f === 'all' || (f === 'live' ? ['pending', 'open'].includes(t.status) : t.typ === f)).reverse();
  $('trades').innerHTML = `<tr><th>訊號日</th><th>方向</th><th>RSI</th><th>週線</th><th>進場</th><th>合約</th><th>履約價</th><th>加權開盤</th><th>權利金</th><th>結算價</th><th>到期價值</th><th>損益（2 口）</th><th>狀態</th></tr>` +
    a.map(t => `<tr><td>${t.sig}</td><td><span class="tag ${t.typ}">${t.typ}</span></td><td>${fmt(t.rsi, 1)}</td>
      <td>${t.wk_rsi_prev != null ? fmt(t.wk_rsi_prev, 1) + '→' + fmt(t.wk_rsi, 1) : '—'}</td><td>${t.entry ?? '—'}</td><td>${t.code ?? '—'}</td>
      <td>${t.strike ? fmt(t.strike) : '—'}</td><td>${t.S0 ? fmt(t.S0, 0) : '—'}</td><td>${t.prem != null ? fmt(t.prem, 1) : '—'}</td>
      <td>${t.fsp ? fmt(t.fsp) : '—'}</td><td>${t.payoff != null ? fmt(t.payoff, 1) : '—'}</td>
      <td class="${cls(t.pnl)}">${t.pnl != null ? money(t.pnl) : '—'}</td><td><span class="st ${t.status}">${ST[t.status]}${t.note ? '｜' + t.note : ''}</span></td></tr>`).join('');
}

// ---------- 圖表（canvas，無外部套件） ----------
let CH = 'eq', DATA = {};
function draw() {
  const cv = $('chart'), dpr = devicePixelRatio || 1, W = cv.clientWidth, H = 300;
  cv.width = W * dpr; cv.height = H * dpr; const g = cv.getContext('2d'); g.scale(dpr, dpr); g.clearRect(0, 0, W, H);
  const L = 64, R = 12, Tp = 12, B = 26, css = getComputedStyle(document.documentElement);
  const col = v => css.getPropertyValue(v).trim();
  let xs = [], ys = [], marks = [], lines = [], fmtY = v => fmt(v);
  if (CH === 'eq') {
    let e = 0; DATA.settled.forEach(t => { e += t.pnl; xs.push(t.entry); ys.push(e); });
    fmtY = v => '$' + fmt(v / 1000) + 'k'; lines = [[0, col('--mu')]];
    marks = DATA.settled.map((t, i) => [i, ys[i], t.typ]);
  } else if (CH === 'rsi') {
    (DATA.series.daily || []).forEach(r => { xs.push(r[0]); ys.push(r[2]); });
    lines = [[80, col('--put')], [20, col('--call')]];
    marks = (DATA.series.daily || []).map((r, i) => r[3] ? [i, r[2], r[3]] : null).filter(Boolean);
  } else {
    (DATA.series.weekly || []).forEach(r => { xs.push(r[0]); ys.push(r[1]); });
    lines = [[80, col('--put')], [20, col('--call')]];
  }
  if (!xs.length) { g.fillStyle = col('--mu'); g.fillText('尚無資料（等待後端第一次執行）', L, 40); return; }
  let lo = Math.min(...ys, ...lines.map(l => l[0])), hi = Math.max(...ys, ...lines.map(l => l[0]));
  if (CH !== 'eq') { lo = 0; hi = 100; }
  const pad = (hi - lo) * 0.05 || 1; lo -= CH === 'eq' ? pad : 0; hi += CH === 'eq' ? pad : 0;
  const X = i => L + (W - L - R) * (xs.length === 1 ? 0.5 : i / (xs.length - 1)), Y = v => Tp + (H - Tp - B) * (1 - (v - lo) / (hi - lo));
  g.font = '11px sans-serif'; g.fillStyle = col('--mu'); g.strokeStyle = col('--line'); g.lineWidth = 1;
  for (let k = 0; k <= 4; k++) { const v = lo + (hi - lo) * k / 4, y = Y(v); g.beginPath(); g.moveTo(L, y); g.lineTo(W - R, y); g.stroke(); g.fillText(fmtY(v), 4, y + 4); }
  const step = Math.max(1, Math.floor(xs.length / 6));
  for (let i = 0; i < xs.length; i += step) g.fillText(xs[i].slice(0, 7), Math.min(X(i) - 18, W - R - 44), H - 8);
  lines.forEach(([v, c]) => { g.strokeStyle = c; g.setLineDash([4, 4]); g.beginPath(); g.moveTo(L, Y(v)); g.lineTo(W - R, Y(v)); g.stroke(); g.setLineDash([]); });
  g.strokeStyle = col('--acc'); g.lineWidth = 1.6; g.beginPath(); ys.forEach((v, i) => i ? g.lineTo(X(i), Y(v)) : g.moveTo(X(i), Y(v))); g.stroke();
  marks.forEach(([i, v, t]) => { g.fillStyle = col(t === 'P' ? '--put' : '--call'); g.beginPath(); g.arc(X(i), Y(v), 3, 0, 7); g.fill(); });
}

(async () => {
  const [S, T, series] = await Promise.all([getJSON('data/status.json', {}), getJSON('data/trades.json', []), getJSON('data/series.json', {})]);
  const settled = T.filter(t => t.status === 'settled').sort((a, b) => a.entry < b.entry ? -1 : 1);
  DATA = {settled, series};
  $('upd').textContent = `後端更新：${S.updated_at ?? '—'}（${S.mode ?? ''}）｜匯率資料至 ${S.fx?.date ?? S.last_scanned ?? '—'}｜已結算 ${settled.length} 筆`;
  renderToday(S, T); renderPositions(T); renderKpis(settled); renderTrades(T);
  $('flt').onchange = () => renderTrades(T);
  $('chartTabs').onclick = e => { if (!e.target.dataset.c) return; CH = e.target.dataset.c; [...$('chartTabs').children].forEach(b => b.classList.toggle('on', b === e.target)); draw(); };
  addEventListener('resize', draw); draw();
})();

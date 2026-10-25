(function () {
  'use strict';
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }

  /* ---------- navigation ---------- */
  var menu = $('.menu');
  if (menu) {
    menu.addEventListener('click', function () {
      var open = document.body.classList.toggle('nav-open');
      menu.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
    document.addEventListener('click', function (e) {
      if (document.body.classList.contains('nav-open') && !e.target.closest('.side') && !e.target.closest('.menu')) {
        document.body.classList.remove('nav-open');
        menu.setAttribute('aria-expanded', 'false');
      }
    });
  }
  $$('[data-edswitch]').forEach(function (s) {
    s.addEventListener('change', function () { location.href = s.value; });
  });
  var active = $('.side li.active');
  if (active && active.scrollIntoView) { try { active.scrollIntoView({ block: 'center' }); } catch (e) {} }

  /* ---------- contents highlighting ---------- */
  var tocLinks = $$('.toc li a');
  if (tocLinks.length && 'IntersectionObserver' in window) {
    var byId = {};
    tocLinks.forEach(function (a) { byId[a.getAttribute('href').slice(1)] = a; });
    var current = null;
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) {
          if (current) current.classList.remove('on');
          current = byId[en.target.id];
          if (current) {
            current.classList.add('on');
            var box = current.closest('.toc');
            if (box) {
              var r = current.getBoundingClientRect(), b = box.getBoundingClientRect();
              if (r.top < b.top + 40 || r.bottom > b.bottom - 40) box.scrollTop += r.top - b.top - b.height / 2;
            }
          }
        }
      });
    }, { rootMargin: '-70px 0px -75% 0px' });
    Object.keys(byId).forEach(function (id) { var el = document.getElementById(id); if (el) io.observe(el); });
  }

  /* ---------- search ---------- */
  var box = $('#results');
  if (!box) return;

  function stem(w) {
    w = w.toLowerCase();
    if (w.length <= 3) return w;
    if (/ies$/.test(w) && w.length > 4) w = w.slice(0, -3) + 'y';
    else if (/sses$/.test(w)) w = w.slice(0, -2);
    else if (/ing$/.test(w) && w.length - 3 >= 3) w = w.slice(0, -3);
    else if (/ed$/.test(w) && w.length - 2 >= 3) w = w.slice(0, -2);
    else if (/(xes|ches|shes|zes)$/.test(w)) w = w.slice(0, -2);
    else if (/s$/.test(w) && !/(ss|us|is)$/.test(w)) w = w.slice(0, -1);
    if (/e$/.test(w) && w.length > 3) w = w.slice(0, -1);
    return w;
  }

  var IDX = null, STOP = {}, TERMKEYS = null, loading = false;
  var qEl = $('#q'), statusEl = $('#status'), archEl = $('#arch');
  var PAGE = 40, shown = PAGE, lastResults = [];

  function load(cb) {
    if (IDX) return cb();
    if (loading) return;
    loading = true;
    statusEl.textContent = 'Loading the search index…';
    fetch('/assets/search-index.json').then(function (r) { return r.json(); }).then(function (j) {
      IDX = j; TERMKEYS = Object.keys(j.terms);
      j.stop.forEach(function (w) { STOP[w] = 1; });
      loading = false; cb();
    }).catch(function () { statusEl.textContent = 'The search index could not be loaded.'; loading = false; });
  }

  function checked(name) { return $$('input[name="' + name + '"]:checked').map(function (i) { return i.value; }); }

  function parseQuery(raw) {
    var phrases = [], rest = raw.replace(/"([^"]+)"/g, function (_, p) { phrases.push(p.toLowerCase().trim()); return ' '; });
    var rawToks = (rest.toLowerCase().match(/[a-z0-9]+/g) || []);
    var endsOpen = /[a-z0-9]$/i.test(raw.trim()) && !/"\s*$/.test(raw.trim());
    var toks = [];
    rawToks.forEach(function (t, i) { toks.push({ raw: t, stem: stem(t), last: i === rawToks.length - 1 && endsOpen }); });
    phrases.forEach(function (p) { (p.match(/[a-z0-9]+/g) || []).forEach(function (t) { toks.push({ raw: t, stem: stem(t), last: false, ph: true }); }); });
    var content = toks.filter(function (t) { return !STOP[t.stem]; });
    if (content.length) toks = content;
    return { toks: toks, phrases: phrases };
  }

  function termDocs(tok, N) {
    var map = {}, df = 0;
    function add(term, w) {
      var p = IDX.terms[term]; if (!p) return;
      for (var i = 0; i < p.length; i += 2) {
        var d = p[i], s = (1 + Math.log(p[i + 1])) * w;
        if (map[d] === undefined) { map[d] = s; df++; } else if (s > map[d]) map[d] = s;
      }
    }
    add(tok.stem, 1);
    if (tok.last && tok.raw.length >= 2) {
      for (var i = 0; i < TERMKEYS.length; i++) {
        var k = TERMKEYS[i];
        if (k !== tok.stem && k.indexOf(tok.raw) === 0) add(k, 0.35);
      }
    }
    var idf = Math.log(1 + N / (1 + df));
    for (var d in map) map[d] *= idf;
    return map;
  }

  function passes(doc, f, includeArch) {
    var a = IDX.acts[doc.a];
    if (!includeArch && !doc.c) return false;
    if (f.gr.length && f.gr.indexOf(a.group) < 0) return false;
    if (f.st.length && f.st.indexOf(a.status) < 0) return false;
    if (f.tp.length && !a.topics.some(function (t) { return f.tp.indexOf(String(t)) >= 0; })) return false;
    return true;
  }

  function snippet(doc, q) {
    var x = doc.x || '', low = x.toLowerCase(), pos = -1, pats = [];
    q.toks.forEach(function (t) {
      pats.push(t.raw);
      if (t.stem.length >= 4 && t.stem !== t.raw) pats.push(t.stem);
    });
    q.phrases.forEach(function (p) { pats.unshift(p); });
    for (var i = 0; i < pats.length; i++) { var p = low.indexOf(pats[i]); if (p >= 0 && (pos < 0 || i === 0 || p < pos)) { pos = p; if (i === 0) break; } }
    if (pos < 0) return esc(x.slice(0, 220)) + (x.length > 220 ? '…' : '');
    var s = Math.max(0, pos - 90), e = Math.min(x.length, pos + 190);
    var txt = (s > 0 ? '…' : '') + x.slice(s, e) + (e < x.length ? '…' : '');
    var h = esc(txt);
    var uniq = pats.filter(function (p, i) { return p.length > 1 && pats.indexOf(p) === i; }).map(function (p) { return esc(p).replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); });
    if (uniq.length) h = h.replace(new RegExp('(' + uniq.join('|') + ')', 'gi'), '<mark>$1</mark>');
    return h;
  }

  function run() {
    var raw = qEl.value.trim();
    var f = { gr: checked('gr'), st: checked('st'), tp: checked('tp') };
    var includeArch = archEl.checked;
    var url = new URL(location.href);
    if (raw) url.searchParams.set('q', raw); else url.searchParams.delete('q');
    try { history.replaceState(null, '', url); } catch (e) {}
    var out = [];
    if (!raw) {
      IDX.docs.forEach(function (d, i) { if (d.i === '' && d.n === '' && passes(d, f, false)) out.push({ i: i, s: 0 }); });
      statusEl.textContent = out.length + ' act' + (out.length === 1 ? '' : 's') + (f.gr.length || f.st.length || f.tp.length ? ' match the filters' : ' in the database');
      lastResults = out.map(function (o) { return { d: IDX.docs[o.i], q: null }; });
      shown = PAGE; render(); return;
    }
    var q = parseQuery(raw);
    if (!q.toks.length && !q.phrases.length) { statusEl.textContent = 'Type a word or a phrase.'; box.innerHTML = ''; return; }
    var N = IDX.docs.length, cand = null, maps = [];
    q.toks.forEach(function (t) { maps.push(termDocs(t, N)); });
    maps.forEach(function (m, i) {
      if (cand === null) { cand = {}; for (var d in m) cand[d] = m[d]; }
      else { var nx = {}; for (var d in cand) if (m[d] !== undefined) nx[d] = cand[d] + m[d]; cand = nx; }
    });
    cand = cand || {};
    var joined = q.toks.filter(function (t) { return !t.ph; }).map(function (t) { return t.raw; }).join(' ');
    var res = [];
    for (var d in cand) {
      var doc = IDX.docs[d];
      if (!passes(doc, f, includeArch)) continue;
      var hay = (doc.h + ' ' + doc.x).toLowerCase(), score = cand[d];
      var ok = true;
      for (var p = 0; p < q.phrases.length; p++) if (hay.indexOf(q.phrases[p]) < 0) { ok = false; break; }
      if (!ok) continue;
      if (q.toks.length > 1 && joined && hay.indexOf(joined) >= 0) score *= 1.6;
      if (doc.h && doc.h.toLowerCase().indexOf(q.toks[0].raw) >= 0) score *= 1.3;
      if (!doc.c) score *= 0.6;
      res.push({ d: doc, s: score, q: q });
    }
    res.sort(function (a, b) { return b.s - a.s; });
    lastResults = res;
    statusEl.textContent = res.length ? res.length + ' result' + (res.length === 1 ? '' : 's') : 'Nothing found. Try fewer words, or remove filters.';
    shown = PAGE; render();
  }

  function render() {
    var html = [];
    lastResults.slice(0, shown).forEach(function (r) {
      var d = r.d, a = IDX.acts[d.a];
      var isAct = d.i === '' && d.n === '';
      var title = isAct ? a.short : (d.n + (d.h && d.n !== 'Preamble' ? ' – ' + d.h : ''));
      var edl = (IDX.eds && IDX.eds[a.id] && IDX.eds[a.id][d.e]) || '';
      var ed = !d.c ? ' <span class="chip arch">archived edition' + (edl ? ': ' + esc(edl) : '') + '</span>' : '';
      var st = a.status === 'repealed' ? ' <span class="chip bad">repealed</span>' : '';
      var sub = isAct ? esc(a.title) : esc(a.short) + ' · ' + esc(a.subject);
      var body = isAct ? esc(d.x) : (r.q ? snippet(d, r.q) : esc((d.x || '').slice(0, 220)));
      html.push('<li><a class="rt" href="' + esc(d.u) + '">' + esc(title) + '</a>' + st + ed + '<div class="ra">' + sub + '</div><div class="rs">' + body + '</div></li>');
    });
    if (lastResults.length > shown) html.push('<li style="border:0;background:none;padding:0"><button class="more" type="button">Show more (' + (lastResults.length - shown) + ' left)</button></li>');
    box.innerHTML = html.join('');
    var more = $('.more', box);
    if (more) more.addEventListener('click', function () { shown += PAGE; render(); });
  }

  var timer = null;
  function schedule() { clearTimeout(timer); timer = setTimeout(function () { load(run); }, 120); }
  qEl.addEventListener('input', schedule);
  $$('#sf input[type=checkbox]').forEach(function (c) { c.addEventListener('change', schedule); });
  $('#sf').addEventListener('submit', function (e) { e.preventDefault(); load(run); });
  var init = new URL(location.href).searchParams.get('q');
  if (init) qEl.value = init;
  load(run);
})();

python3 << 'PYEOF'
import json, os

with open('/home/claude/bible_pairs.json') as f:
    data = json.load(f)

data_js = json.dumps(data)

parts = []
parts.append('''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>KJV Bible Comparison &ndash; 3 Sources</title>
<link href="https://fonts.googleapis.com/css2?family=EB+Garamond:ital,wght@0,400;0,600;1,400&family=Crimson+Pro:wght@300;400;600&display=swap" rel="stylesheet">
<style>
:root {
  --parchment: #f7f2e8;
  --ink: #1a1208;
  --sepia-light: #e8dfc8;
  --sepia-mid: #c4aa7e;
  --sepia-dark: #7a5c2e;
  --accent: #8b1a1a;
  --word-del: #8b1a1a;
  --word-ins: #1a5c1a;
  --cap-color: #1a3a7a;
  --hyp-color: #5c3a1a;
  --border: rgba(196,170,126,0.35);
  --shadow: 0 2px 12px rgba(122,92,46,0.13);
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: var(--parchment); font-family: 'Crimson Pro', Georgia, serif; color: var(--ink); min-height: 100vh; }

header { background: var(--ink); color: var(--parchment); padding: 18px 24px 14px; border-bottom: 3px solid var(--sepia-dark); }
header h1 { font-family: 'EB Garamond', Georgia, serif; font-size: 1.7rem; font-weight: 600; letter-spacing: 0.04em; margin-bottom: 2px; }
header p { font-size: 0.88rem; opacity: 0.6; font-style: italic; }

.pair-bar { display: flex; background: #2a1f0e; border-bottom: 2px solid var(--sepia-dark); }
.pair-btn { flex: 1; padding: 11px 8px; text-align: center; cursor: pointer; color: rgba(247,242,232,0.5); font-size: 0.87rem; font-family: 'Crimson Pro', serif; transition: all 0.15s; border-right: 1px solid rgba(196,170,126,0.2); user-select: none; }
.pair-btn:last-child { border-right: none; }
.pair-btn:hover { color: var(--parchment); background: rgba(255,255,255,0.05); }
.pair-btn.active { color: var(--parchment); background: rgba(255,255,255,0.1); box-shadow: inset 0 -3px 0 var(--sepia-mid); font-weight: 600; }
.pair-btn .pair-count { display: block; font-size: 0.72rem; opacity: 0.65; margin-top: 1px; }

.stats-bar { display: flex; border-bottom: 1px solid var(--border); background: var(--sepia-light); }
.stat-pill { flex: 1; text-align: center; padding: 11px 6px; cursor: pointer; border-right: 1px solid var(--border); transition: background 0.15s; font-size: 0.82rem; font-family: 'Crimson Pro', serif; user-select: none; }
.stat-pill:last-child { border-right: none; }
.stat-pill:hover { background: var(--parchment); }
.stat-pill.active { background: var(--parchment); box-shadow: inset 0 -3px 0 var(--accent); }
.stat-num { font-size: 1.4rem; font-weight: 600; font-family: 'EB Garamond', serif; display: block; line-height: 1.1; }
.sn-all { color: var(--ink); } .sn-word { color: var(--word-del); } .sn-cap { color: var(--cap-color); } .sn-hyp { color: var(--hyp-color); }

.main-layout { display: flex; height: calc(100vh - 196px); overflow: hidden; }

.sidebar { width: 185px; min-width: 185px; border-right: 1px solid var(--border); background: var(--sepia-light); overflow-y: auto; font-size: 0.84rem; }
.sidebar-all { padding: 9px 13px; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.1em; color: var(--sepia-dark); font-weight: 600; border-bottom: 1px solid var(--border); font-family: 'Crimson Pro', serif; position: sticky; top: 0; background: var(--sepia-light); z-index: 5; cursor: pointer; }
.sidebar-all:hover, .sidebar-all.active { color: var(--accent); background: var(--parchment); }
.book-item { padding: 6px 13px; cursor: pointer; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border); transition: background 0.1s; }
.book-item:hover { background: var(--parchment); color: var(--accent); }
.book-item.active { background: var(--parchment); font-weight: 600; color: var(--accent); }
.book-badge { font-size: 0.7rem; background: var(--sepia-mid); color: var(--ink); border-radius: 10px; padding: 1px 6px; min-width: 20px; text-align: center; }

.results-panel { flex: 1; overflow-y: auto; }
.filter-bar { position: sticky; top: 0; z-index: 10; background: var(--parchment); border-bottom: 1px solid var(--border); padding: 8px 16px; display: flex; gap: 10px; align-items: center; }
.search-input { flex: 1; padding: 6px 11px; border: 1px solid var(--sepia-mid); border-radius: 4px; font-family: 'Crimson Pro', serif; font-size: 0.95rem; background: white; color: var(--ink); outline: none; }
.search-input:focus { border-color: var(--accent); }
.results-count { font-size: 0.8rem; color: var(--sepia-dark); white-space: nowrap; font-style: italic; }

.diff-list { padding: 10px 16px 32px; display: flex; flex-direction: column; gap: 9px; }
.diff-entry { border: 1px solid var(--border); border-radius: 6px; overflow: hidden; background: white; box-shadow: var(--shadow); }
.diff-header { display: flex; justify-content: space-between; align-items: center; padding: 6px 12px; background: var(--sepia-light); border-bottom: 1px solid var(--border); }
.diff-ref { font-family: 'EB Garamond', serif; font-weight: 600; font-size: 0.97rem; color: var(--sepia-dark); letter-spacing: 0.02em; }
.diff-badge { font-size: 0.68rem; padding: 2px 7px; border-radius: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; font-family: 'Crimson Pro', serif; }
.badge-word { background: rgba(139,26,26,0.1); color: var(--word-del); border: 1px solid rgba(139,26,26,0.3); }
.badge-capitalisation { background: rgba(26,58,122,0.1); color: var(--cap-color); border: 1px solid rgba(26,58,122,0.3); }
.badge-hyphenation { background: rgba(92,58,26,0.1); color: var(--hyp-color); border: 1px solid rgba(92,58,26,0.3); }

.diff-body { display: grid; grid-template-columns: 1fr 1fr; }
.diff-col { padding: 9px 12px; font-family: 'EB Garamond', serif; font-size: 0.97rem; line-height: 1.65; }
.diff-col:first-child { border-right: 1px solid var(--border); }
.diff-col-label { font-size: 0.66rem; text-transform: uppercase; letter-spacing: 0.1em; color: var(--sepia-dark); font-family: 'Crimson Pro', serif; margin-bottom: 3px; font-weight: 600; }
mark.del { background: rgba(139,26,26,0.1); color: var(--word-del); border-radius: 3px; padding: 0 2px; }
mark.ins { background: rgba(26,92,26,0.1); color: var(--word-ins); border-radius: 3px; padding: 0 2px; }

.empty-state { text-align: center; padding: 60px 20px; color: var(--sepia-dark); font-style: italic; font-size: 1.05rem; }
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--sepia-mid); border-radius: 3px; }
@media (max-width: 680px) {
  .sidebar { width: 120px; min-width: 120px; }
  .diff-body { grid-template-columns: 1fr; }
  .diff-col:first-child { border-right: none; border-bottom: 1px solid var(--border); }
}
</style>
</head>
<body>

<header>
  <h1>&#8213; KJV Bible Comparison &#8213;</h1>
  <p>Three-source comparison &mdash; excluding italics &amp; apostrophe differences</p>
</header>

<div class="pair-bar">
  <div class="pair-btn active" id="pairbtn-b1_b2">
    aruljohn vs farskipper
    <span class="pair-count" id="pcount-b1_b2"></span>
  </div>
  <div class="pair-btn" id="pairbtn-b1_b3">
    aruljohn vs kjvonline
    <span class="pair-count" id="pcount-b1_b3"></span>
  </div>
  <div class="pair-btn" id="pairbtn-b2_b3">
    farskipper vs kjvonline
    <span class="pair-count" id="pcount-b2_b3"></span>
  </div>
</div>

<div class="stats-bar">
  <div class="stat-pill active" id="pill-all"><span class="stat-num sn-all" id="cnt-all">0</span>All</div>
  <div class="stat-pill" id="pill-word"><span class="stat-num sn-word" id="cnt-word">0</span>Word changes</div>
  <div class="stat-pill" id="pill-capitalisation"><span class="stat-num sn-cap" id="cnt-cap">0</span>Capitalisation</div>
  <div class="stat-pill" id="pill-hyphenation"><span class="stat-num sn-hyp" id="cnt-hyp">0</span>Hyphenation</div>
</div>

<div class="main-layout">
  <div class="sidebar">
    <div class="sidebar-all active" id="sidebar-all">&#9776; All Books</div>
    <div id="book-list"></div>
  </div>
  <div class="results-panel">
    <div class="filter-bar">
      <input class="search-input" id="search-box" type="text" placeholder="Search reference or verse text&#x2026;">
      <span class="results-count" id="results-count"></span>
    </div>
    <div class="diff-list" id="diff-list"></div>
  </div>
</div>

<script>
''')

parts.append('const RAW = ')
parts.append(data_js)
parts.append(''';
</script>
<script>
(function() {
  var currentPair = 'b1_b2';
  var currentCat = 'all';
  var currentBook = 'ALL';

  var PAIR_NAMES = {
    b1_b2: ['aruljohn/Bible-kjv', 'farskipper/kjv'],
    b1_b3: ['aruljohn/Bible-kjv', 'kjvonline.org'],
    b2_b3: ['farskipper/kjv', 'kjvonline.org']
  };

  var BADGE = {
    word: '<span class="diff-badge badge-word">Word</span>',
    capitalisation: '<span class="diff-badge badge-capitalisation">Capitalisation</span>',
    hyphenation: '<span class="diff-badge badge-hyphenation">Hyphenation</span>'
  };

  function esc(s) { return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

  // Populate pair counts
  ['b1_b2','b1_b3','b2_b3'].forEach(function(p) {
    document.getElementById('pcount-' + p).textContent = RAW.totals[p].total + ' differences';
  });

  function updateStats() {
    var t = RAW.totals[currentPair];
    document.getElementById('cnt-all').textContent = t.total;
    document.getElementById('cnt-word').textContent = t.word;
    document.getElementById('cnt-cap').textContent = t.capitalisation;
    document.getElementById('cnt-hyp').textContent = t.hyphenation;
  }

  function buildBookList() {
    var bookList = document.getElementById('book-list');
    bookList.innerHTML = '';
    var books = RAW.books[currentPair];
    Object.keys(books).forEach(function(book) {
      var stats = books[book];
      var el = document.createElement('div');
      el.className = 'book-item' + (book === currentBook ? ' active' : '');
      el.setAttribute('data-book', book);
      var nameSpan = document.createElement('span');
      nameSpan.textContent = book;
      var badge = document.createElement('span');
      badge.className = 'book-badge';
      badge.textContent = stats.total;
      el.appendChild(nameSpan);
      el.appendChild(badge);
      el.addEventListener('click', function() { selectBook(book); });
      bookList.appendChild(el);
    });
  }

  function selectBook(book) {
    currentBook = book;
    document.querySelectorAll('.book-item').forEach(function(el) {
      el.classList.toggle('active', el.getAttribute('data-book') === book);
    });
    document.getElementById('sidebar-all').classList.toggle('active', book === 'ALL');
    renderDiffs();
  }

  function setPair(pair) {
    currentPair = pair;
    currentBook = 'ALL';
    currentCat = 'all';
    ['b1_b2','b1_b3','b2_b3'].forEach(function(p) {
      document.getElementById('pairbtn-' + p).classList.toggle('active', p === pair);
    });
    ['all','word','capitalisation','hyphenation'].forEach(function(c) {
      document.getElementById('pill-' + c).classList.toggle('active', c === 'all');
    });
    document.getElementById('sidebar-all').classList.add('active');
    document.getElementById('search-box').value = '';
    updateStats();
    buildBookList();
    renderDiffs();
  }

  function setCat(cat) {
    currentCat = cat;
    ['all','word','capitalisation','hyphenation'].forEach(function(c) {
      document.getElementById('pill-' + c).classList.toggle('active', c === cat);
    });
    renderDiffs();
  }

  function renderDiffs() {
    var search = document.getElementById('search-box').value.trim().toLowerCase();
    var filtered = RAW.pairs[currentPair];

    if (currentCat !== 'all') {
      filtered = filtered.filter(function(d) { return d.category === currentCat; });
    }
    if (currentBook !== 'ALL') {
      filtered = filtered.filter(function(d) { return d.book === currentBook; });
    }
    if (search) {
      filtered = filtered.filter(function(d) {
        return d.ref.toLowerCase().indexOf(search) !== -1 ||
               d.a.toLowerCase().indexOf(search) !== -1 ||
               d.b.toLowerCase().indexOf(search) !== -1;
      });
    }

    document.getElementById('results-count').textContent = filtered.length + (filtered.length === 1 ? ' verse' : ' verses');

    var names = PAIR_NAMES[currentPair];
    var nameA = names[0], nameB = names[1];
    var list = document.getElementById('diff-list');

    if (filtered.length === 0) {
      list.innerHTML = '<div class="empty-state">No differences found for this selection.</div>';
      return;
    }

    var html = '';
    for (var i = 0; i < filtered.length; i++) {
      var d = filtered[i];
      html += '<div class="diff-entry">' +
        '<div class="diff-header">' +
          '<span class="diff-ref">' + esc(d.ref) + '</span>' +
          BADGE[d.category] +
        '</div>' +
        '<div class="diff-body">' +
          '<div class="diff-col"><div class="diff-col-label">' + esc(nameA) + '</div>' + d.ha + '</div>' +
          '<div class="diff-col"><div class="diff-col-label">' + esc(nameB) + '</div>' + d.hb + '</div>' +
        '</div>' +
      '</div>';
    }
    list.innerHTML = html;
  }

  ['b1_b2','b1_b3','b2_b3'].forEach(function(p) {
    document.getElementById('pairbtn-' + p).addEventListener('click', function() { setPair(p); });
  });
  ['all','word','capitalisation','hyphenation'].forEach(function(c) {
    document.getElementById('pill-' + c).addEventListener('click', function() { setCat(c); });
  });
  document.getElementById('sidebar-all').addEventListener('click', function() { selectBook('ALL'); });
  document.getElementById('search-box').addEventListener('input', renderDiffs);

  updateStats();
  buildBookList();
  renderDiffs();
})();
</script>
</body>
</html>
''')

html = ''.join(parts)
with open('/home/claude/bible3way_pairs_final.html', 'w') as f:
    f.write(html)
print("Written, size:", len(html))

import json, re, glob, os, difflib
from collections import defaultdict

def normalize(text):
    t = re.sub(r'\[([^\]]+)\]', r'\1', text)
    t = t.replace('\u2019', "'").replace('\u2018', "'").replace('\u02bc', "'")
    t = re.sub(r'^# ', '', t)
    t = re.sub(r' +', ' ', t).strip()
    return t

# Load B1
b1 = {}
for filepath in glob.glob('../kjv/*.json'):
    fname = os.path.basename(filepath).replace('.json','')
    if fname == 'Books': continue
    with open(filepath) as f:
        data = json.load(f)
    book_name = data['book']
    for ch in data['chapters']:
        for v in ch['verses']:
            ref = f"{book_name} {ch['chapter']}:{v['verse']}"
            b1[ref] = normalize(v['text'])

# Load B2
with open('../farskipper/kjv/json/verses-1769.json') as f:
    b2_raw = json.load(f)
b2 = {ref: normalize(text) for ref, text in b2_raw.items()}

# Load B3
with open('../scraping/kjv.json') as f:
    b3_raw = json.load(f)
b3 = {}
for book, chapters in b3_raw.items():
    for ch_num, verses in chapters.items():
        for v_num, text in verses.items():
            b3[f"{book} {ch_num}:{v_num}"] = normalize(text)

BOOK_ORDER = ["Genesis","Exodus","Leviticus","Numbers","Deuteronomy","Joshua","Judges","Ruth",
"1 Samuel","2 Samuel","1 Kings","2 Kings","1 Chronicles","2 Chronicles","Ezra","Nehemiah",
"Esther","Job","Psalms","Proverbs","Ecclesiastes","Song of Solomon","Isaiah","Jeremiah",
"Lamentations","Ezekiel","Daniel","Hosea","Joel","Amos","Obadiah","Jonah","Micah","Nahum",
"Habakkuk","Zephaniah","Haggai","Zechariah","Malachi","Matthew","Mark","Luke","John","Acts",
"Romans","1 Corinthians","2 Corinthians","Galatians","Ephesians","Philippians","Colossians",
"1 Thessalonians","2 Thessalonians","1 Timothy","2 Timothy","Titus","Philemon","Hebrews",
"James","1 Peter","2 Peter","1 John","2 John","3 John","Jude","Revelation"]

def get_book(ref):
    parts = ref.split(' ')
    return parts[0] + ' ' + parts[1] if parts[0][0].isdigit() else parts[0]

def highlight_pair(t1, t2):
    def tok(t): return re.split(r'(\W+)', t)
    w1, w2 = tok(t1), tok(t2)
    sm = difflib.SequenceMatcher(None, w1, w2, autojunk=False)
    h1, h2 = [], []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == 'equal':
            h1.append(''.join(w1[i1:i2]))
            h2.append(''.join(w2[j1:j2]))
        elif op == 'replace':
            h1.append('<mark class="del">' + ''.join(w1[i1:i2]) + '</mark>')
            h2.append('<mark class="ins">' + ''.join(w2[j1:j2]) + '</mark>')
        elif op == 'delete':
            h1.append('<mark class="del">' + ''.join(w1[i1:i2]) + '</mark>')
        elif op == 'insert':
            h2.append('<mark class="ins">' + ''.join(w2[j1:j2]) + '</mark>')
    return ''.join(h1), ''.join(h2)

def categorize(t1, t2):
    if t1 == t2: return None
    if t1.lower() == t2.lower(): return 'capitalisation'
    if re.sub(r'-', '', t1.lower()) == re.sub(r'-', '', t2.lower()): return 'hyphenation'
    return 'word'

def sort_key(ref):
    book = get_book(ref)
    idx = BOOK_ORDER.index(book) if book in BOOK_ORDER else 99
    return (idx, ref)

# Build diffs for all 3 pairs separately
pairs = {
    'b1_b2': (b1, b2, 'aruljohn/Bible-kjv', 'farskipper/kjv'),
    'b1_b3': (b1, b3, 'aruljohn/Bible-kjv', 'kingjamesbibleonline.org'),
    'b2_b3': (b2, b3, 'farskipper/kjv', 'kingjamesbibleonline.org'),
}

pair_diffs = {}
pair_books = {}
pair_totals = {}

for pair_key, (ba, bb, na, nb) in pairs.items():
    common = set(ba.keys()) & set(bb.keys())
    diffs = []
    book_stats = defaultdict(lambda: defaultdict(int))

    for ref in sorted(common, key=sort_key):
        ta, tb = ba[ref], bb[ref]
        cat = categorize(ta, tb)
        if cat is None: continue
        ha, hb = highlight_pair(ta, tb)
        book = get_book(ref)
        book_stats[book]['total'] += 1
        book_stats[book][cat] += 1
        diffs.append({'ref': ref, 'book': book, 'a': ta, 'b': tb, 'ha': ha, 'hb': hb, 'category': cat})

    totals = {'total': len(diffs)}
    for cat in ['word','capitalisation','hyphenation']:
        totals[cat] = sum(1 for d in diffs if d['category']==cat)

    pair_diffs[pair_key] = diffs
    pair_books[pair_key] = {bk: dict(book_stats[bk]) for bk in BOOK_ORDER if bk in book_stats}
    pair_totals[pair_key] = totals
    print(f"{pair_key}: {len(diffs)} diffs — {totals}")

output = {'pairs': pair_diffs, 'books': pair_books, 'totals': pair_totals}
with open('bible_pairs.json', 'w') as f:
    json.dump(output, f)
print("Done. Size:", os.path.getsize('bible_pairs.json'))

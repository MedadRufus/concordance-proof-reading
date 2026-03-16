"""Utilities to convert ODT text references to HTML anchors linking to the KJV.

This module uses spaCy lemmatization to robustly match root words (e.g., ADVERSITY)
to their inflected forms in the KJV (e.g., adversities, advantageth).
"""

import argparse
import html
import io
import json
import os
import re

from odf import teletype
from odf.opendocument import load
from odf.text import P

KJV_JSON_PATH = "kjv"

# Bible book abbreviation mapping
BOOK_ABBR_TO_FULL = {
    # Old Testament
    "Gen.": "Genesis",
    "Ex.": "Exodus",
    "Lev.": "Leviticus",
    "Num.": "Numbers",
    "Deu.": "Deuteronomy",
    "Josh.": "Joshua",
    "Judg.": "Judges",
    "Ruth": "Ruth",
    "1 Sam.": "1 Samuel",
    "2 Sam.": "2 Samuel",
    "1 Ki.": "1 Kings",
    "2 Ki.": "2 Kings",
    "1 Chr.": "1 Chronicles",
    "2 Chr.": "2 Chronicles",
    "Ezra": "Ezra",
    "Neh.": "Nehemiah",
    "Esth.": "Esther",
    "Job": "Job",
    "Ps.": "Psalms",
    "Prov.": "Proverbs",
    "Eccl.": "Ecclesiastes",
    "Song": "Song of Solomon",
    "Is.": "Isaiah",
    "Jer.": "Jeremiah",
    "Lam.": "Lamentations",
    "Eze.": "Ezekiel",
    "Dan.": "Daniel",
    "Hos.": "Hosea",
    "Joel": "Joel",
    "Amos": "Amos",
    "Obad.": "Obadiah",
    "Jonah": "Jonah",
    "Micah": "Micah",
    "Nah.": "Nahum",
    "Hab.": "Habakkuk",
    "Zeph.": "Zephaniah",
    "Hag.": "Haggai",
    "Zech.": "Zechariah",
    "Mal.": "Malachi",
    # New Testament
    "Mt.": "Matthew",
    "Mk.": "Mark",
    "Lk.": "Luke",
    "Jn.": "John",
    "Acts": "Acts",
    "Rom.": "Romans",
    "1 Cor.": "1 Corinthians",
    "2 Cor.": "2 Corinthians",
    "Gal.": "Galatians",
    "Eph.": "Ephesians",
    "Phil.": "Philippians",
    "Col.": "Colossians",
    "1 Thess.": "1 Thessalonians",
    "2 Thess.": "2 Thessalonians",
    "1 Tim.": "1 Timothy",
    "2 Tim.": "2 Timothy",
    "Tit.": "Titus",
    "Philem.": "Philemon",
    "Heb.": "Hebrews",
    "Jas.": "James",
    "1 Pet.": "1 Peter",
    "2 Pet.": "2 Peter",
    "1 Jn.": "1 John",
    "2 Jn.": "2 John",
    "3 Jn.": "3 John",
    "Jude": "Jude",
    "Rev.": "Revelation",
}

# Books with a single chapter where references are commonly written as "Philem. 9"
# rather than "Philem. 1:9"
SINGLE_CHAPTER_ABBR = {"Obad.", "Philem.", "2 Jn.", "3 Jn.", "Jude"}
SINGLE_CHAPTER_BOOKS = {BOOK_ABBR_TO_FULL[a] for a in SINGLE_CHAPTER_ABBR if a in BOOK_ABBR_TO_FULL}

# Build regex patterns. I Medad barely understand the regex. The only thing that I read are the
# unittests which have concrete test cases.
sorted_abbrs = sorted(BOOK_ABBR_TO_FULL, key=lambda x: -len(x))
# For chapter:verse matching we should NOT match single-chapter book abbreviations
non_single = [a for a in sorted_abbrs if a not in SINGLE_CHAPTER_ABBR]
single = [a for a in sorted_abbrs if a in SINGLE_CHAPTER_ABBR]

NON_SINGLE_PATTERN = "|".join(re.escape(a) for a in non_single)
SINGLE_PATTERN = "|".join(re.escape(a) for a in single)

# Pattern supports two branches:
#  - regular (book + chapter:verse[, ...]) for non-single-chapter books
#  - verse-only (book + verse[, ...]) for single-chapter books (e.g., 'Philem. 9')
BRANCH_MULTI_CHP_BOOKS = (
    rf"(?P<abbr1>{NON_SINGLE_PATTERN})\s+(?P<refs1>\d+:\d+(?:,\s*(?:\d+:\d+|\d+))*)"
)
BRANCH_SINGLE_CHP_BOOKS = rf"(?P<abbr2>{SINGLE_PATTERN})\s+(?P<refs2>\d+(?:,\s*\d+)*)(?!:)"
ref_pattern = re.compile(rf"\b(?:{BRANCH_MULTI_CHP_BOOKS}|{BRANCH_SINGLE_CHP_BOOKS})")

# Pattern to detect orphan numbers/references that look like they should be linked
# but weren't caught by the main ref_pattern.
# Matches things like: "119:107", "58:3", "13:36", "5.8", "9.21,23"
# i.e. a number (with optional dot-separated sub-number or colon-verse) that appears
# in prose context (not already inside an HTML tag).
ORPHAN_REF_PATTERN = re.compile(
    r"""
    (?<![="\w])          # not preceded by = or " (i.e. not inside an HTML attribute)
    \b
    (
        \d+              # chapter / psalm number
        (?:              # optionally followed by:
            [:.]\d+      # :verse  or  .verse  (OCR dot-for-colon)
            (?:,\s*\d+)* # and more comma-separated verses
        )?
    )
    \b
    (?!["\w])            # not followed by " or word char (not inside HTML attribute)
    """,
    re.VERBOSE,
)


def load_kjv(path):
    """Load KJV verse JSON from `path` and return the parsed mapping."""
    kjv_verses = {}

    for filename in os.listdir(path):
        if filename.endswith(".json") and filename != "Books.json":
            filepath = os.path.join(path, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                book = data["book"]
                for chapter_data in data["chapters"]:
                    chapter = chapter_data["chapter"]
                    for verse_data in chapter_data["verses"]:
                        verse = verse_data["verse"]
                        text = verse_data["text"]
                        key = f"{book} {chapter}:{verse}"
                        kjv_verses[key] = text
    return kjv_verses


class Reference:  # pylint: disable=too-many-instance-attributes
    """Represent a parsed Bible reference and produce HTML anchor/link information."""

    # 10 args are justified here - it's a data carrier.
    def __init__(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        abbr,
        book,
        chapter,
        verse,
        single_chapter,
        matched_text,
        part,
        has_colon,
        verses,
        root_word,
    ):
        """Initialize a Reference."""
        self.abbr = abbr
        self.book = book
        self.chapter = chapter
        self.verse = verse
        self.single_chapter = single_chapter
        self.matched_text = matched_text
        self.part = part
        self.has_colon = has_colon
        self.verses = verses
        self.root_word = root_word

    def visible(self, index):
        """Return the visible text for the reference at the given position."""
        if self.single_chapter:
            if index == 0:
                return f"{self.abbr} {self.verse}"
            return self.verse if not self.has_colon else self.part.split(":", 1)[1]
        if index == 0:
            return f"{self.abbr} {self.chapter}:{self.verse}"
        return self.part if self.has_colon else self.verse

    # KJV archaic/variant spellings → modern concordance root equivalences.
    # Maps a KJV word (lowercase) to the set of modern roots it satisfies.
    _KJV_VARIANTS: dict = {
        # shew / shewed / sheweth / shewn  →  SHOW
        "shew": {"show"}, "shewed": {"show"}, "sheweth": {"show"},
        "shewn": {"show"}, "shewing": {"show"},
        # hungred → HUNGERED / HUNGER
        "hungred": {"hungered", "hunger"},
        # nought → NAUGHT
        "nought": {"naught"},
        # brasen → BRAZEN
        "brasen": {"brazen"},
        # graffed / graff → GRAFT
        "graffed": {"graft"}, "graff": {"graft"},
        # veil → VAIL
        "veil": {"vail"},
        # dipped → DIPT
        "dipped": {"dipt"},
        # calves → CALF
        "calves": {"calf"},
        # burned / burneth → BURNT
        "burned": {"burnt"}, "burneth": {"burnt"},
        # lothe / lothed → LOATHE
        "lothe": {"loathe"}, "lothed": {"loathe"},
        # envying / envyings → ENVY / ENVIOUS / ENVIEST
        "envying": {"envy", "envious", "enviest"},
        "envyings": {"envy", "envious", "enviest"},
        "envieth": {"envy", "envious", "enviest"},
        # acknowledgement → ACKNOWLEDGMENT
        "acknowledgement": {"acknowledgment"},
        # acceptably → ACCEPTABLE
        "acceptably": {"acceptable"},
        # assaying → ASSAYED
        "assaying": {"assayed"},
        # beauties → BEAUTY
        "beauties": {"beauty"},
        # bellies → BELLY
        "bellies": {"belly"},
        # blotting → BLOTTETH
        "blotting": {"blotteth"},
        # bramble → BRAMBLES
        "bramble": {"brambles"},
        # brawler → BRAWLERS
        "brawler": {"brawlers"},
        # brigandines / brigandine → BRIGANTINE
        "brigandines": {"brigantine"}, "brigandine": {"brigantine"},
        # bulrush → BULRUSHES
        "bulrush": {"bulrushes"},
        # contentious → CONTENTIONS
        "contentious": {"contentions"},
        # contentment → CONTENTIONS / CONTENT
        "contentment": {"contentions", "content"},
        # deceivableness → DECEIVE
        "deceivableness": {"deceive"},
        # delightest → DELIGHTETH
        "delightest": {"delighteth"},
        # delights → DELIGHTSOME
        "delights": {"delightsome"},
        # desirest → DESIRED
        "desirest": {"desired"},
        # discovereth → DISCOVERED
        "discovereth": {"discovered"},
        # edifieth → EDIFY
        "edifieth": {"edify"},
        # enrichest → ENRICHED
        "enrichest": {"enriched"},
        # entereth → ENTERED
        "entereth": {"entered"},
        # espousals → ESPUSAIS
        "espousals": {"espusais"},
        # expedient → EXPEDITENT
        "expedient": {"expeditent"},
        # farthing → FARTHINGS
        "farthing": {"farthings"},
        # feign → FEIGNED
        "feign": {"feigned"},
        # forbad → FORBADE
        "forbad": {"forbade"},
        # foreknew → FOREKNOW
        "foreknew": {"foreknow"},
        # grudgingly → GRUDGE
        "grudgingly": {"grudge"},
        # heretick → HERESY
        "heretick": {"heresy"},
        # horseleach → HORSELEECH
        "horseleach": {"horseleech"},
        # imputing → IMPUTETH
        "imputing": {"imputeth"},
        # instructer → INSTRUCTOR
        "instructer": {"instructor"},
        # instructing → INSTRUCTED
        "instructing": {"instructed"},
        # journeyings → JOURNEYS
        "journeyings": {"journeys"},
        # justifieth → JUSTIFIED
        "justifieth": {"justified"},
        # killest → KILLEDST
        "killest": {"killedst"},
        # lingereth → LINGERED
        "lingereth": {"lingered"},
        # messias → MESSIAH
        "messias": {"messiah"},
        # outcast → OUTCASTS
        "outcast": {"outcasts"},
        # pacified / pacifieth → PACIFY
        "pacified": {"pacify"}, "pacifieth": {"pacify"},
        # planteth → PLANTED
        "planteth": {"planted"},
        # plowmen → PLOWMAN
        "plowmen": {"plowman"},
        # poureth → POURED
        "poureth": {"poured"},
        # preeminence → PREFERENCE
        "preeminence": {"preference"},
        # proceeding → PROCEEDETH
        "proceeding": {"proceedeth"},
        # prophesieth / prophesied → PROPHESY
        "prophesieth": {"prophesy"}, "prophesied": {"prophesy"},
        # prospereth → PROSPERED
        "prospereth": {"prospered"},
        # puffeth → PUFFED
        "puffeth": {"puffed"},
        # purifieth → PURIFY
        "purifieth": {"purify"},
        # purified → PURIFY
        "purified": {"purify"},
        # quieteth → QUIETED
        "quieteth": {"quieted"},
        # remembereth → REMEMBERED
        "remembereth": {"remembered"},
        # repayed → REPAID
        "repayed": {"repaid"},
        # repairing → REPAIRER
        "repairing": {"repairer"},
        # reproachfully → REPROACHES
        "reproachfully": {"reproaches"},
        # sanctifieth / sanctified → SANCTIFY
        "sanctifieth": {"sanctify"}, "sanctify": {"sanctified"},
        # satisfieth → SATISFY
        "satisfieth": {"satisfy"},
        # scrip → SCRIPT
        "scrip": {"script"},
        # seasoned / season → SEASONED
        "season": {"seasoned"},
        # slave → SLAVER
        "slave": {"slaver"},
        # sorceress → SORCERER
        "sorceress": {"sorcerer"},
        # sottish → SOTHS
        "sottish": {"soths"},
        # stoicks → STOICS
        "stoicks": {"stoics"},
        # subverting / subvert / subverted → SUBVERTER
        "subverting": {"subverter"}, "subvert": {"subverter"},
        "subverted": {"subverter"},
        # subtilty → SUBTILITY
        "subtilty": {"subtility"},
        # suretiship / surety → SURETYSHIP
        "suretiship": {"suretyship"}, "surety": {"suretyship"},
        # tarriest → TARRY
        "tarriest": {"tarry"},
        # tattlers → TATLERS
        "tattlers": {"tatlers"},
        # terrifiest / terrified → TERRIFY
        "terrifiest": {"terrify"}, "terrified": {"terrify"},
        # testifieth → TESTIFY
        "testifieth": {"testify"},
        # thought → THOUGHTS
        "thought": {"thoughts"},
        # transforming → TRANSFORMED
        "transforming": {"transformed"},
        # treasurest → TREASURED
        "treasurest": {"treasured"},
        # troubled → TROUBLES
        "troubled": {"troubles"},
        # troubleth → TROUBLER
        "troubleth": {"troubler"},
        # trieth → TRY
        "trieth": {"try"},
        # unblameably → UNBLAMEABLE
        "unblameably": {"unblameable"},
        # unmoveable → UNMOVABLE
        "unmoveable": {"unmovable"},
        # unworthily → UNWORTHY
        "unworthily": {"unworthy"},
        # visitest / visiting → VISITED
        "visitest": {"visited"}, "visiting": {"visited"},
        # watchmen → WATCHMAN
        "watchmen": {"watchman"},
        # weighing / weigh → WEIGHT
        "weigh": {"weight"},
        # wellpleasing → PLEASE
        "wellpleasing": {"please"},
        # whet → WHEP
        "whet": {"whep"},
        # wizard → WIZARDS
        "wizard": {"wizards"},
        # revealed/revelation → REV entries already matched by substring
        # increasing → INCREASED
        "increasing": {"increased"},
        # increaseth → INCREASED
        "increaseth": {"increased"},
        # changeth → CHANGED
        "changeth": {"changed"},
        # chastiseth → CHASTISED
        "chastiseth": {"chastised"},
        # eagle → EAGLES
        "eagle": {"eagles"},
        # enchanment → INCHANTMENT
        "enchantment": {"inchantment"},
        # exile → EXCILE
        "exile": {"excile"},
        # excuse / excused → EXECUSE
        "excuse": {"execuse"}, "excused": {"execuse"},
        # inflaming → INFLAME
        "enflaming": {"inflame"},
        # lingereth → LINGERED
        # passeth → PASSETH (already substring)
        # peaceably → PEACEABLE
        "peaceably": {"peaceable"},
        # perverted → PREVERTED
        "perverted": {"preverted"},
        # proceeding → PROCEEDETH (already above)
        # prospereth → PROSPERED (already above)
        # subverting → SUBVERTER (already above)
        # gins → GRIN (snares/traps in KJV)
        "gins": {"grin"},
        # knoweth → KNOWEST
        "knoweth": {"knowest"},
        # contentious → CONTENTIONS (already above)
        # dainties → DAINTY
        "dainties": {"dainty"},
        # denying → DENIED
        "denying": {"denied"},
        # revellings → RIOT
        "revellings": {"riot"},
        # free → FREEMAN / FREEWOMAN
        "free": {"freeman", "freewoman"},
        # saviour → SAVETH (KJV uses Saviour where concordance uses SAVETH)
        "saviour": {"saveth", "save", "saved", "saves"},
        # boil (singular) → BOILS
        "boil": {"boils"},
        # care (singular) → CARES
        "care": {"cares"},
        # beasts → CREATURES (four living creatures = beasts in KJV)
        "beasts": {"creatures"},
        # beast → CREATURES
        "beast": {"creatures"},
        # wilfully → WILLFULLY (KJV spelling)
        "wilfully": {"willfully"},
        # entangle / entangled → INTANGLE (concordance spelling)
        "entangle": {"intangle"}, "entangled": {"intangle"},
        # entreated → INTREATED (KJV 'en' vs concordance 'in')
        "entreated": {"intreated"},
        # engrafted → INGRAFTED
        "engrafted": {"ingrafted"},
        # marriage → ESPUSAIS (espousal/marriage)
        "marriage": {"espusais"},
        # sanctification → SAME (wrong verse assignment — leave as-is)
        # end (no end) → ENDURE (wrong verse)
        # outwardly → OUTSTRETCHED (wrong verse)
        # debtor/debtors → DEATH (wrong verse — concordance error)
        # caldrons → CALAMITY (wrong verse — concordance error)
    }

    def find_root_word_matches(self, clean_verse, root_word):
        """Find matches of root word in the verse and return bolded version with matches highlighted."""
        root_lower = root_word.lower()
        verse_lower = clean_verse.lower()

        # Extended suffix list covering KJV verb forms and common derivations
        ROOT_SUFFIXES = [
            "", "s", "es", "ed", "ing", "ly", "eth", "est", "er", "ers",
            "ness", "ment", "ment", "ation", "ation", "ful", "less",
            "ieth", "ied", "ier", "iest",
            "ily", "ally", "ably", "ibly",
        ]

        # Also generate candidate stems from root for suffix-stripped matching:
        # e.g. root=JUSTIFY → stem=justifi, justif; root=SANCTIFY → sanctif
        stems = {root_lower}
        if root_lower.endswith("y"):
            stems.add(root_lower[:-1] + "i")   # justify → justifi
            stems.add(root_lower[:-1])           # justify → justif (for justifieth)
        if root_lower.endswith("e"):
            stems.add(root_lower[:-1])           # arise → aris (for arising)
        if root_lower.endswith("ed"):
            stems.add(root_lower[:-2])           # baptized → baptiz
            stems.add(root_lower[:-1])           # baptized → baptize
        if root_lower.endswith("ing"):
            stems.add(root_lower[:-3])           # backsliding → backsli
            stems.add(root_lower[:-3] + "e")

        def word_matches_root(word_lower):
            """Return True if word_lower is a form of root_lower."""
            # Direct containment
            if root_lower in word_lower:
                return True
            # Direct suffix expansion of root
            if any(word_lower == root_lower + sfx for sfx in ROOT_SUFFIXES):
                return True
            # Root ends in 'e': drop-e before suffix
            if root_lower.endswith("e"):
                stem = root_lower[:-1]
                if any(word_lower == stem + sfx
                       for sfx in ["ing", "ed", "er", "ers", "ingly", "eth"]):
                    return True
            # Root ends in 'y': y→ies, y→ied, y→ier
            if root_lower.endswith("y"):
                stem = root_lower[:-1]
                if any(word_lower == stem + sfx
                       for sfx in ["ies", "ied", "ier", "ieth", "ily"]):
                    return True
            # Root ends in 'ic': +ally
            if root_lower.endswith("ic") and word_lower == root_lower + "ally":
                return True
            # Root ends in consonant: double consonant + ing/ed
            if (len(root_lower) >= 3 and root_lower[-1] == root_lower[-2]
                    and root_lower[-1] not in "aeiou"):
                stem = root_lower[:-1]
                if any(word_lower == stem + sfx for sfx in ["ing", "ed", "er"]):
                    return True
            # Stem-based matching (covers forms like justifi+eth → justifieth)
            for stem in stems:
                if stem and word_lower.startswith(stem) and len(word_lower) > len(stem):
                    return True
            # KJV variant spelling lookup: verse word maps to this root
            kjv_roots = Reference._KJV_VARIANTS.get(word_lower, set())
            if root_lower in kjv_roots:
                return True
            return False

        # Quick pre-check: is there ANY potential match in the verse?
        verse_words_set = set(re.findall(r"\b\w+\b", verse_lower))
        has_match = any(word_matches_root(w) for w in verse_words_set)
        if not has_match:
            return None, False

        # Full pass: bold every matching word
        words = re.findall(r"\b\w+\b|\W+", clean_verse)
        matched_any = False
        bolded_parts = []
        for word in words:
            if word.isalnum():
                if word_matches_root(word.lower()):
                    bolded_parts.append(f"<strong>{html.escape(word)}</strong>")
                    matched_any = True
                else:
                    bolded_parts.append(html.escape(word))
            else:
                bolded_parts.append(html.escape(word))

        return "".join(bolded_parts), matched_any

    def get_full_verse_key(self):
        """Return full verse key like 'Proverbs 24:24'."""
        return f"{self.book} {self.chapter}:{self.verse}"

    def to_anchor(self, index: int, issues: list | None = None) -> str:
        """Construct the anchor HTML for this reference with a real tooltip span.

        If *issues* is provided, append a dict describing any problem found so
        the summary table at the top of the page can link directly to it.
        """
        full_key = self.get_full_verse_key()
        verse = self.verses.get(full_key, "")
        visible = self.visible(index)

        url = (
            "https://www.biblegateway.com/passage/?search="
            f"{self.book}+{self.chapter}%3A{self.verse}&version=KJV"
        )

        issue_id: str | None = None

        if not verse:
            css_class = "bible-ref-missing"
            ref_text = f"{visible} [REF NOT FOUND]"
            tooltip_content = f"{full_key} (KJV) - Reference not found"
            issue_id = f"issue-{len(issues)}" if issues is not None else None
            if issues is not None:
                issues.append({
                    "id": issue_id,
                    "type": "ref-not-found",
                    "label": ref_text,
                    "detail": full_key,
                    "root": self.root_word,
                })
        else:
            root = self.root_word
            bolded_verse, matched_any = self.find_root_word_matches(verse, root)

            if matched_any:
                css_class = "bible-ref"
                ref_text = visible
                tooltip_content = (
                    f"<strong>{html.escape(root)}</strong>: {full_key} (KJV) - {bolded_verse}"
                )
            else:
                css_class = "bible-ref-no-root"
                ref_text = f"{visible} [ROOT WORD MISSING]"
                tooltip_content = f"{full_key} (KJV) - {html.escape(verse)}"
                issue_id = f"issue-{len(issues)}" if issues is not None else None
                if issues is not None:
                    issues.append({
                        "id": issue_id,
                        "type": "root-missing",
                        "label": ref_text,
                        "detail": full_key,
                        "root": self.root_word,
                    })

        id_attr = f' id="{issue_id}"' if issue_id else ""
        escaped_ref_text = html.escape(ref_text)
        return (
            f'<span class="ref-pair"{id_attr}>'
            f'<a href="{html.escape(url)}" class="{css_class}">{escaped_ref_text}</a>'
            f'<span class="tooltip">{tooltip_content}</span>'
            f"</span>"
        )


def parse_references_with_root(text, verses, root_word):
    """Parse references in `text` and attach `root_word` to each."""
    results = []
    for match in ref_pattern.finditer(text):
        abbr = match.group("abbr1") or match.group("abbr2")
        refs_part = match.group("refs1") or match.group("refs2")
        full_book = BOOK_ABBR_TO_FULL.get(abbr, abbr)
        single_chapter = full_book in SINGLE_CHAPTER_BOOKS

        parts = [p.strip() for p in refs_part.split(",")]
        current_chapter = None

        for part in parts:
            if has_colon := ":" in part:
                chapter, verse = part.split(":", 1)
                current_chapter = chapter
            else:
                chapter = "1" if single_chapter else current_chapter
                verse = part

            if chapter is None:
                continue  # skip malformed

            results.append(
                Reference(
                    abbr=abbr,
                    book=full_book,
                    chapter=chapter,
                    verse=verse,
                    single_chapter=single_chapter,
                    matched_text=match.group(0),
                    part=part,
                    has_colon=has_colon,
                    verses=verses,
                    root_word=root_word,
                )
            )
    return results


def highlight_orphan_numbers(html_fragment: str, issues: list | None = None) -> str:
    """
    In the rendered HTML fragment, find numeric tokens that look like they could
    be Bible references (e.g. "119:107", "58:3", "5.8") but are sitting in plain
    text — i.e. NOT already inside any HTML element (tag or its content).

    Those tokens are wrapped in <span class="ocr-suspect"> so they stand out
    visually as likely OCR errors / missed references.

    Strategy: track nesting depth by scanning open/close tags.  Only text at
    depth 0 (outside all tags) is eligible for highlighting.
    """
    TOKEN_RE = re.compile(r"(</?[a-zA-Z][^>]*?>|<!--.*?-->)", re.DOTALL)

    ORPHAN_RE = re.compile(
        r"\b\d+[:.]\d+(?:,\s*\d+)*\b"  # chapter:verse  or  chapter.verse
        r"|\b\d+\.\d+\b"               # number.number (OCR dot-for-colon)
    )

    def replace_orphan(m):
        token = m.group(0)
        issue_id = f"issue-{len(issues)}" if issues is not None else None
        if issues is not None:
            issues.append({
                "id": issue_id,
                "type": "unlinked-ref",
                "label": token,
                "detail": "Possible OCR error or unrecognised reference format",
                "root": None,
            })
        id_attr = f' id="{issue_id}"' if issue_id else ""
        return (
            f'<span class="ref-pair"{id_attr}>'
            f'<span class="ocr-suspect">Unlinked: {token}</span>'
            f'<span class="tooltip">Possible OCR error / unlinked reference: {token}</span>'
            f'</span>'
        )

    parts = TOKEN_RE.split(html_fragment)
    result = []
    depth = 0  # HTML nesting depth

    for part in parts:
        if TOKEN_RE.fullmatch(part):
            # It's a tag token — adjust depth and pass through unchanged.
            if part.startswith("</"):
                depth = max(0, depth - 1)
            elif not part.endswith("/>"):  # not self-closing
                depth += 1
            result.append(part)
        else:
            # Plain text run — only highlight when we're at the top level,
            # i.e. not inside any HTML element's content.
            if depth == 0:
                result.append(ORPHAN_RE.sub(replace_orphan, part))
            else:
                result.append(part)

    return "".join(result)


def convert_odt_bytes_to_html(odt_bytes):
    """Convert ODT bytes to an HTML string (keeps everything in memory)."""

    kjv_verses = load_kjv(KJV_JSON_PATH)

    bio = io.BytesIO(odt_bytes)
    doc = load(bio)

    issues: list = []
    paragraphs = extract_paragraphs(doc, kjv_verses, issues)

    style = """
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            margin: 10em;
        }
        p {
            margin: 0 0 1em 0;
        }

        /* ── Issues summary table ───────────────────────────────────────── */
        #issues-summary {
            border-collapse: collapse;
            width: 100%;
            margin-bottom: 3em;
            font-size: 13px;
        }
        #issues-summary caption {
            font-size: 16px;
            font-weight: bold;
            text-align: left;
            padding: 0 0 0.5em 0;
            color: #333;
        }
        #issues-summary th {
            background: #f0f0f0;
            border: 1px solid #ccc;
            padding: 6px 10px;
            text-align: left;
            white-space: nowrap;
        }
        #issues-summary td {
            border: 1px solid #ddd;
            padding: 5px 10px;
            vertical-align: top;
        }
        #issues-summary tr:nth-child(even) td {
            background: #fafafa;
        }
        #issues-summary tr:hover td {
            background: #f5f5f5;
        }
        .issue-badge {
            display: inline-block;
            border-radius: 3px;
            padding: 1px 6px;
            font-size: 11px;
            font-weight: bold;
            white-space: nowrap;
        }
        .badge-ref-not-found  { background:#ffe6e6; color:#cc0000; border:1px solid #cc0000; }
        .badge-root-missing   { background:#fff9e6; color:#cc6600; border:1px solid #cc6600; }
        .badge-unlinked-ref   { background:#ffe6e6; color:#cc0000; border:1px solid #cc0000; }
        #issues-summary a.jump-link {
            color: #0055aa;
            text-decoration: none;
            font-weight: bold;
        }
        #issues-summary a.jump-link:hover { text-decoration: underline; }

        /* Reference pair container */
        .ref-pair {
            position: relative;
            display: inline-block;
            margin-right: 0.2em;
        }

        /* Tooltip styling */
        .tooltip {
            position: absolute;
            bottom: 100%;
            left: 50%;
            transform: translateX(-50%);
            background: #333;
            color: white;
            padding: 8px 12px;
            border-radius: 4px;
            font-size: 12px;
            z-index: 1000;
            opacity: 0;
            visibility: hidden;
            pointer-events: none;
            white-space: normal;
            min-width: 200px;
            word-wrap: break-word;
            margin-bottom: 6px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.3);
            transition: opacity 0.2s ease;
        }

        .ref-pair:hover .tooltip {
            opacity: 1;
            visibility: visible;
        }

        /* Link styles */
        .bible-ref {
            color: #0066cc;
            cursor: help;
            border-bottom: 1px dotted #0066cc;
            text-decoration: none;
        }
        .bible-ref:hover {
            background-color: #f0f8ff;
            text-decoration: underline;
        }

        .bible-ref-missing {
            color: #cc0000;
            cursor: help;
            border-bottom: 2px solid #cc0000;
            text-decoration: none;
            background-color: #ffe6e6;
        }
        .bible-ref-missing:hover {
            background-color: #ffcccc;
            text-decoration: underline;
        }

        .bible-ref-no-root {
            color: #cc6600;
            cursor: help;
            border-bottom: 2px dashed #cc6600;
            text-decoration: none;
            background-color: #fff9e6;
        }
        .bible-ref-no-root:hover {
            background-color: #ffebcc;
            text-decoration: underline;
        }

        /* Enhanced highlighting for matched words in tooltips */
        .tooltip strong {
            background-color: #ffff00; /* Yellow background */
            color: #000; /* Black text */
            padding: 1px 2px;
            border-radius: 2px;
            font-weight: bold;
        }

        /* OCR suspect / unlinked reference — same style as ref-not-found */
        .ocr-suspect {
            color: #cc0000;
            cursor: help;
            border-bottom: 2px solid #cc0000;
            text-decoration: none;
            background-color: #ffe6e6;
            font-weight: bold;
        }
    """

    return write_html(paragraphs, style, issues)


def extract_root_word(txt):
    """Extract the root word from the given text."""
    root_word = None
    words = re.split(r"(\s+)", txt)  # keep whitespace for position tracking
    i = 0
    while i < len(words):
        w = words[i].strip()
        if not w:
            i += 1
            continue

        # Candidate: all caps, length ≥ 2, no punctuation inside (ignore trailing .,;)
        clean_w = re.sub(r"[.,;:!?\)]*$", "", w)
        if clean_w.isalpha() and clean_w.isupper() and len(clean_w) >= 2:
            # Look ahead: next non-whitespace token should NOT be all-caps (unless multi-word root — rare)
            j = i + 1
            while j < len(words) and words[j].isspace():
                j += 1
            if j < len(words):
                next_token = re.sub(r"[.,;:!?\)]*$", "", words[j])
                if (next_token and next_token[0].islower()) or next_token in {
                    "I",
                    "a",
                    "the",
                    "his",
                    "her",
                    "their",
                    "my",
                    "thy",
                    "ye",
                    "you",
                    "we",
                    "it",
                }:
                    root_word = clean_w
                    break
            # Also accept if next token is punctuation (e.g., comma)
            elif j < len(words) and re.match(r"^[,\.\-\)]", words[j]):
                root_word = clean_w
                break
        i += 1

    if root_word is None:
        # Fallback: use first all-caps word ≥2 chars, even if imperfect
        fallback_match = re.search(r"\b([A-Z]{2,})\b", txt)
        if fallback_match:
            root_word = fallback_match.group(1)

    return root_word


def extract_paragraphs(doc, verses, issues: list):
    paragraphs = []

    all_elements = doc.getElementsByType(P)

    for idx, elem in enumerate(all_elements):
        raw_txt = teletype.extractText(elem)
        if not raw_txt.strip():
            continue
        txt = re.sub(r"\s+", " ", raw_txt).strip()

        # Extract root word using the new function
        root_word = extract_root_word(txt)

        if root_word is None:
            # No root word found → treat as plain text
            paragraphs.append(html.escape(txt))
            continue

        # Now split by |, but only after root word
        # Remove root word from txt for segment parsing
        # Find where root_word appears (first occurrence)
        root_pos = txt.find(root_word)
        if root_pos == -1:
            paragraphs.append(html.escape(txt))
            continue

        remainder = txt[root_pos + len(root_word) :].lstrip()
        segments = [s.strip() for s in remainder.split("|") if s.strip()]

        # Create a closure to avoid repeated function creation
        def create_substitution_function(verses, root_word, issues):
            def substitute_references(match):
                refs = parse_references_with_root(match.group(0), verses, root_word)
                anchor_texts = [ref.to_anchor(i, issues) for i, ref in enumerate(refs)]
                result = ", ".join(anchor_texts)
                return result if result else html.escape(match.group(0))

            return substitute_references

        substitution_func = create_substitution_function(verses, root_word, issues)

        rendered_segments = []
        for seg in segments:
            new_seg = ref_pattern.sub(substitution_func, seg)
            # After linking known references, highlight any leftover orphan numbers
            new_seg = highlight_orphan_numbers(new_seg, issues)
            rendered_segments.append(new_seg)

        final_line = f"<strong>{html.escape(root_word)}</strong> " + " | ".join(rendered_segments)
        paragraphs.append(final_line)

    return paragraphs


def build_issues_table(issues: list) -> str:
    """Return an HTML table summarising all issues, with jump-to links."""
    if not issues:
        return '<p><em>No issues found.</em></p>\n'

    BADGE = {
        "ref-not-found": ('<span class="issue-badge badge-ref-not-found">Ref not found</span>', "Ref not found"),
        "root-missing":  ('<span class="issue-badge badge-root-missing">Root word missing</span>', "Root word missing"),
        "unlinked-ref":  ('<span class="issue-badge badge-unlinked-ref">Unlinked reference</span>', "Unlinked reference"),
    }

    # Count by type for the header summary line
    counts: dict[str, int] = {}
    for issue in issues:
        counts[issue["type"]] = counts.get(issue["type"], 0) + 1

    summary_parts = []
    for itype, (badge_html, _) in BADGE.items():
        if itype in counts:
            summary_parts.append(f"{badge_html} &times; {counts[itype]}")
    summary_line = " &nbsp; ".join(summary_parts)

    rows = []
    for n, issue in enumerate(issues, start=1):
        itype = issue["type"]
        badge_html = BADGE.get(itype, (html.escape(itype), itype))[0]
        label = html.escape(issue["label"])
        detail = html.escape(issue["detail"])
        root = html.escape(issue["root"]) if issue["root"] else "—"
        issue_id = issue["id"]
        jump = f'<a class="jump-link" href="#{issue_id}" title="Jump to occurrence in document">↓ {label}</a>'
        rows.append(
            f"<tr>"
            f"<td>{n}</td>"
            f"<td>{badge_html}</td>"
            f"<td>{jump}</td>"
            f"<td>{detail}</td>"
            f"<td>{root}</td>"
            f"</tr>"
        )

    rows_html = "\n".join(rows)
    return f"""<table id="issues-summary">
  <caption>Issues summary &mdash; {len(issues)} total &nbsp; ({summary_line})</caption>
  <thead>
    <tr>
      <th>#</th>
      <th>Type</th>
      <th>Reference</th>
      <th>Verse key</th>
      <th>Root word</th>
    </tr>
  </thead>
  <tbody>
{rows_html}
  </tbody>
</table>
"""


def write_html(paragraphs, style, issues: list | None = None):
    """Write *paragraphs* to an HTML string wrapped in a simple HTML document.

    If *issues* is provided, an issues-summary table is inserted at the top of
    the ``<body>`` so the reader can see all problems at a glance and click
    through to each occurrence.
    """
    html_content = (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '    <meta charset="UTF-8">\n'
        "    <title>Bible Concordance</title>\n"
        f"    <style>{style}</style>\n"
        "</head>\n"
        "<body>\n"
    )
    if issues is not None:
        html_content += build_issues_table(issues)
    for p in paragraphs:
        html_content += f"<p>{p}</p>\n"
    html_content += "</body>\n</html>"
    return html_content


def convert_odt_to_html(odt_path, html_path):
    """Compatibility wrapper: read file and save to disk."""
    if not os.path.exists(odt_path):
        raise FileNotFoundError(f"File '{odt_path}' not found.")

    with open(odt_path, "rb") as f:
        odt_bytes = f.read()

    html_content = convert_odt_bytes_to_html(odt_bytes)

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    return html_path


def main():
    """Convert an ODT file with Bible references to an HTML file with hyperlinks."""
    parser = argparse.ArgumentParser(
        description="Convert an ODT file with Bible references to an HTML file with hyperlinks."
    )
    parser.add_argument("input_odt", help="The path to the input ODT file.")
    parser.add_argument("output_html", help="The path to the output HTML file.")
    args = parser.parse_args()

    out = convert_odt_to_html(args.input_odt, args.output_html)
    print(f"Success: HTML saved to {out}")


if __name__ == "__main__":
    # Example usage:
    # python3 add_hyperlinks.py input/concordance.odt output/concordance.html
    main()

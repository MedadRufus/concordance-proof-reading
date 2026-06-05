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

NON_SINGLE_PATTERN = "|".join(re.escape(a).replace(r"\ ", r"[\  \xa0]") for a in non_single)
SINGLE_PATTERN = "|".join(re.escape(a).replace(r"\ ", r"[\  \xa0]") for a in single)

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
        # bulrush → BULRUSHES
        "bulrush": {"bulrushes"},
        # contentious → CONTENTIONS
        "contentious": {"contentions"},
        # contentment →  CONTENT
        "contentment": {"content"},
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
        # wizard → WIZARDS
        "wizard": {"wizards"},
        # ankles (modern KJV editions) → ANCLES (archaic concordance spelling)
        "ankles": {"ancles"},
        # cloak (some KJV editions) → CLOKE (archaic concordance spelling)
        "cloak": {"cloke"},
        # honor / honored (some KJV editions) → HONOUR
        "honor": {"honour"}, "honored": {"honour"}, "honoring": {"honour"},
        # long-suffering (hyphenated in some KJV editions) → LONGSUFFERING
        "long-suffering": {"longsuffering"},
        # standard / bearer (KJV editions that hyphenate standard-bearer) → STANDARDBEARER
        "standard": {"standardbearer"}, "bearer": {"standardbearer"},
        # stumble / stumbling (1 Pet 2:8 has 'stone of stumbling') → STUMBLINGSTONE
        "stumble": {"stumblingstone"}, "stumbling": {"stumblingstone"},
        # wondrously variant spellings
        "wonderously": {"wondrously"}, "wondrously": {"wondrously"},
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
        # knoweth → KNOWEST
        "knoweth": {"knowest"},
        # contentious → CONTENTIONS (already above)
        # dainties → DAINTY
        "dainties": {"dainty"},
        # denying → DENIED
        "denying": {"denied"},
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
        # sanctification → SAME (wrong verse assignment — leave as-is)
        # end (no end) → ENDURE (wrong verse)
        # outwardly → OUTSTRETCHED (wrong verse)
        # debtor/debtors → DEATH (wrong verse — concordance error)
        # caldrons → CALAMITY (wrong verse — concordance error)
        # firstripe (KJV spelling) → FRISTRIPE (concordance spelling for FIRSTRIPE)
        "firstripe": {"fristripe", "firstripe"},
    }

    def find_root_word_matches(self, clean_verse, root_word):
        """Find matches of root word in the verse and return bolded version with matches highlighted.

        Returns (html_verse, matched_any, variants_found) where variants_found is a sorted
        list of the distinct word forms of root_word that appeared in the verse.
        """
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
            # Compound-word prefix check: verse splits a compound at a hyphen,
            # so individual parts (e.g. 'long', 'standard', 'stumbling') should
            # match roots that start with them (e.g. 'longsuffering',
            # 'standardbearer', 'stumblingstone').
            # Guard with minimum length to avoid false positives.
            if len(word_lower) >= 4 and root_lower.startswith(word_lower):
                return True
            return False

        # Quick pre-check: is there ANY potential match in the verse?
        verse_words_set = set(re.findall(r"\b\w+\b", verse_lower))
        has_match = any(word_matches_root(w) for w in verse_words_set)
        if not has_match:
            return None, False, []

        # Full pass: bold every matching word
        words = re.findall(r"\b\w+\b|\W+", clean_verse)
        matched_any = False
        variants_found: list[str] = []
        bolded_parts = []
        for word in words:
            if word.isalnum():
                if word_matches_root(word.lower()):
                    bolded_parts.append(f"<strong>{html.escape(word)}</strong>")
                    matched_any = True
                    if word.lower() not in [v.lower() for v in variants_found]:
                        variants_found.append(word)
                else:
                    bolded_parts.append(html.escape(word))
            else:
                bolded_parts.append(html.escape(word))

        return "".join(bolded_parts), matched_any, sorted(variants_found, key=str.lower)

    def get_full_verse_key(self):
        """Return full verse key like 'Proverbs 24:24'."""
        return f"{self.book} {self.chapter}:{self.verse}"

    def to_anchor(self, index: int, issues: list ) -> str:
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
            ref_text = visible
            tooltip_content = (
                f"<span class='tip-label tip-missing'>❌ Wrong reference</span>"
                f"<span class='tip-verse-key'>{html.escape(full_key)}</span>"
                f"This verse does not exist in the KJV. "
                f"Check the reference in the ODT and correct the chapter/verse number."
            )
            issue_id = f"issue-{len(issues)}" if issues is not None else None
            if issues is not None:
                issues.append({
                    "id": issue_id,
                    "type": "ref-not-found",
                    "label": visible,
                    "detail": full_key,
                    "root": self.root_word,
                })
        else:
            root = self.root_word
            bolded_verse, matched_any, variants = self.find_root_word_matches(verse, root)

            if matched_any:
                # Determine if the match was on the exact root word or only on variant forms
                exact_match = any(v.lower() == root.lower() for v in variants)
                other_forms = [v for v in variants if v.lower() != root.lower()]

                if exact_match:
                    css_class = "bible-ref"
                    tip_label = "<span class='tip-label tip-ok'>✔ Linked</span>"
                else:
                    # Only variant forms found — make this visually distinct
                    css_class = "bible-ref-variant"
                    tip_label = "<span class='tip-label tip-variant'>~ Variant form</span>"
                    issue_id = f"issue-{len(issues)}" if issues is not None else None
                    if issues is not None:
                        forms_str = ", ".join(other_forms)
                        issues.append({
                            "id": issue_id,
                            "type": "variant-form",
                            "label": visible,
                            "detail": full_key,
                            "root": self.root_word,
                            "forms": forms_str,
                        })

                ref_text = visible
                variants_html = ""
                if other_forms:
                    forms_str = html.escape(", ".join(other_forms))
                    variants_html = f"<span class='tip-variants'>Variant forms found: {forms_str}</span>"
                tooltip_content = (
                    f"{tip_label}"
                    f"<span class='tip-verse-key'>{html.escape(full_key)}</span>"
                    f"<em>{bolded_verse}</em>"
                    f"{variants_html}"
                )
            else:
                css_class = "bible-ref-no-root"
                ref_text = visible
                tooltip_content = (
                    f"<span class='tip-label tip-noroot'>⚠ Wrong verse?</span>"
                    f"<span class='tip-verse-key'>{html.escape(full_key)}</span>"
                    f"The word <strong style='background:#ffff00;color:#000'>{html.escape(root)}</strong> "
                    f"does not appear in this verse. The reference may point to the wrong verse — "
                    f"check and correct it in the ODT.<br><br>"
                    f"<em>{html.escape(verse)}</em>"
                )
                issue_id = f"issue-{len(issues)}" if issues is not None else None
                if issues is not None:
                    issues.append({
                        "id": issue_id,
                        "type": "root-missing",
                        "label": visible,
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
        # Normalise non-breaking space in numbered-book abbreviations
        # so "1\xa0Cor." looks up correctly as "1 Cor." in the dict
        abbr_key = abbr.replace("\xa0", " ")
        full_book = BOOK_ABBR_TO_FULL.get(abbr_key, abbr_key)
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
                    abbr=abbr_key,
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




_LORD_PAT = re.compile(r"\b(LORD|Lord)\b")

def _replace_lord_in_seg(seg, lord_lookup):
    ref_positions = []
    for m in ref_pattern.finditer(seg):
        abbr = m.group("abbr1") or m.group("abbr2")
        refs_raw = m.group("refs1") or m.group("refs2")
        abbr_key = abbr.replace("\xa0", " ")
        full_book = BOOK_ABBR_TO_FULL.get(abbr_key, abbr_key)
        single = full_book in SINGLE_CHAPTER_BOOKS
        cur_ch = None
        for part in refs_raw.split(","):
            part = part.strip()
            if ":" in part:
                cur_ch, verse = part.split(":", 1)
            else:
                verse = part
                if single: cur_ch = "1"
            if cur_ch:
                ref_positions.append((m.start(), f"{full_book} {cur_ch}:{verse}"))
    out = []; last = 0
    for m in _LORD_PAT.finditer(seg):
        out.append(html.escape(seg[last:m.start()]))
        last = m.end()
        key = next((k for p, k in ref_positions if p >= m.start()), None)
        if key is None:
            key = next((k for p, k in reversed(ref_positions) if p < m.start()), None)
        forms = lord_lookup.get(key, frozenset()) if key else frozenset()
        if forms == frozenset({"LORD"}):
            out.append('L<span class="lord-sc">ord</span>')
        else:
            out.append(html.escape(m.group()))
    out.append(html.escape(seg[last:]))
    return "".join(out)

def highlight_orphan_numbers(html_fragment: str, issues: list) -> str:
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
            f'<span class="ocr-suspect">{token}</span>'
            f'<span class="tooltip">'
            f"<span class='tip-label tip-unlinked'>🔗 Unlinked number</span>"
            f"<span class='tip-verse-key'>{token}</span>"
            f"This looks like a Bible reference but has no book name attached. "
            f"Add the missing book abbreviation before this number in the ODT "
            f"(e.g. change <em>{token}</em> to <em>Ps. {token}</em>)."
            f'</span>'
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

    style = ""  # styles are now in write_html directly

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


LORD_SC_MARKER = "\x00LORD_SC\x00"  # placeholder preserved through plain-text processing

_TEXT_ATTR  = ("urn:oasis:names:tc:opendocument:xmlns:text:1.0", "style-name")
_SPACE_ATTR = ("urn:oasis:names:tc:opendocument:xmlns:text:1.0", "c")
_SPACE_QNAME = ("urn:oasis:names:tc:opendocument:xmlns:text:1.0", "s")


def _extract_text_with_lord(elem) -> str:
    """Extract text from an ODT paragraph element, replacing
    L + <text:span T9990>ord</text:span>  with LORD_SC_MARKER."""
    from odf.element import Element

    parts = []

    def walk(node):
        if not isinstance(node, Element):
            parts.append(str(node) if node is not None else "")
            return
        # text:s (space) element
        if node.qname == _SPACE_QNAME:
            count = int(node.attributes.get(_SPACE_ATTR, "1"))
            parts.append(" " * count)
            return
        # Check for our small-caps span
        if node.attributes.get(_TEXT_ATTR) == "T9990":
            inner = "".join(
                str(c) for c in node.childNodes
                if not isinstance(c, Element)
            )
            if inner == "ord" and parts and parts[-1].endswith("L"):
                parts[-1] = parts[-1][:-1]
                parts.append(LORD_SC_MARKER)
                return
            else:
                parts.append(inner)
                return
        for child in node.childNodes:
            walk(child)

    walk(elem)
    return "".join(parts)


def extract_paragraphs(doc, verses, issues: list, lord_lookup: dict = None):
    paragraphs = []

    all_elements = doc.getElementsByType(P)

    for idx, elem in enumerate(all_elements):
        raw_txt = _extract_text_with_lord(elem)
        if not raw_txt.strip():
            continue
        txt = re.sub(r"[ \t\r\n]+", " ", raw_txt).strip()

        # Extract root word using the new function
        root_word = extract_root_word(txt)

        if root_word is None:
            # No root word found → treat as plain text
            plain = html.escape(txt).replace(LORD_SC_MARKER, 'L<span class="lord-sc">ord</span>')
            paragraphs.append(plain)
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
            if lord_lookup:
                # Replace LORD/Lord in plain text BEFORE ref linkification,
                # using nearest KJV verse to determine the correct form.
                seg_html = _replace_lord_in_seg(seg, lord_lookup)
                # Now linkify refs: run substitution_func against original seg,
                # then replace the escaped ref text in the lord-rendered html.
                for m in ref_pattern.finditer(seg):
                    anchor = substitution_func(m)
                    seg_html = seg_html.replace(html.escape(m.group(0)), anchor, 1)
                new_seg = seg_html
            else:
                new_seg = ref_pattern.sub(substitution_func, seg)
            # Convert LORD_SC_MARKER (from ODT small-caps span) to HTML
            new_seg = new_seg.replace(LORD_SC_MARKER, 'L<span class="lord-sc">ord</span>')
            new_seg = highlight_orphan_numbers(new_seg, issues)
            rendered_segments.append(new_seg)

        final_line = f"<strong>{html.escape(root_word)}</strong> " + " | ".join(rendered_segments)
        final_line = final_line.replace(LORD_SC_MARKER, 'L<span class="lord-sc">ord</span>')
        paragraphs.append(final_line)

    return paragraphs


def build_issues_panel(issues: list) -> str:
    """Return a sticky sidebar panel listing all issues with jump links."""
    if not issues:
        return (
            '<div id="issues-panel">'
            '<div id="panel-header">'
            '<strong>Issues to fix</strong>'
            '<span class="panel-counts">'
            '<span class="pc all-clear">✔ No issues</span>'
            '</span>'
            '</div>'
            '<div class="panel-section panel-allclear">'
            '<div class="section-explain" style="padding-top:8px;">'
            'All references checked out — no wrong verses, missing references, or unlinked numbers found.'
            '</div>'
            '</div>'
            '</div>'
        )

    counts: dict[str, int] = {}
    for issue in issues:
        counts[issue["type"]] = counts.get(issue["type"], 0) + 1

    n_missing  = counts.get("ref-not-found", 0)
    n_noroot   = counts.get("root-missing", 0)
    n_unlinked = counts.get("unlinked-ref", 0)
    n_variant  = counts.get("variant-form", 0)

    # Group rows by type so editor can tackle one category at a time
    sections = [
        ("ref-not-found", "❌ Wrong reference",   "panel-missing",  n_missing,
         "This verse does not exist in the KJV — the chapter/verse number is wrong."),
        ("root-missing",  "⚠ Wrong verse?",       "panel-noroot",   n_noroot,
         "The heading word isn't found in this verse — may point to the wrong verse."),
        ("variant-form",  "~ Variant form",        "panel-variant",  n_variant,
         "The heading word appears in a different form in this verse (e.g. abased for ABASE)."),
        ("unlinked-ref",  "🔗 Unlinked number",   "panel-unlinked", n_unlinked,
         "Looks like a reference but has no book name — add the book abbreviation."),
    ]

    html_parts = ['<div id="issues-panel">']
    html_parts.append('<div id="panel-header">')
    html_parts.append('<strong>Issues to fix</strong>')
    html_parts.append(
        f'<span class="panel-counts">'
        f'<span class="pc missing">{n_missing} wrong ref</span>'
        f'<span class="pc noroot">{n_noroot} wrong verse?</span>'
        f'<span class="pc variant">{n_variant} variant</span>'
        f'<span class="pc unlinked">{n_unlinked} unlinked</span>'
        f'</span>'
    )
    html_parts.append('</div>')  # panel-header

    for itype, label, css, count, explanation in sections:
        if count == 0:
            continue
        group_issues = [iss for iss in issues if iss["type"] == itype]
        html_parts.append(f'<div class="panel-section {css}">')
        html_parts.append(f'<div class="section-heading">{label} <span class="section-count">{count}</span></div>')
        html_parts.append(f'<div class="section-explain">{explanation}</div>')
        html_parts.append('<ol class="issue-list">')
        for iss in group_issues:
            root_note = f' <span class="root-note">({html.escape(iss["root"])})</span>' if iss.get("root") else ""
            forms_note = f' <span class="root-note">→ {html.escape(iss["forms"])}</span>' if iss.get("forms") else ""
            html_parts.append(
                f'<li><a class="jump-link" href="#{iss["id"]}">'
                f'{html.escape(iss["label"])}</a>'
                f'{root_note}{forms_note}'
                f'<span class="verse-key">{html.escape(iss["detail"])}</span>'
                f'</li>'
            )
        html_parts.append('</ol>')
        html_parts.append('</div>')  # panel-section

    html_parts.append('</div>')  # issues-panel
    return '\n'.join(html_parts)


def build_legend() -> str:
    """Return a compact colour-key legend bar."""
    return """
<div id="legend">
  <strong>Colour key:</strong>
  <span class="leg leg-ok">Blue = linked correctly ✔ (hover to see verse)</span>
  <span class="leg leg-variant">Green background = ~ variant form — heading word found in a different form</span>
  <span class="leg leg-missing">Red background = ❌ wrong reference — verse doesn't exist</span>
  <span class="leg leg-noroot">Amber background = ⚠ wrong verse? — heading word not found in verse</span>
  <span class="leg leg-unlinked">Red underline = 🔗 unlinked number — missing book name</span>
  &nbsp;&nbsp;<strong>Lord:</strong>
  <span class="leg">L<span class="lord-sc">ord</span> = <em>LORD</em> in KJV (YHWH)</span>
  <span class="leg">Lord = <em>Lord</em> in KJV (Adonai)</span>
</div>
"""


def write_html(paragraphs, _style_unused, issues: list):
    """Write paragraphs to a self-contained HTML document optimised for hand-editing review."""

    style = """
/* ── Reset & base ─────────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; }
body {
    font-family: Georgia, serif;
    font-size: 15px;
    line-height: 1.7;
    background: #f7f7f5;
    color: #222;
    margin: 0;
    padding: 0;
}

/* ── Layout: sidebar + main ───────────────────────────────────── */
#layout {
    display: flex;
    align-items: flex-start;
    min-height: 100vh;
}
#main {
    flex: 1;
    min-width: 0;
    padding: 2em 3em 4em 2em;
    max-width: 900px;
}
p {
    margin: 0 0 0.6em 0;
    padding: 3px 6px;
    border-radius: 3px;
}
p:hover {
    background: #efefec;
}

/* ── Legend bar ───────────────────────────────────────────────── */
#legend {
    background: #fff;
    border: 1px solid #ddd;
    border-radius: 6px;
    padding: 10px 16px;
    margin-bottom: 1.8em;
    font-size: 13px;
    line-height: 2;
}
#legend strong { margin-right: 12px; }
.leg { display: inline-block; margin-right: 16px; padding: 2px 8px; border-radius: 3px; }
.leg-ok      { color: #0066cc; border-bottom: 1px dotted #0066cc; }
.leg-missing { background: #ffe6e6; color: #cc0000; font-weight: bold; }
.leg-noroot  { background: #fff3cd; color: #7a4f00; border-bottom: 2px dashed #cc8800; }
.leg-unlinked{ color: #cc0000; border-bottom: 2px solid #cc0000; font-weight: bold; }
.leg-variant { background: #e6f4ee; color: #0a6640; border-bottom: 2px solid #0a9960; }

/* ── Sticky sidebar panel ─────────────────────────────────────── */
#issues-panel {
    width: 280px;
    min-width: 260px;
    position: sticky;
    top: 0;
    max-height: 100vh;
    overflow-y: auto;
    background: #fff;
    border-right: 1px solid #ddd;
    font-size: 12.5px;
    line-height: 1.5;
    padding-bottom: 2em;
}
#panel-header {
    background: #2c3e50;
    color: #fff;
    padding: 12px 14px;
    position: sticky;
    top: 0;
    z-index: 10;
}
#panel-header strong { font-size: 14px; display: block; margin-bottom: 6px; }
.panel-counts { display: flex; gap: 6px; flex-wrap: wrap; }
.pc {
    padding: 2px 7px;
    border-radius: 10px;
    font-size: 11px;
    font-weight: bold;
    white-space: nowrap;
}
.pc.missing  { background: #ffe6e6; color: #cc0000; }
.pc.noroot   { background: #fff3cd; color: #7a4f00; }
.pc.unlinked { background: #ffe6e6; color: #cc0000; }
.pc.all-clear { background: #d4edda; color: #155724; }
.pc.variant  { background: #d4edda; color: #0a6640; }

.panel-section { border-bottom: 1px solid #eee; padding: 10px 14px; }
.panel-missing .section-heading { color: #cc0000; }
.panel-noroot  .section-heading { color: #7a4f00; }
.panel-unlinked .section-heading { color: #cc0000; }
.panel-variant .section-heading { color: #0a6640; }
.section-heading {
    font-weight: bold;
    font-size: 12.5px;
    margin-bottom: 4px;
    display: flex;
    align-items: center;
    gap: 6px;
}
.section-count {
    background: #eee;
    color: #333;
    border-radius: 8px;
    padding: 0 6px;
    font-size: 11px;
}
.section-explain {
    color: #666;
    font-size: 11.5px;
    margin-bottom: 6px;
    font-style: italic;
}
.issue-list {
    margin: 0;
    padding-left: 18px;
}
.issue-list li {
    margin-bottom: 5px;
}
.jump-link {
    color: #0055cc;
    text-decoration: none;
    font-weight: bold;
}
.jump-link:hover { text-decoration: underline; }
.root-note {
    color: #888;
    font-size: 11px;
    font-style: italic;
}
.verse-key {
    display: block;
    color: #999;
    font-size: 11px;
    padding-left: 2px;
}

/* ── Reference pair & tooltip ─────────────────────────────────── */
.ref-pair {
    position: relative;
    display: inline-block;
}
.tooltip {
    display: none;
    position: absolute;
    bottom: calc(100% + 6px);
    left: 50%;
    transform: translateX(-50%);
    background: #1a1a2e;
    color: #eee;
    padding: 10px 14px;
    border-radius: 6px;
    font-size: 12.5px;
    font-family: Arial, sans-serif;
    line-height: 1.5;
    z-index: 9999;
    min-width: 260px;
    max-width: 420px;
    word-wrap: break-word;
    box-shadow: 0 4px 16px rgba(0,0,0,0.35);
    white-space: normal;
    pointer-events: none;
}
.ref-pair:hover .tooltip { display: block; }

/* Tooltip inner labels */
.tip-label {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 3px;
    font-weight: bold;
    font-size: 11px;
    margin-bottom: 5px;
}
.tip-ok      { background: #1a6b1a; color: #fff; }
.tip-missing { background: #cc0000; color: #fff; }
.tip-noroot  { background: #cc8800; color: #fff; }
.tip-unlinked{ background: #cc0000; color: #fff; }
.tip-variant { background: #1a6b55; color: #fff; }
.tip-verse-key {
    display: block;
    color: #aad4ff;
    font-size: 11.5px;
    font-weight: bold;
    margin-bottom: 5px;
}
.tip-variants {
    display: block;
    color: #aaffcc;
    font-size: 11px;
    margin-top: 5px;
    font-style: italic;
}
.tooltip em { color: #ddd; font-style: normal; }
.tooltip strong {
    background: #ffff00;
    color: #000;
    padding: 0 2px;
    border-radius: 2px;
}

/* ── Bible reference link styles ──────────────────────────────── */
.bible-ref {
    color: #0066cc;
    text-decoration: none;
    border-bottom: 1px dotted #0066cc;
    cursor: help;
}
.bible-ref:hover { background: #e8f0fe; }

.bible-ref-variant {
    color: #0a6640;
    background: #e6f4ee;
    border-bottom: 2px solid #0a9960;
    text-decoration: none;
    cursor: help;
    padding: 0 2px;
    border-radius: 2px;
}
.bible-ref-variant:hover { background: #c3e8d4; }

.bible-ref-missing {
    color: #cc0000;
    font-weight: bold;
    background: #ffe6e6;
    border-bottom: 2px solid #cc0000;
    text-decoration: none;
    cursor: help;
    padding: 0 2px;
    border-radius: 2px;
}
.bible-ref-missing:hover { background: #ffcccc; }

.bible-ref-no-root {
    color: #7a4f00;
    background: #fff3cd;
    border-bottom: 2px dashed #cc8800;
    text-decoration: none;
    cursor: help;
    padding: 0 2px;
    border-radius: 2px;
}
.bible-ref-no-root:hover { background: #ffe8a0; }

.ocr-suspect {
    color: #cc0000;
    font-weight: bold;
    border-bottom: 2px solid #cc0000;
    cursor: help;
    padding: 0 1px;
}

/* LORD (tetragrammaton): L + small-caps ord, matching ODT rendering */
.lord-sc { font-variant: small-caps; }

/* ── Scroll-to highlight ──────────────────────────────────────── */
:target {
    outline: 3px solid #f5a623;
    outline-offset: 2px;
    border-radius: 2px;
    animation: flash 1.8s ease-out;
}
@keyframes flash {
    0%   { background: #fff3cd; }
    100% { background: transparent; }
}
"""

    issues_panel = build_issues_panel(issues if issues is not None else [])
    legend = build_legend()

    paras_html = '\n'.join(f'<p>{p}</p>' for p in paragraphs)

    return (
        '<!DOCTYPE html>\n'
        '<html lang="en">\n'
        '<head>\n'
        '  <meta charset="UTF-8">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '  <title>Bible Concordance — Editor Review</title>\n'
        f'  <style>{style}</style>\n'
        '</head>\n'
        '<body>\n'
        '<div id="layout">\n'
        f'{issues_panel}\n'
        '<div id="main">\n'
        f'{legend}\n'
        f'{paras_html}\n'
        '</div>\n'  # #main
        '</div>\n'  # #layout
        '</body>\n</html>'
    )


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

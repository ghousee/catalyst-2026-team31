"""Structure-aware chunker for HP NonStop manuals (text extracted from the PDFs).

Pure logic, no I/O beyond reading the text you pass in, so it is unit-testable without Docker.

Pipeline: pages (split on form feed) -> drop running headers/footers/page numbers -> drop TOC/index
pages -> paragraphs -> section boundaries -> pack/split/merge to ~300-800 tokens.

Section boundaries come from three signals (extracted text has no reliable indentation):
  1. a short paragraph equal to a title found in the manual's own table of contents;
  2. a message/event number paragraph (e.g. "3001", "MEAS 3000", "*3001* TERM ...");
  3. the short paragraph(s) right before a "Cause." paragraph (FUP-style all-caps message titles).
"""
import re
from dataclasses import dataclass

CHARS_PER_TOKEN = 3.5  # rough estimate for manual text; the real count is reported by the embedder
MIN_TOKENS = 120
TARGET_TOKENS = 600
MAX_TOKENS = 800

_DOT_LEADER = re.compile(r"^\s*(?P<title>\S.*?)\s*\.{4,}\s*\d+\s*$")
_PAGE_REF = re.compile(r"^\s*(?P<title>[A-Za-z][^.]*?)\s+(?:[A-Z]-)?\d{1,2}\s?-\s?\d{1,3}\s*$")
_PAGE_NUM_DASH = re.compile(r"^\s*(?:[ivxlc]{1,6}|[A-Z]?\s?-?\s?\d{1,3}\s?-\s?\d{1,3})\s*$")  # "x", "3 - 261", "G-1"
_PLAIN_NUM = re.compile(r"^\s*\d{1,4}\s*$")  # also a message number: only a page number if last on page / after footer
_DOC_ID_FOOTER = re.compile(r"--\s?\d{6}-\d{3}\s*$")
_MSG_HEADING = re.compile(r"^(?:[A-Z]{2,8}\s)?\*?\d{3,5}\*?$")
_MSG_NUM_ONLY = re.compile(r"^\d{1,5}$")
_CAUSE = re.compile(r"^\s*Cause\b(?!\s{2,}Action)[.:\s]")
_CHAPTER = re.compile(r"^(?:\d{1,2}|[A-Z])\.\s+(?P<title>\S.*)$")


@dataclass
class Chunk:
    id: str
    manual: str
    section: str          # "Chapter > Heading (pdf p.N)"
    text: str
    page: int             # 1-based page index in the extracted text
    est_tokens: int


def est_tokens(s):
    return int(len(s) / CHARS_PER_TOKEN) + 1


def norm_title(s):
    return re.sub(r"\s+", " ", s).strip().rstrip(".:").lower()


def slugify(s, max_len=60):
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s[:max_len].strip("-") or "section"


def split_pages(text):
    return text.split("\f")


def _digit_norm(line):
    return re.sub(r"\d+", "#", line.strip())


def strip_running_lines(pages):
    """Remove page numbers, doc-id footers and lines repeated on >=8% of pages (running heads).

    A bare 1-4 digit line is ambiguous: TMF/Pathway message numbers are printed that way. It is only
    treated as a page number when it is the last non-empty line of its page or follows a doc-id footer.
    """
    n = max(len(pages), 1)
    counts = {}
    for p in pages:
        seen = {_digit_norm(l) for l in p.splitlines() if 0 < len(l.strip()) <= 90}
        for k in seen:
            counts[k] = counts.get(k, 0) + 1
    # column running heads like "TMFCOM Commands      STATUS AUDITTRAIL" differ per page; those
    # survive as short paragraphs but are harmless (they do not match TOC titles exactly).
    frequent = {k for k, c in counts.items() if c >= max(15, 0.08 * n) and k != "#"}
    # HP-classic layout: first line is "<chapter>   <current section>" (TMF, TACL, Pathway, FUP, PEEK).
    lefts = {}
    for p in pages:
        h = _split_head(next((l for l in p.splitlines() if l.strip()), ""))
        if h:
            key = h[0] or h[1]
            lefts[key] = lefts.get(key, 0) + 1
    out, heads = [], []
    for p in pages:
        raw = p.splitlines()
        head = None
        first = next((i for i, l in enumerate(raw) if l.strip()), None)
        if first is not None:
            h = _split_head(raw[first])
            if h and lefts.get(h[0] or h[1], 0) >= 5:
                head = h
                raw = raw[:first] + raw[first + 1:]
        heads.append(head)
        last = max((i for i, l in enumerate(raw) if l.strip()), default=-1)
        keep, prev_footer = [], False
        for i, l in enumerate(raw):
            s = l.strip()
            if s:
                if _DOC_ID_FOOTER.search(s):
                    prev_footer = True
                    continue
                if _PAGE_NUM_DASH.match(s) or _digit_norm(s) in frequent:
                    continue
                if _PLAIN_NUM.match(s) and (i == last or prev_footer):
                    continue
                prev_footer = False
            keep.append(l.rstrip())
        out.append(keep)
    return out, heads


def _split_head(line):
    """("chapter", "section") if the line looks like a running head, else None.

    Two columns ("TMFCOM Commands    STATUS AUDITTRAIL") -> (left, right); a short single-column line
    -> ("", line), only trusted by the caller when it repeats as the first line of >=5 pages.
    """
    st = line.strip()
    parts = re.split(r"\s{2,}", st)
    if len(parts) == 2 and all(2 <= len(x) <= 70 for x in parts) and not re.search(r"\d\s?-\s?\d", line):
        return parts[0], re.sub(r"\s+", " ", parts[1])
    if len(parts) == 1 and 3 <= len(st) <= 60 and not st.endswith((".", ",", ":")) and not re.search(r"\d$", st):
        return "", st
    return None


def toc_titles(pages, toc_fraction=0.15):
    """(titles, chapters): normalized section titles from the contents pages (first 15% of the manual;
    the back-of-book index would add generic words like "volume" as fake headings), and chapter titles."""
    titles, chapters = set(), set()
    for lines in pages[: max(10, int(len(pages) * toc_fraction))]:
        for l in lines:
            m = _DOT_LEADER.match(l) or _PAGE_REF.match(l)
            if m:
                t = norm_title(m.group("title"))
                if 2 <= len(t) <= 90:
                    titles.add(t)
            c = _CHAPTER.match(l.strip())
            if c and len(l.strip()) < 80 and not l.rstrip().endswith("."):
                chapters.add(norm_title(c.group("title")))
    return titles, chapters


def _index_start(pages):
    """Page index where the back-of-book Index begins (pages from there on are dropped)."""
    for i in range(int(len(pages) * 0.7), len(pages)):
        first = next((l.strip() for l in pages[i] if l.strip()), "")
        if first == "Index" or first.startswith("Index  "):
            return i
    return len(pages)


def _is_toc_page(lines):
    body = [l for l in lines if l.strip()]
    if len(body) < 6:
        return False
    hits = sum(1 for l in body if _DOT_LEADER.match(l) or _PAGE_REF.match(l))
    return hits / len(body) > 0.4


class Para(list):
    """A paragraph (list of lines) that remembers the page it started on."""
    page = 0


def _paragraphs(lines):
    para = []
    for l in lines:
        if l.strip():
            para.append(l)
        elif para:
            yield para
            para = []
    if para:
        yield para


def _dedent(para, page=0):
    ind = min(len(l) - len(l.lstrip()) for l in para)
    out = Para(re.sub(r" {3,}", "  ", l[ind:]) for l in para)
    out.page = page
    return out


def _short(para):
    return len(para) <= 2 and sum(len(l.strip()) for l in para) <= 160


def _looks_like_title(para):
    t = " ".join(l.strip() for l in para)
    return _short(para) and not t.endswith(".") and not t.startswith(("•", "�", "-", "*", "[")) \
        and not re.search(r"\s{3,}", " ".join(para)) and bool(re.match(r"[A-Za-z0-9*]", t))


@dataclass
class _Sec:
    chapter: str
    title: str
    page: int
    paras: list
    kind: str = "section"

    def text(self):
        return "\n\n".join("\n".join(p) for p in self.paras)


def sections(text, ignore_front_pages=0):
    """Split manual text into sections: [_Sec]. Front matter before the first TOC title is kept as 'Front matter'."""
    pages, heads = strip_running_lines(split_pages(text))
    titles, chapters = toc_titles(pages)
    pages = pages[: _index_start(pages)]
    cur_head = None
    secs = []
    cur = _Sec("", "Front matter", 1, [])
    chapter = ""
    for pno, lines in enumerate(pages, start=1):
        if pno <= ignore_front_pages or _is_toc_page(lines):
            continue
        paras = [_dedent(p, pno) for p in _paragraphs(lines)]
        head = heads[pno - 1]
        if head:
            chapter = head[0] or chapter
            if head[1] != cur_head and norm_title(head[1]) != norm_title(cur.title):
                # running head changed: a new entry starts on this page (covers entries missing from the TOC)
                if cur.paras:
                    secs.append(cur)
                cur = _Sec(chapter, head[1], pno, [])
            cur_head = head[1]
        i = 0
        while i < len(paras):
            p = paras[i]
            joined = " ".join(l.strip() for l in p)
            nt = norm_title(joined)
            nxt = paras[i + 1] if i + 1 < len(paras) else None
            is_title = False
            if _short(p) and nt in titles:
                is_title = True
                if nt in chapters:
                    chapter = joined.strip()
            elif len(p) == 1 and _MSG_HEADING.match(joined.strip()):
                is_title = True
                if _MSG_NUM_ONLY.match(joined.strip()):
                    joined = f"Message {joined.strip()}"
            elif len(p) == 1 and _MSG_NUM_ONLY.match(joined.strip()) and any(
                    _CAUSE.match(q[0]) for q in paras[i + 1:i + 5]):
                is_title = True  # 1-2 digit message number (TMFCOM messages 1..99)
                joined = f"Message {joined.strip()}"
            elif nxt is not None and _CAUSE.match(nxt[0]) and _looks_like_title(p) and len(joined) > 3:
                is_title = True
            if is_title:
                if cur.paras:
                    secs.append(cur)
                cur = _Sec(chapter, joined.strip(), pno, [])
                # message title paragraph followed by its own restated text: keep both in the section
                cur.paras.append(p)
            else:
                if not cur.paras:
                    cur.page = pno
                cur.paras.append(p)
            i += 1
    if cur.paras:
        secs.append(cur)
    return _qualify_generic(secs)


def _qualify_generic(secs, min_repeats=5):
    """Headings repeated many times ("Examples", "Output Displayed", "Considerations") only make sense
    under their parent command, so prefix them with the last specific heading."""
    freq = {}
    for s in secs:
        freq[norm_title(s.title)] = freq.get(norm_title(s.title), 0) + 1
    parent = ""
    for s in secs:
        if freq[norm_title(s.title)] >= min_repeats and not s.title.startswith("Message ") and parent:
            s.title = f"{parent} - {s.title.rstrip(':')}"
        elif not s.title.startswith("Message "):
            parent = s.title
    return secs


def _split_big(paras, title):
    """Split a too-large section's paragraphs into parts of ~TARGET_TOKENS (paragraph boundaries; giant
    paragraphs are split by lines)."""
    flat = []
    for p in paras:
        if est_tokens("\n".join(p)) > MAX_TOKENS:
            buf = Para()
            buf.page = p.page
            for l in p:
                buf.append(l)
                if est_tokens("\n".join(buf)) >= TARGET_TOKENS:
                    flat.append(buf)
                    buf = Para()
                    buf.page = p.page
            if buf:
                flat.append(buf)
        else:
            flat.append(p)
    parts, cur, cur_t = [], [], 0
    for p in flat:
        t = est_tokens("\n".join(p))
        if cur and cur_t + t > TARGET_TOKENS:
            parts.append(cur)
            cur, cur_t = [], 0
        cur.append(p)
        cur_t += t
    if cur:
        parts.append(cur)
    return parts


def chunk_manual(text, manual, min_tokens=MIN_TOKENS, max_tokens=MAX_TOKENS):
    """Chunk one manual's text. Returns [Chunk] with unique ids 'doc:<manual>:<slug>'."""
    secs = [s for s in sections(text) if s.text().strip() and s.title != "Front matter"]
    # 1) split oversized sections
    pieces = []  # (chapter, title, page, paras)
    for s in secs:
        if est_tokens(s.text()) > max_tokens:
            for k, part in enumerate(_split_big(s.paras, s.title)):
                title = s.title if k == 0 else f"{s.title} (part {k + 1})"
                pieces.append([s.chapter, title, getattr(part[0], "page", 0) or s.page, part, [s.title]])
        else:
            pieces.append([s.chapter, s.title, s.page, s.paras, [s.title]])
    # 2) merge small pieces into the next one (same chapter) so a tiny entry keeps its neighbour's context
    merged = []
    for pc in pieces:
        if merged:
            prev = merged[-1]
            pt = est_tokens("\n\n".join("\n".join(p) for p in prev[3]))
            ct = est_tokens("\n\n".join("\n".join(p) for p in pc[3]))
            if (pt < min_tokens or ct < min_tokens // 2) and prev[0] == pc[0] and pt + ct <= max_tokens:
                prev[3] = prev[3] + pc[3]
                prev[4] = prev[4] + pc[4]
                continue
        merged.append(pc)
    # 3) materialise
    out, used = [], {}
    for chapter, title, page, paras, titles in merged:
        body = "\n\n".join("\n".join(p) for p in paras)
        label = title if len(titles) == 1 else f"{titles[0]} .. {titles[-1]}"
        path = " > ".join(x for x in (chapter, label) if x and x != label) or label
        if chapter and chapter != label:
            path = f"{chapter} > {label}"
        slug = slugify(title)
        if titles[0].startswith("Message "):
            slug = slug.replace("message-", "msg-", 1)
        used[slug] = used.get(slug, 0) + 1
        if used[slug] > 1:
            slug = f"{slug}-{used[slug]}"
        out.append(Chunk(f"doc:{manual}:{slug}", manual, f"{path} (txt p.{page})", body, page, est_tokens(body)))
    return out

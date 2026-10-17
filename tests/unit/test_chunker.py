"""Chunker: structure-aware splitting of extracted manual text (no Docker, no manuals needed)."""
from backend.ingest.chunker import (MAX_TOKENS, chunk_manual, est_tokens, norm_title, sections, slugify,
                                    strip_running_lines)

TOC = "\n".join(["Contents", ""] + [f"{t} Command{'.' * 30} {n}" for t, n in
                                      [("STOP DISK", 12), ("ABORT DISK", 14), ("START DISK", 15), ("INFO DISK", 16),
                                       ("ADD DISK", 17), ("ALTER DISK", 18), ("DELETE DISK", 19)]])


def entry(title, body):
    return f"{title}\n\n{body}\n\nHP NonStop Test Manual--123456-001\n   3 - 1\n"


def manual(*pages):
    return "\f".join(pages)


BODY_STOP = "The STOP DISK command terminates access to a disk. " * 6
BODY_ABORT = "The ABORT DISK command stops access as quickly as possible. " * 6


def test_toc_page_is_dropped_and_titles_become_sections():
    text = manual("Front matter junk\n\nLegal text", TOC,
                  entry("STOP DISK Command", BODY_STOP), entry("ABORT DISK Command", BODY_ABORT))
    chunks = chunk_manual(text, "TestSCF", min_tokens=1)
    ids = [c.id for c in chunks]
    assert ids == ["doc:TestSCF:stop-disk-command", "doc:TestSCF:abort-disk-command"]
    assert all("....." not in c.text for c in chunks)          # contents lines never reach a chunk
    assert "Legal text" not in " ".join(c.text for c in chunks)  # front matter dropped


def test_each_command_entry_is_its_own_chunk_with_section_label():
    text = manual(TOC, entry("STOP DISK Command", BODY_STOP), entry("ABORT DISK Command", BODY_ABORT))
    by = {c.id: c for c in chunk_manual(text, "T", min_tokens=1)}
    assert "terminates access" in by["doc:T:stop-disk-command"].text
    assert "stops access as quickly" not in by["doc:T:stop-disk-command"].text
    assert by["doc:T:abort-disk-command"].section.startswith("ABORT DISK Command")


def test_message_numbers_start_sections_even_when_one_or_two_digits():
    msgs = ("37\n\nThe command specified an invalid DENSITY parameter.\n\nCause. Bad density.\nRecovery. Retry.\n\n"
            "3001\n\n*3001* TERM t1, INVALID PSEUDOCODE DETECTED\n\nCause. Corrupt object file.\nEffect. Suspended.\n")
    text = manual(TOC, entry("STOP DISK Command", BODY_STOP), msgs)
    ids = [c.id for c in chunk_manual(text, "T", min_tokens=1)]
    assert "doc:T:msg-37" in ids and "doc:T:msg-3001" in ids


def test_bare_number_before_cause_is_not_stripped_as_page_number():
    pages, _ = strip_running_lines(["37\n\nInvalid thing.\n\nCause. x\n"])
    assert pages[0][0] == "37"
    # but a bare number as the last line of a page is a page number
    pages, _ = strip_running_lines(["Some text here.\n\n12\n"])
    assert "12" not in [l.strip() for l in pages[0]]


def test_doc_id_footer_and_dashed_page_numbers_removed():
    pages, _ = strip_running_lines(["Body line.\n\nHP NonStop X Manual--540138-001\n   3 - 261\n"])
    assert [l.strip() for l in pages[0] if l.strip()] == ["Body line."]


def test_oversized_section_is_split_under_max_tokens_with_unique_ids():
    big = "\n\n".join(f"Paragraph {i}. " + "word " * 120 for i in range(20))
    text = manual(TOC, entry("STOP DISK Command", big))
    chunks = chunk_manual(text, "T")
    assert len(chunks) > 3
    assert all(c.est_tokens <= MAX_TOKENS for c in chunks)
    assert len({c.id for c in chunks}) == len(chunks)


def test_tiny_sections_merge_into_neighbour_within_chapter():
    text = manual(TOC, entry("STOP DISK Command", "Short."), entry("ABORT DISK Command", BODY_ABORT))
    chunks = chunk_manual(text, "T")  # default min_tokens=120
    assert len(chunks) == 1
    assert "Short." in chunks[0].text and "ABORT DISK" in chunks[0].text


def test_repeated_generic_headings_are_qualified_with_parent_command():
    names = ["Examples", "STOP DISK Command", "ABORT DISK Command", "START DISK Command",
             "INFO DISK Command", "ADD DISK Command", "ALTER DISK Command", "DELETE DISK Command"]
    toc = "\n".join(["Contents", ""] + [f"{t}{'.' * 30} {i}" for i, t in enumerate(names)])
    cmds = ["STOP", "ABORT", "START", "INFO", "ADD", "ALTER"]
    body = [entry(f"{c} DISK Command", BODY_STOP) + "\n\nExamples\n\n" + "-> sample\n" * 30 for c in cmds]
    titles = [s.title for s in sections(manual(toc, *body))]
    assert "STOP DISK Command - Examples" in titles and "ABORT DISK Command - Examples" in titles


def test_helpers():
    assert slugify("STOP DISK Command!") == "stop-disk-command"
    assert slugify("") == "section"
    assert norm_title("  Examples: ") == "examples"
    assert est_tokens("x" * 350) > 90

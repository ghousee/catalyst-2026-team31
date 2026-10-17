"""Step 5: claim verification with MiniCheck-Flan-T5-Large (770M, CPU).

Re-implements the official inference (github.com/Liyan06/MiniCheck, minicheck/inference.py) directly on
transformers so we do not need the `minicheck` package (which drags in vllm/nltk): input is
"predict: <doc chunk>" + </s> + "<claim>", one decoder step, softmax over logits of token ids [3, 209]
(no-support, support). The document is split into ~400-word windows; the claim score is the max over windows.
"""
import re

MODEL_ID = "lytang/MiniCheck-Flan-T5-Large"
WINDOW_WORDS = 400

_model = None

# ---- negation guard: MiniCheck scored a claim that inverted a note ("do not X" -> "do X") at 0.97
_FILLER = set("a an the of to in on at is are be it its this that and or for with by as from first only".split())


def _words(text):
    return [w for w in re.findall(r"[a-z0-9$]+", text.lower().replace("n't", " not")) if w not in _FILLER]


def _neg_windows(text):
    """For each negation, the set of content words around it in the same sentence (4 after, 2 before)."""
    out = []
    for sent in re.split(r"(?<=[.!?;])\s+", text):
        ws = _words(sent)
        out += [set(ws[max(0, i - 2):i] + ws[i + 1:i + 5]) - {"not", "never", "cannot", "longer", "no"}
                for i, w in enumerate(ws) if w in ("not", "never", "cannot") or (w == "no" and ws[i + 1:i + 2] == ["longer"])]
    return out


def negation_mismatch(claim, source):
    """True if the claim negates something near terms the source does not negate, or the source negates
    something near >= 2 (or one long) claim terms that the claim does not negate. Simple on purpose; loosen on false drops."""
    cw, sw = _neg_windows(claim), _neg_windows(source)
    if any(not any(c & s for s in sw) for c in cw):
        return True
    claim_words = set(_words(claim))
    # a shared long word (FILESPERVOLUME, AUDITTRAIL) is as good as two shared short ones
    return any(not any(c & s for c in cw) and (len(s & claim_words) >= 2 or any(len(w) >= 8 for w in s & claim_words))
               for s in sw)



def windows(doc, n=WINDOW_WORDS):
    """Split text into consecutive windows of at most n whitespace-separated words (pure)."""
    words = doc.split()
    return [" ".join(words[i:i + n]) for i in range(0, len(words), n)] or [""]


def _load():
    global _model
    if _model is None:
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        tok = AutoTokenizer.from_pretrained(MODEL_ID)
        mdl = AutoModelForSeq2SeqLM.from_pretrained(MODEL_ID).eval()
        _model = (torch, tok, mdl)
    return _model


def support_prob(doc, claim, max_len=2048):
    """P(claim is supported by doc), max over doc windows."""
    return support_probs([(doc, claim)], max_len)[0]


def support_probs(pairs, max_len=2048):
    """Batch version: [(doc, claim)] -> [P(supported)], one forward pass for all claims and windows."""
    if not pairs:
        return []
    torch, tok, mdl = _load()
    texts, owner = [], []
    for k, (doc, claim) in enumerate(pairs):
        for w in windows(doc):
            texts.append(tok.eos_token.join(["predict: " + w, claim]))
            owner.append(k)
    enc = tok(texts, max_length=max_len, truncation=True, padding=True, return_tensors="pt")
    with torch.no_grad():
        dec = torch.zeros((enc["input_ids"].size(0), 1), dtype=torch.long)
        logits = mdl(input_ids=enc["input_ids"], attention_mask=enc["attention_mask"],
                     decoder_input_ids=dec).logits.squeeze(1)
        probs = torch.softmax(logits[:, [3, 209]], dim=-1)[:, 1].tolist()
    best = [0.0] * len(pairs)
    for k, p in zip(owner, probs):
        best[k] = max(best[k], p)
    return best

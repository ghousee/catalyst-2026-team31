"""Step 5: claim verification with MiniCheck-Flan-T5-Large (770M, CPU).

Re-implements the official inference (github.com/Liyan06/MiniCheck, minicheck/inference.py) directly on
transformers so we do not need the `minicheck` package (which drags in vllm/nltk): input is
"predict: <doc chunk>" + </s> + "<claim>", one decoder step, softmax over logits of token ids [3, 209]
(no-support, support). The document is split into ~400-word windows; the claim score is the max over windows.
"""
MODEL_ID = "lytang/MiniCheck-Flan-T5-Large"
WINDOW_WORDS = 400

_model = None


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
    torch, tok, mdl = _load()
    texts = [tok.eos_token.join(["predict: " + w, claim]) for w in windows(doc)]
    enc = tok(texts, max_length=max_len, truncation=True, padding=True, return_tensors="pt")
    with torch.no_grad():
        dec = torch.zeros((enc["input_ids"].size(0), 1), dtype=torch.long)
        logits = mdl(input_ids=enc["input_ids"], attention_mask=enc["attention_mask"],
                     decoder_input_ids=dec).logits.squeeze(1)
        probs = torch.softmax(logits[:, [3, 209]], dim=-1)[:, 1]
    return float(probs.max())

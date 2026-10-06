"""PDF-FPSE engine v3.

Text:   maximal shared word-runs are treated as "clumps" and tested with a Poisson clumping model whose
        chance rate is estimated from the class itself (robustly, so copied pairs do not distort it).
Images: screenshot content match, tested against the class with a robust z-test.
Combine: Fisher's method -> Benjamini-Hochberg false discovery rate across all pairs.
"""
import csv, io, math, os, re
from collections import Counter
from dataclasses import dataclass, field
from itertools import combinations

try:
    import pymupdf as fitz
except ImportError:          # older PyMuPDF only provides "fitz"
    import fitz
import numpy as np
from PIL import Image
from scipy import stats

SHINGLE = 3                      # words in the unit used to find shared runs
MIN_RUN = 10                     # identical words in a row that a teacher can read as "a copied passage"
MIN_TEST_WORDS = 4               # shortest shared run that enters the statistical test
Q_COPIED, Q_REVIEW = 0.01, 0.05  # false-discovery-rate limits
EMP_MAX, DEFAULT_DECAY, DECAY_RANGE = 14, 0.3, (0.05, 0.7)
IMG_MATCH, IMG_MIN = 0.92, 0.75  # fixed rule (small classes) / smallest match worth testing
IMG_TOL, IMG_SIZE, MIN_MASK = 30, (512, 320), 0.003
MIN_IMG_PX, MARGIN = 80, 0.07
SPLIT = re.compile(r"[\s.,;:!?\"'()\[\]{}<>/\\|=+*&^%$#@~`\-\u2013\u2014\u2018\u2019\u201c\u201d]+")


def tokenize(text):
    """Lowercase words/numbers/identifiers in any script (so SQL, digits and non-English text are kept)."""
    return [t for t in SPLIT.split(text.lower()) if t]


@dataclass
class Img:
    arr: np.ndarray
    aspect: float
    mask: np.ndarray | None = None


@dataclass
class Doc:
    name: str
    text: str = ""
    tokens: list = field(default_factory=list)
    index: dict = field(default_factory=dict)    # 3-word phrase -> start positions
    ok: list = field(default_factory=list)       # position holds a rare, non-prompt phrase
    images: list = field(default_factory=list)


def extract(path):
    d = Doc(name=os.path.basename(path))
    with fitz.open(path) as pdf:
        parts, seen = [], set()
        for page in pdf:
            h = page.rect.height
            for b in page.get_text("blocks"):
                if b[6] == 0 and h * MARGIN < (b[1] + b[3]) / 2 < h * (1 - MARGIN):   # skip headers/footers
                    parts.append(b[4])
            for img in page.get_images(full=True):
                if img[0] in seen:
                    continue
                seen.add(img[0])
                try:
                    im = Image.open(io.BytesIO(pdf.extract_image(img[0])["image"]))
                    if min(im.size) >= MIN_IMG_PX:
                        d.images.append(Img(np.asarray(im.convert("L").resize(IMG_SIZE, Image.BILINEAR)).astype(np.int16),
                                            im.width / im.height))
                except Exception:
                    pass
    d.text = "\n".join(parts)
    return d


def read_prompt(path):
    if path.lower().endswith(".pdf"):
        with fitz.open(path) as pdf:
            return "\n".join(p.get_text() for p in pdf)
    return open(path, encoding="utf-8", errors="ignore").read()


def _phrases(tokens):
    return [tuple(tokens[i:i + SHINGLE]) for i in range(len(tokens) - SHINGLE + 1)]


def preprocess(docs, prompt_text=""):
    """Index every 3-word phrase; mark phrases that are common wording or part of the assignment prompt."""
    prompt = set(_phrases(tokenize(prompt_text)))
    for d in docs:
        d.tokens = tokenize(d.text)
        d.index = {}
        for i, sh in enumerate(_phrases(d.tokens)):
            d.index.setdefault(sh, []).append(i)
    freq = Counter(sh for d in docs for sh in d.index)
    n = len(docs)
    rare_max = min(max(3, math.ceil(0.15 * n)), max(n - 1, 2))
    common = {sh for sh, c in freq.items() if c > rare_max} | prompt
    for d in docs:
        d.ok = [False] * len(d.tokens)
        for sh, pos in d.index.items():
            if sh not in common:
                for i in pos:
                    d.ok[i] = True


def prepare_images(docs):
    """Mark which pixels of each screenshot are its own content (window frames/menus/logos are ignored)."""
    groups = {}
    for d in docs:
        for im in d.images:
            groups.setdefault(round(im.aspect / 0.05), []).append((d, im))
    for items in groups.values():
        shared = len({id(d) for d, _ in items}) >= 3
        median = np.median(np.stack([im.arr for _, im in items]), axis=0) if shared else None
        for _, im in items:
            base = median if shared else np.bincount(im.arr.ravel().astype(np.uint8)).argmax()
            im.mask = np.abs(im.arr - base) > IMG_TOL


# ---------------------------------------------------------------- text evidence
def shared_runs(a, b):
    """All maximal runs of identical consecutive words between a and b that contain a rare phrase.
    Returns [(length_in_words, start_in_a)]. A run is ONE event, however many phrases it contains."""
    diag = {}
    for sh in a.index.keys() & b.index.keys():
        pa, pb = a.index[sh], b.index[sh]
        if len(pa) * len(pb) > 2500:           # extremely repetitive text (e.g. long lines of dashes)
            continue
        for i in pa:
            for j in pb:
                diag.setdefault(i - j, []).append(i)
    runs = []
    for starts in diag.values():
        starts.sort()
        s0 = prev = starts[0]
        for i in starts[1:] + [None]:
            if i is not None and i == prev + 1:
                prev = i
                continue
            if any(a.ok[s0:prev + 1]):
                runs.append((prev - s0 + SHINGLE, s0))
            if i is not None:
                s0 = prev = i
    return runs


def fit_null(pairs, runs):
    """Chance model for shared runs, learned from the class itself.
    - rate[l]: how many runs of >= l words a pair shares by chance, per pair of word positions (measured
      directly for l = 3..EMP_MAX; beyond that it falls off geometrically with the measured decay).
    - phi: overdispersion (some pairs coincide more than others), used to widen the Poisson to a
      negative binomial.
    Pairs that already contain an obvious copy (a run >= 15 words) are left out, so copying cannot make
    'normal' look more similar than it is."""
    normal = [(a, b, rs) for (a, b), rs in zip(pairs, runs) if not any(L >= EMP_MAX + 1 for L, _ in rs)]
    if len(normal) < 3:
        normal = [(a, b, rs) for (a, b), rs in zip(pairs, runs)]
    nm = [len(a.tokens) * len(b.tokens) for a, b, _ in normal]
    total = sum(nm) or 1
    floor = 0.5 / total                       # never claim a chance rate below half a coincidence in the class
    rate = {}
    for l in range(3, EMP_MAX + 1):
        rate[l] = max(sum(sum(L >= l for L, _ in rs) for _, _, rs in normal) / total, floor)
        if l > 3:
            rate[l] = min(rate[l], rate[l - 1])
    decay = (rate[10] / rate[6]) ** 0.25 if rate[6] > floor else DEFAULT_DECAY
    decay = min(max(decay, DECAY_RANGE[0]), DECAY_RANGE[1])
    phi = 1.0
    for l in range(8, 3, -1):                 # estimate dispersion at the longest length with enough counts
        exp = [x * rate[l] for x in nm]
        if sum(exp) >= 10:
            obs = [sum(L >= l for L, _ in rs) for _, _, rs in normal]
            phi = max(1.0, sum((o - e) ** 2 for o, e in zip(obs, exp)) / sum(exp))
            break
    return dict(rate=rate, decay=decay, phi=phi)


def _tail(count, lam, phi):
    """P(X >= count) for a Poisson (phi = 1) or negative binomial (phi > 1) with mean lam."""
    if phi <= 1.001:
        return float(stats.poisson.sf(count - 1, lam))
    return float(stats.nbinom.sf(count - 1, lam / (phi - 1), 1 / phi))


def text_pvalue(a, b, runs, null):
    """Scan statistic: for each run length l seen, how likely are this many runs of >= l words by chance?
    Take the best l and correct for the number of lengths tried (Bonferroni)."""
    lengths = sorted({L for L, _ in runs if L >= MIN_TEST_WORDS})
    if not lengths:
        return 1.0
    nm = len(a.tokens) * len(b.tokens)
    rate = lambda l: null["rate"][l] if l <= EMP_MAX else null["rate"][EMP_MAX] * null["decay"] ** (l - EMP_MAX)
    best = min(_tail(sum(L >= l for L, _ in runs), nm * rate(l), null["phi"]) for l in lengths)
    return min(1.0, len(lengths) * max(best, 1e-300))


# ---------------------------------------------------------------- image evidence
def best_image_match(a, b):
    best = None
    for ia in a.images:
        for ib in b.images:
            if abs(ia.aspect - ib.aspect) > 0.05:
                continue
            used = ia.mask | ib.mask
            if used.sum() < MIN_MASK * used.size:     # nothing specific to either screenshot
                continue
            same = float((np.abs(ia.arr - ib.arr) <= IMG_TOL)[used].mean())
            best = same if best is None else max(best, same)
    return best


def image_pvalues(scores):
    """Robust z-test: how far above the class's typical screenshot match (median, MAD) is this pair?"""
    known = [s for s in scores if s is not None]
    if len(known) < 8:
        return [None] * len(scores)               # too few to describe 'normal'; fixed rule is used instead
    med = float(np.median(known))
    scale = max(1.4826 * float(np.median(np.abs(np.array(known) - med))), 0.03)
    return [None if s is None else 1.0 if s < IMG_MIN else max(float(stats.norm.sf((s - med) / scale)), 1e-300)
            for s in scores]


# ---------------------------------------------------------------- combining
def fisher(ps):
    return float(stats.chi2.sf(-2 * sum(math.log(max(p, 1e-300)) for p in ps), 2 * len(ps)))


def benjamini_hochberg(p):
    n = len(p)
    order = np.argsort(p)
    q, prev = np.empty(n), 1.0
    for rank in range(n, 0, -1):
        idx = order[rank - 1]
        prev = min(prev, p[idx] * n / rank)
        q[idx] = prev
    return q


MATRIX_COLS = ["PDF_1", "PDF_2", "Shared_Words", "Longest_Match_Words", "Text_P_Value", "Image_Match_Percent",
               "Q_Value", "Trigger_Type", "Verdict"]
FLAG_COLS = ["Flagged_PDF", "Matched_With", "Trigger_Type", "Q_Value", "Longest_Match_Words", "Shared_Passage",
             "Image_Match_Percent", "Faculty_Review_Status", "Teacher_Notes"]


def analyze(docs, prompt="", progress=lambda frac, msg: None):
    prepare_images(docs)
    preprocess(docs, prompt)
    pairs = list(combinations(docs, 2))
    solo = len(pairs) == 1
    runs = []
    for i, (a, b) in enumerate(pairs):
        runs.append(shared_runs(a, b))
        if i % 10 == 0:
            progress(0.55 + 0.3 * i / len(pairs), f"Comparing pair {i + 1} of {len(pairs)}")
    null = None if solo else fit_null(pairs, runs)
    img = [best_image_match(a, b) for a, b in pairs]
    img_p = image_pvalues(img)
    rows, combined = [], []
    for (a, b), rs, s, pi in zip(pairs, runs, img, img_p):
        longest, start = max(rs, default=(0, 0))
        pt = None if solo else text_pvalue(a, b, rs, null)
        fixed_img = s is not None and pi is None and s >= IMG_MATCH      # small class: fixed 92% rule
        text_sig = (longest >= MIN_RUN) if solo else pt < Q_REVIEW
        img_sig = fixed_img or (pi is not None and pi < Q_REVIEW)
        ps = [p for p in (pt, pi) if p is not None]
        combined.append(fisher(ps) if ps else 1.0)
        rows.append(dict(PDF_1=a.name, PDF_2=b.name, Shared_Words=sum(L for L, _ in rs if L >= MIN_TEST_WORDS),
                         Longest_Match_Words=longest, Text_P_Value="" if pt is None else float(f"{pt:.3e}"),
                         Image_Match_Percent="" if s is None else round(s * 100, 1),
                         Trigger_Type="Both" if text_sig and img_sig else "Text" if text_sig else "Image" if img_sig else "",
                         _passage=" ".join(a.tokens[start:start + longest]) if longest else "", _fixed=fixed_img))
    q = [None] * len(rows) if solo else benjamini_hochberg(np.array(combined))
    for r, qv in zip(rows, q):
        r["Q_Value"] = "" if qv is None else float(f"{qv:.3e}")
        long_ok = r["Longest_Match_Words"] >= MIN_RUN
        copied = (long_ok and r["_fixed"]) if solo else (qv < Q_COPIED and long_ok)
        review = r["_fixed"] or (long_ok if solo else qv < Q_REVIEW)
        r["Verdict"] = "Copied" if copied else "Needs review" if review else "No evidence"
    rows.sort(key=lambda r: (r["Q_Value"] if r["Q_Value"] != "" else 1, -r["Longest_Match_Words"]))
    n = len(docs)
    warn = f"Only {n} PDFs: the chance model rests on {len(pairs)} pairs, so p-values are rough. Ten or more PDFs is better." if 2 < n < 6 else ""
    return rows, solo, warn


def run(folder, out_dir, prompt_file=None, progress=lambda frac, msg: None):
    files = sorted(os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(".pdf"))
    docs, skipped = [], []
    for i, p in enumerate(files):
        progress(i / max(len(files), 1) * 0.5, f"Reading {os.path.basename(p)}")
        try:
            docs.append(extract(p))
        except Exception:
            skipped.append(os.path.basename(p))
    if len(docs) < 2:
        raise ValueError("Need at least two readable PDF files in the folder." + (f" Could not read: {', '.join(skipped)}" if skipped else ""))
    rows, solo, warn = analyze(docs, read_prompt(prompt_file) if prompt_file else "", progress)
    os.makedirs(out_dir, exist_ok=True)
    mpath, fpath = os.path.join(out_dir, "pairwise_similarity_matrix.csv"), os.path.join(out_dir, "flagged_plagiarized_files.csv")
    with open(mpath, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, MATRIX_COLS, extrasaction="ignore"); w.writeheader(); w.writerows(rows)
    flagged = [r for r in rows if r["Verdict"] == "Copied"]
    with open(fpath, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh); w.writerow(FLAG_COLS)
        for r in flagged:
            w.writerow([r["PDF_1"], r["PDF_2"], r["Trigger_Type"], r["Q_Value"], r["Longest_Match_Words"], r["_passage"],
                        r["Image_Match_Percent"], "", ""])
    progress(1.0, "Done")
    return dict(rows=rows, flagged=len(flagged), docs=len(docs), pairs=len(rows), solo=solo, warn=warn,
                skipped=skipped, matrix=mpath, flags=fpath)
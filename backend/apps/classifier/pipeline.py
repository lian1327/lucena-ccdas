"""
Module 3 — AI classification engine (scikit-learn).

Two linked models over the report text (description only: auto-generated titles contain the label and would leak):
  1. category model     → one of the 8 categories
  2. sub-type model     → the sub-type, restricted to the predicted category at prediction time

Features: TF-IDF of word 1–2-grams + TF-IDF of character 2–5-grams (within word boundaries). Character n-grams
are what make Taglish work: they match "baha / bahaa / binabaha / flooded" spellings and typos without a
Filipino stemmer or dictionary.

Model selection: Complement Naive Bayes, Logistic Regression and a linear SVM (probability-calibrated) are
compared by stratified 5-fold cross-validated macro-F1 on the training split; the winner is evaluated once on
a held-out 20% test split and on the hand-written challenge set, then refit on all data for deployment.
Macro-F1 (not accuracy) is the selection metric because categories are imbalanced (Business Permit is rare).

Reported for the paper: accuracy, macro-F1, per-category precision/recall/F1, confusion matrix, a majority-
class baseline, and "auto-assign coverage": how many reports clear the confidence threshold and how accurate
those are. That last one justifies the auto-assign policy (AI fills the category only when confident; PACD
always verifies).
"""
import csv
import statistics
import time
from collections import Counter
from pathlib import Path

import joblib
import numpy as np
from django.conf import settings
from sklearn.calibration import CalibratedClassifierCV
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_recall_fscore_support
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.naive_bayes import ComplementNB
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.svm import LinearSVC

from .text import normalize

SEED = 42
AUTO_THRESHOLD = getattr(settings, "ML_AUTO_ASSIGN_THRESHOLD", 0.70)
OTHER_SUB = "_other"


def _remote_storage():
    """The default file storage when it isn't the local disk (e.g. Cloudflare R2 on a free host)."""
    from django.core.files.storage import FileSystemStorage, default_storage

    return None if isinstance(default_storage, FileSystemStorage) else default_storage


def _push_model(fname):
    """Copy a trained model to remote storage so it survives restarts of a host with an ephemeral disk."""
    store = _remote_storage()
    if store is None:
        return
    from django.core.files import File

    key = f"ml/models/{fname}"
    if store.exists(key):
        store.delete(key)
    with open(model_dir() / fname, "rb") as fh:
        store.save(key, File(fh))


def _pull_model(fname):
    """Fetch a model file from remote storage after a restart. Returns True if it is now on disk."""
    store = _remote_storage()
    key = f"ml/models/{fname}"
    if store is None or not store.exists(key):
        return False
    with store.open(key, "rb") as src, open(model_dir() / fname, "wb") as dst:
        dst.write(src.read())
    return True


def model_dir():
    d = Path(getattr(settings, "ML_MODEL_DIR", Path(settings.BASE_DIR) / "ml" / "models"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def features():
    return FeatureUnion([
        ("word", TfidfVectorizer(preprocessor=normalize, ngram_range=(1, 2), min_df=2, sublinear_tf=True)),
        ("char", TfidfVectorizer(preprocessor=normalize, analyzer="char_wb", ngram_range=(2, 5), min_df=2,
                                 sublinear_tf=True, max_features=60000)),
    ])


ALGORITHMS = {
    "complement_nb": lambda: ComplementNB(alpha=0.3),
    "logistic_regression": lambda: LogisticRegression(C=8, max_iter=3000, class_weight="balanced"),
    "linear_svm": lambda: CalibratedClassifierCV(LinearSVC(C=0.5, class_weight="balanced"), cv=3),
}


def build(algo):
    return Pipeline([("features", features()), ("clf", ALGORITHMS[algo]())])


# ---------------------------------------------------------------- data
def load_dataset(real_only=False, extra_csv=None, before=None):
    """(texts, categories, subcategories, sources) from staff-verified reports (+ an optional labelled CSV)."""
    from apps.concerns.models import Concern

    qs = Concern.objects.filter(is_verified=True, category__isnull=False).exclude(description="") \
        .values_list("description", "category__code", "subcategory__code", "is_synthetic")
    if real_only:
        qs = qs.filter(is_synthetic=False)
    if before:
        qs = qs.filter(created_at__lt=before)
    texts, cats, subs, src = [], [], [], Counter()
    seen = set()
    for desc, cat, sub, synthetic in qs.iterator():
        key = normalize(desc)
        if key in seen or len(key) < 8:
            continue
        seen.add(key)
        texts.append(desc)
        cats.append(cat)
        subs.append(sub or OTHER_SUB if cat == "other" else (sub or f"{cat}:*"))
        src["synthetic" if synthetic else "real"] += 1
    if extra_csv:
        for row in read_csv(extra_csv):
            texts.append(row["text"])
            cats.append(row["category"])
            subs.append(row.get("subcategory") or (OTHER_SUB if row["category"] == "other" else f"{row['category']}:*"))
            src["extra_csv"] += 1
    return texts, cats, subs, dict(src)


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [r for r in csv.DictReader(f) if (r.get("text") or "").strip() and r.get("category")]


# ---------------------------------------------------------------- evaluation helpers
def report(y_true, y_pred, labels, names=None):
    p, r, f, s = precision_recall_fscore_support(y_true, y_pred, labels=labels, zero_division=0)
    names = names or {}
    return {
        "accuracy": round(accuracy_score(y_true, y_pred), 4),
        "macro_f1": round(f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0), 4),
        "weighted_f1": round(f1_score(y_true, y_pred, labels=labels, average="weighted", zero_division=0), 4),
        "per_class": [{"code": c, "name": names.get(c, c), "precision": round(p[i], 4), "recall": round(r[i], 4),
                       "f1": round(f[i], 4), "support": int(s[i])} for i, c in enumerate(labels)],
        "confusion": {"labels": list(labels), "matrix": confusion_matrix(y_true, y_pred, labels=labels).tolist()},
        "n": len(y_true),
    }


def coverage(y_true, proba, classes, thresholds=(0.5, 0.6, 0.7, 0.8, 0.9)):
    """Share of reports the AI would auto-assign at each confidence threshold, and how accurate those are."""
    top = proba.argmax(axis=1)
    conf = proba.max(axis=1)
    pred = np.array(classes)[top]
    y = np.array(y_true)
    out = []
    for t in thresholds:
        m = conf >= t
        out.append({"threshold": t, "coverage": round(float(m.mean()), 4),
                    "accuracy": round(float((pred[m] == y[m]).mean()), 4) if m.any() else None})
    return out


# ---------------------------------------------------------------- training
def train(real_only=False, extra_csv=None, challenge_csv=None, log=print, cv_folds=5, before=None):
    from apps.concerns.models import Category, Subcategory

    t0 = time.time()
    texts, cats, subs, sources = load_dataset(real_only, extra_csv, before)
    if len(texts) < 50 or len(set(cats)) < 2:
        raise ValueError(f"Not enough verified, labelled reports to train on ({len(texts)}).")
    cat_names = {c.code: c.name for c in Category.objects.all()}
    sub_names = {s.code: s.name for s in Subcategory.objects.all()} | {OTHER_SUB: "Other community issue"}
    counts = Counter(cats)
    rare = {c for c, n in counts.items() if n < cv_folds}
    keep = [i for i, c in enumerate(cats) if c not in rare]
    texts, cats, subs = [texts[i] for i in keep], [cats[i] for i in keep], [subs[i] for i in keep]
    log(f"  dataset: {len(texts)} unique reports {sources}; categories {dict(Counter(cats))}")

    X_tr, X_te, c_tr, c_te, s_tr, s_te = train_test_split(texts, cats, subs, test_size=0.2, random_state=SEED, stratify=cats)
    labels = sorted(set(cats))

    # model comparison on the training split (cross-validated macro-F1)
    skf = StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=SEED)
    comparison = []
    base = DummyClassifier(strategy="most_frequent").fit(X_tr, c_tr)
    comparison.append({"algorithm": "majority_baseline", "cv_macro_f1": None,
                       "test_macro_f1": round(f1_score(c_te, base.predict(X_te), average="macro", zero_division=0), 4),
                       "test_accuracy": round(accuracy_score(c_te, base.predict(X_te)), 4)})
    best, best_score = None, -1
    for algo in ALGORITHMS:
        t = time.time()
        scores = cross_val_score(build(algo), X_tr, c_tr, cv=skf, scoring="f1_macro", n_jobs=1)
        m = build(algo).fit(X_tr, c_tr)
        pred = m.predict(X_te)
        row = {"algorithm": algo, "cv_macro_f1": round(float(scores.mean()), 4), "cv_std": round(float(scores.std()), 4),
               "test_macro_f1": round(f1_score(c_te, pred, average="macro", zero_division=0), 4),
               "test_accuracy": round(accuracy_score(c_te, pred), 4), "seconds": round(time.time() - t, 1)}
        comparison.append(row)
        log(f"  {algo:22s} CV macro-F1 {row['cv_macro_f1']:.3f} ± {row['cv_std']:.3f} · test acc {row['test_accuracy']:.3f}")
        if scores.mean() > best_score:
            best, best_score = algo, scores.mean()
    log(f"  selected: {best}")

    # held-out evaluation of the selected configuration
    cat_model = build(best).fit(X_tr, c_tr)
    sub_model = build(best).fit(X_tr, s_tr)
    c_pred = cat_model.predict(X_te)
    proba = cat_model.predict_proba(X_te)
    s_pred = _restricted_sub(sub_model, X_te, c_pred)
    metrics = {
        "algorithm": best, "selection": "highest cross-validated macro-F1 (category)", "comparison": comparison,
        "category": report(c_te, c_pred, labels, cat_names),
        "subcategory": {k: v for k, v in report(s_te, s_pred, sorted(set(subs)), sub_names).items() if k != "confusion"},
        "coverage": coverage(c_te, proba, list(cat_model.classes_)),
        "auto_threshold": AUTO_THRESHOLD,
        "features": "TF-IDF word 1–2-grams + char_wb 2–5-grams on normalised text",
    }
    challenge = evaluate_csv(cat_model, sub_model, challenge_csv, cat_names) if challenge_csv else {}

    # deploy: refit on everything
    final_cat = build(best).fit(texts, cats)
    final_sub = build(best).fit(texts, subs)
    sub_parent = {s.code: s.category.code for s in Subcategory.objects.select_related("category")} | {OTHER_SUB: "other"}
    metrics["seconds"] = round(time.time() - t0, 1)
    return {
        "algorithm": best, "n_train": len(X_tr), "n_test": len(X_te), "sources": sources,
        "metrics": metrics, "challenge": challenge,
        "artifact": {"category": final_cat, "subcategory": final_sub, "sub_parent": sub_parent,
                     "cat_names": cat_names, "sub_names": sub_names},
    }


def _restricted_sub(sub_model, X, cat_pred, sub_parent=None):
    """Pick the most likely sub-type that belongs to the predicted category."""
    from apps.concerns.models import Subcategory

    parent = sub_parent or ({s.code: s.category.code for s in Subcategory.objects.select_related("category")}
                            | {OTHER_SUB: "other"})
    proba = sub_model.predict_proba(X)
    classes = list(sub_model.classes_)
    out = []
    for row, cat in zip(proba, cat_pred):
        best, bp = None, -1
        for j, code in enumerate(classes):
            if (parent.get(code) == cat or code == f"{cat}:*") and row[j] > bp:
                best, bp = code, row[j]
        out.append(best or classes[int(row.argmax())])
    return out


def evaluate_csv(cat_model, sub_model, path, cat_names):
    rows = read_csv(path)
    if not rows:
        return {}
    X = [r["text"] for r in rows]
    y = [r["category"] for r in rows]
    pred = cat_model.predict(X)
    proba = cat_model.predict_proba(X)
    labels = sorted(set(y) | set(pred))
    out = report(y, pred, labels, cat_names)
    out["coverage"] = coverage(y, proba, list(cat_model.classes_))
    ys = [r.get("subcategory") or OTHER_SUB for r in rows]
    sp = _restricted_sub(sub_model, X, pred)
    out["subcategory_accuracy"] = round(accuracy_score(ys, sp), 4)
    out["errors"] = [{"text": X[i], "expected": y[i], "predicted": pred[i], "confidence": round(float(proba[i].max()), 3)}
                     for i in range(len(X)) if y[i] != pred[i]][:40]
    out["source"] = str(path)
    return out


# ---------------------------------------------------------------- serving
_cache = {}


def active_artifact():
    from .models import ModelVersion

    mv = ModelVersion.objects.filter(is_active=True).first()
    if not mv:
        return None, None
    if _cache.get("version") != mv.version:
        path = model_dir() / mv.file
        if not path.exists() and not _pull_model(mv.file):
            return mv, None
        _cache.clear()
        _cache.update(version=mv.version, artifact=joblib.load(path))
    return mv, _cache["artifact"]


def classify(text, top_k=3):
    """{category, subcategory, confidence, top:[...], model_version} or None when no model is active."""
    mv, art = active_artifact()
    if not art or not (text or "").strip():
        return None
    cat_model, sub_model = art["category"], art["subcategory"]
    p = cat_model.predict_proba([text])[0]
    classes = list(cat_model.classes_)
    order = p.argsort()[::-1][:top_k]
    sp = sub_model.predict_proba([text])[0]
    sclasses = list(sub_model.classes_)
    top = []
    for j in order:
        cat = classes[j]
        best, bp = None, 0.0
        for k, code in enumerate(sclasses):
            if art["sub_parent"].get(code) == cat and sp[k] > bp:
                best, bp = code, float(sp[k])
        mass = sum(float(sp[k]) for k, code in enumerate(sclasses) if art["sub_parent"].get(code) == cat) or 1
        top.append({"category": cat, "category_name": art["cat_names"].get(cat, cat), "confidence": round(float(p[j]), 4),
                    "subcategory": best if best != OTHER_SUB else None,
                    "subcategory_name": art["sub_names"].get(best) if best and best != OTHER_SUB else None,
                    "subcategory_confidence": round(bp / mass, 4) if best else None})
    first = top[0]
    return {**first, "top": top, "model_version": mv.version, "auto": first["confidence"] >= AUTO_THRESHOLD}


def save_version(result, user=None, activate=False, notes=""):
    from django.db import transaction

    from .models import ModelVersion

    v = (ModelVersion.objects.order_by("-version").values_list("version", flat=True).first() or 0) + 1
    fname = f"classifier_v{v}.joblib"
    joblib.dump(result["artifact"], model_dir() / fname, compress=3)
    _push_model(fname)
    with transaction.atomic():
        current = ModelVersion.objects.filter(is_active=True).first()
        better = current is None or result["metrics"]["category"]["macro_f1"] >= (current.metrics.get("category", {}).get("macro_f1") or 0)
        mv = ModelVersion.objects.create(
            version=v, trained_by=user, algorithm=result["algorithm"], file=fname, n_train=result["n_train"],
            n_test=result["n_test"], data_sources=result["sources"], metrics=result["metrics"],
            challenge_metrics=result["challenge"], notes=notes,
        )
        if activate or better:
            ModelVersion.objects.filter(is_active=True).update(is_active=False)
            mv.is_active = True
            mv.save(update_fields=["is_active"])
    return mv


def summary_line(m):
    c = m["category"]
    return f"accuracy {c['accuracy']:.3f}, macro-F1 {c['macro_f1']:.3f} on {c['n']} held-out reports"


def mean(xs):
    xs = [x for x in xs if x is not None]
    return statistics.mean(xs) if xs else None

"""
Train, evaluate and register the complaint classifier (Module 3).

    python manage.py train_classifier                         # train on staff-verified reports, evaluate, activate if not worse
    python manage.py train_classifier --real-only             # ignore synthetic data (use once LGU data is loaded)
    python manage.py train_classifier --extra-csv logbook.csv # add labelled historical reports: text,category,subcategory
    python manage.py train_classifier --activate              # activate even if macro-F1 is lower than the current model

Writes ml/reports/classifier_v<N>.md (tables for Chapter 4) and the confusion matrix as CSV.
"""
import csv
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.classifier import pipeline

DEFAULT_CHALLENGE = Path(settings.BASE_DIR) / "ml" / "challenge_set.csv"


class Command(BaseCommand):
    help = "Train + evaluate the category/sub-type classifier and register a new model version."

    def add_arguments(self, p):
        p.add_argument("--real-only", action="store_true")
        p.add_argument("--extra-csv")
        p.add_argument("--challenge", default=str(DEFAULT_CHALLENGE))
        p.add_argument("--activate", action="store_true")
        p.add_argument("--notes", default="")
        p.add_argument("--before", help="YYYY-MM-DD: only train on reports created before this date (temporal hold-out).")

    def handle(self, *a, **o):
        challenge = o["challenge"] if Path(o["challenge"]).exists() else None
        before = None
        if o["before"]:
            from django.utils import timezone
            from django.utils.dateparse import parse_date
            from datetime import datetime
            before = timezone.make_aware(datetime.combine(parse_date(o["before"]), datetime.min.time()))
        res = pipeline.train(real_only=o["real_only"], extra_csv=o["extra_csv"], challenge_csv=challenge,
                             log=self.stdout.write, before=before)
        if before:
            o["notes"] = (o["notes"] + f" Trained only on reports before {o['before']}.").strip()
        mv = pipeline.save_version(res, activate=o["activate"], notes=o["notes"])
        m, ch = res["metrics"], res["challenge"]
        self.stdout.write(self.style.SUCCESS(
            f"v{mv.version} ({res['algorithm']}) {pipeline.summary_line(m)}"
            + (f"; challenge set accuracy {ch['accuracy']:.3f}, macro-F1 {ch['macro_f1']:.3f} (n={ch['n']})" if ch else "")
            + (" — ACTIVE" if mv.is_active else " — not activated (lower macro-F1 than the active model)")))
        path = write_report(mv, res)
        self.stdout.write(f"  report: {path}")


def write_report(mv, res):
    out = Path(settings.BASE_DIR) / "ml" / "reports"
    out.mkdir(parents=True, exist_ok=True)
    m, ch = res["metrics"], res["challenge"]
    L = [f"# Classifier v{mv.version} evaluation", "",
         f"Algorithm selected: **{m['algorithm']}** ({m['selection']}). Features: {m['features']}.",
         f"Data: {res['sources']} → {res['n_train']} training / {res['n_test']} held-out test reports.", "",
         "## Model comparison (category)", "", "| Model | CV macro-F1 (5-fold) | Test accuracy | Test macro-F1 |", "|---|---|---|---|"]
    for r in m["comparison"]:
        cv = "—" if r["cv_macro_f1"] is None else f"{r['cv_macro_f1']:.3f} ± {r.get('cv_std', 0):.3f}"
        L.append(f"| {r['algorithm']} | {cv} | {r['test_accuracy']:.3f} | {r['test_macro_f1']:.3f} |")
    L += ["", "## Per category (held-out test set)", "", "| Category | Precision | Recall | F1 | Support |", "|---|---|---|---|---|"]
    for c in m["category"]["per_class"]:
        L.append(f"| {c['name']} | {c['precision']:.3f} | {c['recall']:.3f} | {c['f1']:.3f} | {c['support']} |")
    L += ["", f"Category accuracy **{m['category']['accuracy']:.3f}**, macro-F1 **{m['category']['macro_f1']:.3f}**. "
              f"Sub-type accuracy {m['subcategory']['accuracy']:.3f}.", "",
          "## Auto-assign policy (confidence threshold vs. coverage)", "", "| Threshold | Share auto-assigned | Accuracy of those |", "|---|---|---|"]
    for r in m["coverage"]:
        L.append(f"| ≥ {r['threshold']:.0%} | {r['coverage']:.1%} | {'—' if r['accuracy'] is None else f'{r['accuracy']:.1%}'} |")
    if ch:
        L += ["", "## Hand-written challenge set", "",
              f"{ch['n']} complaints written independently of the synthetic generator: accuracy **{ch['accuracy']:.3f}**, "
              f"macro-F1 **{ch['macro_f1']:.3f}**, sub-type accuracy {ch['subcategory_accuracy']:.3f}.", "",
              "| Category | Precision | Recall | F1 | n |", "|---|---|---|---|---|"]
        for c in ch["per_class"]:
            L.append(f"| {c['name']} | {c['precision']:.3f} | {c['recall']:.3f} | {c['f1']:.3f} | {c['support']} |")
        L += ["", "Auto-assign on the challenge set:", "", "| Threshold | Share auto-assigned | Accuracy of those |", "|---|---|---|"]
        for r in ch["coverage"]:
            L.append(f"| ≥ {r['threshold']:.0%} | {r['coverage']:.1%} | {'—' if r['accuracy'] is None else f'{r['accuracy']:.1%}'} |")
        if ch["errors"]:
            L += ["", "Misclassified examples:", ""] + [f"- “{e['text']}” → {e['predicted']} (expected {e['expected']}, "
                                                         f"confidence {e['confidence']:.0%})" for e in ch["errors"][:12]]
    L += ["", "## Limitations", "",
          "- Synthetic reports are generated from phrase banks; scores on them are optimistic.",
          "- The challenge set is small and written by the developers; real LGU reports are the decisive test.",
          "- Retrain with `--real-only` or `--extra-csv` once anonymised LGU complaints are available."]
    md = out / f"classifier_v{mv.version}.md"
    md.write_text("\n".join(L), encoding="utf-8")
    cm = m["category"]["confusion"]
    with open(out / f"classifier_v{mv.version}_confusion.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["actual \\ predicted"] + cm["labels"])
        for lab, row in zip(cm["labels"], cm["matrix"]):
            w.writerow([lab] + row)
    return md

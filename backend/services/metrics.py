from statistics import mean
from functools import lru_cache

from nltk.translate.meteor_score import meteor_score
from rouge_score import rouge_scorer

try:
    from nltk.corpus import wordnet as nltk_wordnet
except Exception:  # pragma: no cover
    nltk_wordnet = None


_rouge = rouge_scorer.RougeScorer(["rouge1", "rouge2", "rougeL"], use_stemmer=True)


class _NoWordNet:
    @staticmethod
    def synsets(_word: str) -> list:
        return []


def _safe_meteor(reference: str, prediction: str) -> float:
    ref_tokens = reference.split()
    pred_tokens = prediction.split()

    if nltk_wordnet is not None:
        try:
            return float(meteor_score([ref_tokens], pred_tokens, wordnet=nltk_wordnet))
        except LookupError:
            pass

    return float(meteor_score([ref_tokens], pred_tokens, wordnet=_NoWordNet()))

@lru_cache(maxsize=1)
def _get_bert_score_fn():
    try:
        from bert_score import score as bert_score_fn
        return bert_score_fn
    except Exception:  # pragma: no cover
        return None


@lru_cache(maxsize=1)
def _get_bert_scorer():
    try:
        from bert_score import BERTScorer
        return BERTScorer(lang="id")
    except Exception:  # pragma: no cover
        return None


def compute_text_metrics(reference: str, prediction: str) -> dict[str, float | None]:
    rouge = _rouge.score(reference, prediction)

    meteor = _safe_meteor(reference, prediction)

    bert_f1 = None
    bert_scorer = _get_bert_scorer()
    if bert_scorer is not None:
        _, _, f1 = bert_scorer.score([prediction], [reference])
        bert_f1 = float(f1[0].item())
    else:
        # Backward-compatible fallback for environments where BERTScorer cannot be built.
        bert_score = _get_bert_score_fn()
        if bert_score is not None:
            _, _, f1 = bert_score([prediction], [reference], lang="id", verbose=False)
            bert_f1 = float(f1[0].item())

    return {
        "rouge1_f1": float(rouge["rouge1"].fmeasure),
        "rouge2_f1": float(rouge["rouge2"].fmeasure),
        "rougel_f1": float(rouge["rougeL"].fmeasure),
        "meteor": float(meteor),
        "bertscore_f1": bert_f1,
    }


def summarize_metrics(items: list[dict]) -> dict[str, float | None]:
    def avg(field: str) -> float | None:
        vals = [float(item[field]) for item in items if item.get(field) is not None]
        return float(mean(vals)) if vals else None

    return {
        "rouge1_f1": avg("rouge1_f1"),
        "rouge2_f1": avg("rouge2_f1"),
        "rougel_f1": avg("rougel_f1"),
        "meteor": avg("meteor"),
        "bertscore_f1": avg("bertscore_f1"),
        "latency_ms": avg("latency_ms"),
    }

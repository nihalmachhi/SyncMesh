"""Offline TF-IDF and token similarity suggestions for possible duplicates."""

from collections import Counter
from math import log, sqrt

from syncmesh.nlp.normalize import normalize_name


def similarity(left: str, right: str) -> float:
    """Combine character 3-5 gram TF-IDF cosine with token-set Jaccard."""
    a, b = normalize_name(left), normalize_name(right)
    if not a or not b:
        return 0.0
    grams_a, grams_b = _ngrams(a), _ngrams(b)
    vocabulary = set(grams_a) | set(grams_b)
    vectors = []
    for grams in (grams_a, grams_b):
        vector = {
            gram: count * (log(2 / (int(gram in grams_a) + int(gram in grams_b))) + 1)
            for gram, count in grams.items()
        }
        vectors.append(vector)
    dot = sum(vectors[0].get(gram, 0) * vectors[1].get(gram, 0) for gram in vocabulary)
    norm_a = sqrt(sum(value * value for value in vectors[0].values()))
    norm_b = sqrt(sum(value * value for value in vectors[1].values()))
    cosine = dot / (norm_a * norm_b) if norm_a and norm_b else 0.0
    tokens_a, tokens_b = set(a.split()), set(b.split())
    jaccard = len(tokens_a & tokens_b) / len(tokens_a | tokens_b)
    return round(0.7 * cosine + 0.3 * jaccard, 6)


def find_duplicates(items: list[dict], threshold: float = 0.72) -> list[dict]:
    """Return deterministic candidate pairs; suggestions never merge automatically."""
    candidates = []
    ordered = sorted(items, key=lambda item: str(item.get("id", "")))
    for index, left in enumerate(ordered):
        for right in ordered[index + 1 :]:
            score = similarity(str(left.get("name", "")), str(right.get("name", "")))
            if score >= threshold:
                candidates.append(
                    {"left_id": left.get("id"), "right_id": right.get("id"), "score": score}
                )
    return candidates


def _ngrams(value: str) -> Counter[str]:
    """Count padded character n-grams from length three through five."""
    padded = f"  {value}  "
    return Counter(
        padded[start : start + size]
        for size in (3, 4, 5)
        for start in range(max(0, len(padded) - size + 1))
    )


def suggest_category(names: list[str], categories: list[str], name: str) -> str:
    """Train a tiny local Multinomial Naive Bayes model for category hints."""
    try:
        from sklearn.feature_extraction.text import CountVectorizer  # type: ignore[import-untyped]
        from sklearn.naive_bayes import MultinomialNB  # type: ignore[import-untyped]
    except ImportError as error:
        raise RuntimeError(
            "install SyncMesh with the [nlp] extra to use category suggestions"
        ) from error
    if len(names) != len(categories) or not names:
        raise ValueError("training names and categories must have equal nonzero length")
    vectorizer = CountVectorizer(ngram_range=(1, 2), strip_accents="unicode")
    training = vectorizer.fit_transform([normalize_name(value) for value in names])
    classifier = MultinomialNB().fit(training, categories)
    prediction = classifier.predict(vectorizer.transform([normalize_name(name)]))
    return str(prediction[0])


def evaluate_dedupe() -> dict:
    """Measure candidate precision and recall on fixed labelled synthetic pairs."""
    examples = [
        ("Organic brown rice 1 kg", "Brown-rice 1000 g", True),
        ("Dark roast coffee beans", "Coffee beans, dark roast", True),
        ("Unsweetened almond milk", "Almond milk unsweetened", True),
        ("Long grain brown rice", "Brown rice flour", False),
        ("Apple juice", "Apple cider vinegar", False),
        ("Whole cow milk", "Oat milk", False),
        ("Green tea bags", "Green tea, 25 bags", True),
        ("Sea salt fine", "Fine sea-salt", True),
        ("Red lentils", "Red lentil soup", False),
        ("Olive oil extra virgin", "Extra-virgin olive oil", True),
    ]
    calibration = examples[:6]
    evaluation = examples[6:]
    thresholds = sorted({round(similarity(left, right), 6) for left, right, _ in calibration})
    thresholds += [round(value / 100, 2) for value in range(101)]

    def calibration_score(candidate: float) -> tuple[float, float, float]:
        tp = sum(
            similarity(left, right) >= candidate and label for left, right, label in calibration
        )
        fp = sum(
            similarity(left, right) >= candidate and not label for left, right, label in calibration
        )
        fn = sum(
            similarity(left, right) < candidate and label for left, right, label in calibration
        )
        precision = tp / max(1, tp + fp)
        recall = tp / max(1, tp + fn)
        f1 = 2 * precision * recall / max(1e-12, precision + recall)
        return f1, precision, candidate

    threshold = max(thresholds, key=calibration_score)
    true_positive = false_positive = false_negative = 0
    for left, right, label in evaluation:
        prediction = similarity(left, right) >= threshold
        true_positive += int(prediction and label)
        false_positive += int(prediction and not label)
        false_negative += int(not prediction and label)
    return {
        "synthetic_pairs": len(examples),
        "calibration_pairs": len(calibration),
        "evaluation_pairs": len(evaluation),
        "threshold": threshold,
        "precision": round(true_positive / max(1, true_positive + false_positive), 4),
        "recall": round(true_positive / max(1, true_positive + false_negative), 4),
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "synthetic": True,
        "limitation": (
            "Only ten fixed synthetic product pairs; this does not estimate real catalog accuracy."
        ),
    }

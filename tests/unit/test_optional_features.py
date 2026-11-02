"""Optional offline NLP and vision helpers."""

import hashlib

import pytest

from syncmesh.nlp.dedupe import evaluate_dedupe, find_duplicates, similarity, suggest_category
from syncmesh.nlp.normalize import normalize_name
from syncmesh.vision.barcode import decode_code, valid_ean13
from syncmesh.vision.blobs import ChunkAssembler, store_blob
from syncmesh.vision.phash import difference_hash, hamming_distance


def test_name_normalization_handles_unicode_punctuation_and_mass_units():
    """Equivalent Unicode and metric product quantities normalize together."""
    assert normalize_name("BROWN-RICE 1 kg") == normalize_name("Brown Rice 1000 g")
    assert normalize_name("  Crème—brûlée ") == "crème brûlée"
    assert similarity("BROWN-RICE 1 kg", "Brown Rice 1000 g") > 0.9


def test_duplicate_helper_returns_suggestion_pairs_in_stable_order():
    """The NLP helper suggests likely duplicates without mutating source data."""
    items = [
        {"id": "b", "name": "Coffee beans dark roast"},
        {"id": "a", "name": "Dark roast coffee beans"},
    ]

    suggestions = find_duplicates(items, threshold=0.6)

    assert suggestions[0]["left_id"] == "a"
    assert suggestions[0]["right_id"] == "b"
    assert items[0]["id"] == "b"


def test_generated_duplicate_evaluation_is_labelled_and_repeatable():
    """Generated precision and recall describe the fixed synthetic fixture only."""
    result = evaluate_dedupe()

    assert result == evaluate_dedupe()
    assert result["synthetic"] is True
    assert result["synthetic_pairs"] == 10
    assert 0 <= result["precision"] <= 1
    assert 0 <= result["recall"] <= 1


def test_local_category_suggestion_uses_optional_naive_bayes():
    """The optional sklearn model returns a category from local training examples."""
    result = suggest_category(
        ["brown rice", "basmati rice", "green tea", "black tea"],
        ["Grains", "Grains", "Tea", "Tea"],
        "jasmine tea",
    )

    assert result == "Tea"


def test_ean13_checksum_validates_and_rejects_bad_values():
    """EAN-13 checks use the standardized alternating checksum weights."""
    assert valid_ean13("4006381333931")
    assert not valid_ean13("4006381333932")
    assert not valid_ean13("not-a-barcode")


def test_chunked_blobs_resume_and_verify_content_address(tmp_path):
    """Sequential chunks reconstruct the exact SHA-256-addressed payload."""
    payload = b"synthetic image attachment"
    digest = hashlib.sha256(payload).hexdigest()
    assembler = ChunkAssembler(digest, len(payload))

    assert assembler.append(0, payload[:8]) is False
    assert assembler.offset == 8
    with pytest.raises(ValueError, match="offset"):
        assembler.append(1, payload[8:])
    assert assembler.append(8, payload[8:]) is True
    assert assembler.bytes() == payload
    assert store_blob(payload, tmp_path) == digest
    assert (tmp_path / digest).read_bytes() == payload


def test_perceptual_hash_is_stable_and_counts_pixel_differences():
    """dHash helpers operate on images generated in the test itself."""
    image_module = pytest.importorskip("PIL.Image")
    from io import BytesIO

    original = image_module.new("L", (12, 12), color=10)
    changed = image_module.new("L", (12, 12), color=230)
    original_bytes, changed_bytes = BytesIO(), BytesIO()
    original.save(original_bytes, format="PNG")
    changed.save(changed_bytes, format="PNG")

    first = difference_hash(original_bytes.getvalue())
    second = difference_hash(changed_bytes.getvalue())
    assert len(first) == 16
    assert hamming_distance(first, first) == 0
    assert hamming_distance(first, second) == 0


def test_generated_qr_code_decodes_offline_with_opencv():
    """A QR image generated at test time is decoded without network access."""
    pytest.importorskip("cv2")
    qrcode = pytest.importorskip("qrcode")
    from io import BytesIO

    buffer = BytesIO()
    qrcode.make("syncmesh:item:SKU-42", box_size=8, border=4).save(buffer, format="PNG")

    assert decode_code(buffer.getvalue()) == "syncmesh:item:SKU-42"

"""EAN-13 validation and local QR/barcode decoding helpers."""


def valid_ean13(value: str) -> bool:
    """Check an EAN-13 number using its alternating 1/3 checksum weights."""
    if len(value) != 13 or not value.isascii() or not value.isdigit():
        return False
    checksum = sum(
        int(digit) * (1 if index % 2 == 0 else 3) for index, digit in enumerate(value[:12])
    )
    return (10 - checksum % 10) % 10 == int(value[-1])


def decode_code(image_bytes: bytes) -> str | None:
    """Decode a QR code or a supported linear barcode with OpenCV locally."""
    try:
        import cv2
        import numpy as np
    except ImportError as error:
        raise RuntimeError("install SyncMesh with the [vision] extra to scan codes") from error
    image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("image bytes could not be decoded")
    qr_text, _, _ = cv2.QRCodeDetector().detectAndDecode(image)
    if qr_text:
        return qr_text
    barcode_detector = getattr(cv2, "barcode_BarcodeDetector", None)
    if barcode_detector is None:
        return None
    found, values, _, _ = barcode_detector().detectAndDecodeWithType(image)
    return values[0] if found and values else None

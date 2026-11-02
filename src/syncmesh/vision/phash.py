"""Small perceptual hash helper for visually similar product photos."""

from io import BytesIO


def difference_hash(image_bytes: bytes) -> str:
    """Compute a 64-bit dHash from an image using the optional Pillow extra."""
    try:
        from PIL import Image
    except ImportError as error:
        raise RuntimeError("install SyncMesh with the [vision] extra to hash photos") from error
    image = Image.open(BytesIO(image_bytes)).convert("L").resize((9, 8))
    pixels = list(image.tobytes())
    bits = [
        pixels[row * 9 + col] > pixels[row * 9 + col + 1] for row in range(8) for col in range(8)
    ]
    return f"{sum(int(bit) << (63 - index) for index, bit in enumerate(bits)):016x}"


def hamming_distance(left: str, right: str) -> int:
    """Count differing bits between two hexadecimal dHash values."""
    if len(left) != 16 or len(right) != 16:
        raise ValueError("dHash values must contain exactly 16 hexadecimal digits")
    try:
        return (int(left, 16) ^ int(right, 16)).bit_count()
    except ValueError as error:
        raise ValueError("dHash values must be hexadecimal") from error

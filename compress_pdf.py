import argparse
import io
import os
from dataclasses import dataclass
from typing import Iterable, List, Tuple

import pikepdf
from PIL import Image


BYTES_IN_MB = 1024 * 1024


@dataclass
class CompressionAttempt:
    quality: int
    max_dimension: int


@dataclass
class CompressionStats:
    images_processed: int = 0
    images_recompressed: int = 0
    failures: int = 0


def _human_size(num_bytes: int) -> str:
    return f"{num_bytes / BYTES_IN_MB:.2f} MB"


def _validate_inputs(input_path: str, target_mb: int, max_input_mb: int) -> None:
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    input_size = os.path.getsize(input_path)
    if input_size > max_input_mb * BYTES_IN_MB:
        raise ValueError(
            f"Input file is too large ({_human_size(input_size)}). "
            f"Maximum supported size is {max_input_mb} MB."
        )

    if target_mb <= 0:
        raise ValueError("Target size must be greater than 0 MB.")


def _resize_image(image: Image.Image, max_dimension: int) -> Image.Image:
    width, height = image.size
    max_current_dimension = max(width, height)
    if max_current_dimension <= max_dimension:
        return image

    scale = max_dimension / max_current_dimension
    new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
    return image.resize(new_size, Image.Resampling.LANCZOS)


def _recompress_images(
    pdf: pikepdf.Pdf, quality: int, max_dimension: int
) -> CompressionStats:
    stats = CompressionStats()

    for page in pdf.pages:
        image_names = list(page.images.keys())
        for image_name in image_names:
            stats.images_processed += 1
            try:
                pdf_image = pikepdf.PdfImage(page.images[image_name])
                with pdf_image.as_pil_image() as image:
                    image = image.convert("RGB")
                    image = _resize_image(image, max_dimension)
                    buffer = io.BytesIO()
                    image.save(
                        buffer,
                        format="JPEG",
                        optimize=True,
                        quality=quality,
                        progressive=True,
                    )
                    buffer.seek(0)
                    new_stream = pikepdf.Stream(
                        pdf, buffer.read(), Filter=pikepdf.Name("/DCTDecode")
                    )
                    new_stream["/Type"] = pikepdf.Name("/XObject")
                    new_stream["/Subtype"] = pikepdf.Name("/Image")
                    new_stream["/Width"] = image.width
                    new_stream["/Height"] = image.height
                    new_stream["/ColorSpace"] = pikepdf.Name("/DeviceRGB")
                    new_stream["/BitsPerComponent"] = 8
                    page.images[image_name] = new_stream
                    stats.images_recompressed += 1
            except Exception:
                stats.failures += 1
                continue

    return stats


def _save_pdf(pdf: pikepdf.Pdf, output_path: str) -> None:
    pdf.save(
        output_path,
        compress_streams=True,
        object_stream_mode=pikepdf.ObjectStreamMode.generate,
        linearize=True,
    )


def _attempts_sequence() -> Iterable[CompressionAttempt]:
    return [
        CompressionAttempt(quality=80, max_dimension=2600),
        CompressionAttempt(quality=70, max_dimension=2200),
        CompressionAttempt(quality=60, max_dimension=2000),
        CompressionAttempt(quality=50, max_dimension=1800),
        CompressionAttempt(quality=40, max_dimension=1600),
        CompressionAttempt(quality=30, max_dimension=1400),
    ]


def compress_pdf(
    input_path: str,
    output_path: str,
    target_mb: int = 100,
    max_input_mb: int = 2000,
) -> Tuple[bool, List[CompressionStats]]:
    _validate_inputs(input_path, target_mb, max_input_mb)
    attempt_stats: List[CompressionStats] = []

    for attempt in _attempts_sequence():
        with pikepdf.open(input_path) as pdf:
            stats = _recompress_images(pdf, attempt.quality, attempt.max_dimension)
            _save_pdf(pdf, output_path)
            attempt_stats.append(stats)

        output_size = os.path.getsize(output_path)
        if output_size <= target_mb * BYTES_IN_MB:
            return True, attempt_stats

    return False, attempt_stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compress a PDF by recompressing images while keeping the document content intact."
        )
    )
    parser.add_argument("input", help="Path to the input PDF (max 2 GB).")
    parser.add_argument("output", help="Path to the compressed PDF.")
    parser.add_argument(
        "--target-mb",
        type=int,
        default=100,
        help="Desired maximum output size in MB (default: 100).",
    )
    parser.add_argument(
        "--max-input-mb",
        type=int,
        default=2000,
        help="Maximum allowed input size in MB (default: 2000).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        success, attempts = compress_pdf(
            input_path=args.input,
            output_path=args.output,
            target_mb=args.target_mb,
            max_input_mb=args.max_input_mb,
        )
    except Exception as exc:
        raise SystemExit(f"Compression failed: {exc}") from exc

    output_size = os.path.getsize(args.output)
    print(f"Output file size: {_human_size(output_size)}")

    if success:
        print("Compression succeeded within target size.")
    else:
        print(
            "Compression completed but did not reach the target size. "
            "Consider lowering --target-mb or adjusting the input."
        )

    for index, stats in enumerate(attempts, start=1):
        print(
            f"Attempt {index}: processed {stats.images_processed} images, "
            f"recompressed {stats.images_recompressed}, "
            f"failed {stats.failures}."
        )


if __name__ == "__main__":
    main()

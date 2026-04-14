"""
utils/image_search.py
----------------------
Image search menggunakan OpenAI GPT-4o-mini Vision:
1. Gambar dianalisis oleh GPT-4o-mini → deskripsi teks produk
2. Deskripsi di-embed dengan text-embedding-3-small
3. Embedding digunakan untuk search di Qdrant

Pendekatan ini TIDAK butuh torch/CLIP — lebih ringan dan akurat
karena GPT-4o-mini bisa memahami konteks visual produk.
"""

import os
import base64
from io import BytesIO
from typing import Union
from dotenv import load_dotenv

load_dotenv()


def _image_to_base64(image_input: Union[str, bytes]) -> str:
    """Convert image file path atau bytes ke base64 string."""
    if isinstance(image_input, str):
        with open(image_input, "rb") as f:
            data = f.read()
    elif isinstance(image_input, bytes):
        data = image_input
    else:
        raise ValueError(f"Unsupported image_input type: {type(image_input)}")
    return base64.b64encode(data).decode("utf-8")


def describe_image(image_input: Union[str, bytes]) -> str:
    """
    Gunakan GPT-4o-mini Vision untuk mendeskripsikan produk dalam gambar.
    Output: teks deskripsi produk dalam Bahasa Indonesia + Inggris.
    """
    from utils.observability import get_openai_embed_client
    client = get_openai_embed_client()

    b64 = _image_to_base64(image_input)

    # Deteksi format gambar dari magic bytes
    if isinstance(image_input, bytes):
        if image_input[:4] == b'\x89PNG':
            mime = "image/png"
        elif image_input[:2] == b'\xff\xd8':
            mime = "image/jpeg"
        elif image_input[:4] == b'RIFF':
            mime = "image/webp"
        else:
            mime = "image/jpeg"  # default
    else:
        ext = str(image_input).lower().split(".")[-1]
        mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                "png": "image/png", "webp": "image/webp"}.get(ext, "image/jpeg")

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{b64}"},
                    },
                    {
                        "type": "text",
                        "text": (
                            "Deskripsikan produk dalam gambar ini secara singkat untuk keperluan pencarian e-commerce. "
                            "Sebutkan: jenis produk, warna, material, kategori, dan ciri khas utama. "
                            "Jawab dalam 2-3 kalimat, Bahasa Indonesia."
                        ),
                    },
                ],
            }
        ],
        max_tokens=200,
    )

    return response.choices[0].message.content.strip()


def get_image_embedding(image_input: Union[str, bytes]) -> list[float]:
    """
    Generate embedding dari gambar via:
    1. GPT-4o-mini Vision → deskripsi teks
    2. text-embedding-3-small → embedding vektor

    Compatible dengan Qdrant yang menyimpan text embeddings (dim=1536).
    """
    from utils.observability import get_openai_embed_client

    # Step 1: dapatkan deskripsi teks dari gambar
    description = describe_image(image_input)
    print(f"  🔍 Deskripsi gambar: {description}")

    # Step 2: embed deskripsi teks → vektor 1536 dim
    client = get_openai_embed_client()
    response = client.embeddings.create(
        model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
        input=description,
    )
    return response.data[0].embedding

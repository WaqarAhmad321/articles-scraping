import hashlib


def make_article_id(url: str) -> str:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()
    return f"ART{digest[:8].upper()}"

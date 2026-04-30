from urllib.parse import urlparse


# English URL/section markers
_OPINION_HINTS = ("opinion", "op-ed", "oped", "column", "viewpoint", "comment", "columnist")
_BLOG_HINTS = ("blog", "blogs", "weblog")
_EDITORIAL_HINTS = ("editorial", "editorials", "idaria")

# Urdu (Naskh) markers — appear in section breadcrumbs / JSON-LD articleSection
# returned by Express, DawnNews, ARY-Urdu, BBC Urdu.
_OPINION_HINTS_UR = ("رائے", "نقطہ نظر", "کالم", "قلم کار", "تجزیہ")
_BLOG_HINTS_UR = ("بلاگ",)
_EDITORIAL_HINTS_UR = ("اداریہ", "اداریے")


def classify_article_type(url: str, section: str | None = None) -> str:
    """Classify an article by its URL path and optional section/breadcrumb.
    Section can be e.g. JSON-LD's `articleSection` value, which often carries
    the Urdu label even when the URL is transliterated."""
    path = urlparse(url).path.lower()
    sec_raw = section or ""
    sec_lower = sec_raw.lower()
    haystack_en = path + " " + sec_lower

    # Editorial wins over Blog wins over Opinion (most specific first)
    if any(h in haystack_en for h in _EDITORIAL_HINTS) or any(h in sec_raw for h in _EDITORIAL_HINTS_UR):
        return "Editorial"
    if any(h in haystack_en for h in _BLOG_HINTS) or any(h in sec_raw for h in _BLOG_HINTS_UR):
        return "Blog"
    if any(h in haystack_en for h in _OPINION_HINTS) or any(h in sec_raw for h in _OPINION_HINTS_UR):
        return "Opinion"
    return "News Report"

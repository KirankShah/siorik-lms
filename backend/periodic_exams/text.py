import html
import re
import unicodedata

from django.utils.html import strip_tags


def normalize_question_text(question_text):
    """Canonical visible question text used as the Periodic Exam no-repeat key.

    Mirrors Level Assessment's normalization (HTML markup/entities, Unicode
    forms, case, punctuation and whitespace are ignored) without importing
    Level Assessment services. A parity test guards against drift.
    """
    visible_text = strip_tags(html.unescape(question_text or ''))
    normalized = unicodedata.normalize('NFKC', visible_text).casefold()
    return ' '.join(re.findall(r'[^\W_]+', normalized, flags=re.UNICODE))

import unicodedata


def remove_accents(input_str: str) -> str:
    """Strip diacritics from a string via NFKD normalization."""
    if not input_str:
        return ""
    nfkd_form = unicodedata.normalize('NFKD', str(input_str))
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])

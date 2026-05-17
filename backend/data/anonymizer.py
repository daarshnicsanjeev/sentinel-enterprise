import spacy

_nlp = spacy.load("en_core_web_sm")
_ENTITY_TYPES = {"PERSON", "ORG", "GPE"}


def anonymize(text: str) -> tuple[str, dict[str, str]]:
    """Replace PERSON, ORG, GPE named entities with tokens like [PERSON_1]. Returns (anonymized, mapping)."""
    doc = _nlp(text)
    entity_map: dict[str, str] = {}
    counters: dict[str, int] = {}
    result = text
    for ent in reversed(doc.ents):
        if ent.label_ in _ENTITY_TYPES:
            counters[ent.label_] = counters.get(ent.label_, 0) + 1
            token = f"[{ent.label_}_{counters[ent.label_]}]"
            entity_map[token] = ent.text
            result = result[: ent.start_char] + token + result[ent.end_char :]
    return result, entity_map

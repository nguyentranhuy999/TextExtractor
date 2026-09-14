from __future__ import annotations

import random
import re
import unicodedata
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from .schemas import TableOutput
from .utils import read_json

ALIASES_PATH = Path(__file__).parent / "resources" / "aliases.json"
ALIASES = read_json(ALIASES_PATH)


def norm(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).casefold().split())


def label(value):
    return re.sub(r"[\s_-]+", " ", norm(value)).strip()


def canonical(value, groups):
    key = label(value)
    for name, aliases in groups.items():
        if key in {label(x) for x in [name, *aliases]}:
            return name
    return key


def table_id(name):
    return canonical(name, ALIASES["tables"])


def field_id(table, name):
    return canonical(name, ALIASES["fields"].get(table, {}))


ONES = dict(zip("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split(), range(20)))
TENS = dict(zip("twenty thirty forty fifty sixty seventy eighty ninety".split(), range(20, 100, 10)))


def word_number(value):
    words = value.replace("-", " ").split()
    sign = -1 if words and words[0] in ("minus", "negative") else 1
    if sign < 0:
        words = words[1:]
    if not words:
        return None
    if "point" in words:
        i = words.index("point")
        integer = word_number(" ".join(words[:i]))
        fraction = words[i + 1:]
        if integer is None or not fraction or any(w not in ONES or ONES[w] > 9 for w in fraction):
            return None
        return sign * (integer + Decimal("0." + "".join(str(ONES[w]) for w in fraction)))
    total = current = 0
    previous = None
    for word in words:
        if word in ONES:
            if previous in ONES or (previous in TENS and ONES[word] >= 10):
                return None
            current += ONES[word]
        elif word in TENS:
            if previous in ONES or previous in TENS:
                return None
            current += TENS[word]
        elif word == "hundred" and current:
            current *= 100
        elif word == "thousand" and current:
            total += current * 1000
            current = 0
        elif word == "and" and previous in ("hundred", "thousand"):
            continue
        else:
            return None
        previous = word
    return Decimal(sign * (total + current))


def normalized_value(raw, table, field):
    if raw is None or not isinstance(raw, str) or not raw.strip():
        return None
    value = norm(raw)
    if value in ("null", "none", "n/a", "na"):
        return None
    percentage = "percentage" in field or field.endswith("%")
    has_percent = bool(re.search(r"(?:%|percent|per cent)$", value))
    if has_percent:
        if not percentage:
            return "unit:percent:" + value
        value = re.sub(r"\s*(?:%|percent|per cent)$", "", value).strip()
    if re.fullmatch(r"[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|[+-]?\.\d+", value):
        try:
            number = Decimal(value.replace(",", ""))
        except InvalidOperation:
            number = None
    else:
        number = word_number(value)
    if number is not None:
        return "num:" + (format(number.normalize(), "f") if number else "0")
    return "str:" + value


def entity_map(gold: TableOutput):
    names = defaultdict(set)
    for table in gold.tables:
        names[table_id(table.table_name)].update(norm(r.entity_name) for r in table.rows)
    return names


def resolve_entity(raw, candidates):
    key = norm(raw)
    if key in candidates or key.startswith("__unresolved_"):
        return key
    pieces = re.findall(r"\w+", key)
    matches = []
    for candidate in candidates:
        full = re.findall(r"\w+", candidate)
        if not pieces or not full:
            continue
        # Suffix (surname, team nickname), prefix (city), or initial + surname.
        suffix = len(pieces) < len(full) and full[-len(pieces):] == pieces
        prefix = len(pieces) < len(full) and full[:len(pieces)] == pieces
        expanded = len(pieces) > len(full) and (pieces[-len(full):] == full or pieces[:len(full)] == full)
        initial = len(pieces) == len(full) and pieces[-1] == full[-1] and all(a == b or len(a) == 1 and b.startswith(a) for a, b in zip(pieces[:-1], full[:-1]))
        if suffix or prefix or initial or expanded:
            matches.append(candidate)
    return matches[0] if len(matches) == 1 else key


def sets(output, gold_names=None):
    facts, fields, entities = set(), set(), set()
    total_facts = 0
    cell_values = defaultdict(set)
    for table in output.tables:
        kind = table_id(table.table_name)
        fields.update((kind, field_id(kind, f)) for f in table.field_names)
        for row in table.rows:
            entity = resolve_entity(row.entity_name, (gold_names or {}).get(kind, set()))
            entities.add((kind, entity))
            for cell in row.cells:
                field = field_id(kind, cell.field_name)
                fields.add((kind, field))
                for raw in cell.raw_values:
                    value = normalized_value(raw, kind, field)
                    if value is not None:
                        fact = (kind, entity, field, value)
                        facts.add(fact)
                        total_facts += 1
                        cell_values[fact[:3]].add(value)
    return dict(facts=facts, fields=fields, entities=entities, duplicates=total_facts-len(facts), conflicts=sum(len(v)>1 for v in cell_values.values()))


def counts(pred, gold):
    return dict(tp=len(pred & gold), fp=len(pred-gold), fn=len(gold-pred))


def scores(tp, fp, fn):
    empty = tp+fp+fn == 0
    return dict(precision=tp/(tp+fp) if tp+fp else float(empty), recall=tp/(tp+fn) if tp+fn else float(empty), f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 1.0)


def score_output(prediction: TableOutput, gold: TableOutput, kind=None):
    p, g = sets(prediction, entity_map(gold)), sets(gold)
    if kind:
        p = {**p, **{k:{v for v in p[k] if v[0] == kind} for k in ("facts", "fields", "entities")}}
        g = {**g, **{k:{v for v in g[k] if v[0] == kind} for k in ("facts", "fields", "entities")}}
    result = {}
    for name in ("facts", "fields", "entities"):
        c = counts(p[name], g[name])
        result[name] = {**c, **scores(**c), "gold_count":len(g[name])}
    result.update(exact=all(p[k] == g[k] for k in ("facts", "fields", "entities")), duplicates=p["duplicates"], conflicts=p["conflicts"], both_empty=not p["facts"] and not g["facts"])
    errors = defaultdict(list)
    for fact in sorted(g["facts"] - p["facts"]):
        kind, entity, field, _ = fact
        category = "missing_field" if (kind, field) not in p["fields"] else "missing_entity" if (kind, entity) not in p["entities"] else "missing_or_wrong_value"
        errors[category].append(fact)
    errors["extra_or_wrong_fact"] = sorted(p["facts"] - g["facts"])
    errors["extra_field"] = sorted(p["fields"] - g["fields"])
    result["errors"] = dict(errors)
    return result


def aggregate_counts(rows, metric="facts"):
    return {key:sum(row[metric][key] for row in rows) for key in ("tp", "fp", "fn")}


def quantile(values, q):
    if not values:
        return None
    v = sorted(values)
    pos = (len(v)-1)*q
    lo = int(pos)
    return v[lo] + (v[min(lo+1,len(v)-1)]-v[lo])*(pos-lo)


def paired_bootstrap(left, right, latencies_left, latencies_right, *, seed=2026, repetitions=2000, game_keys=None):
    ids = sorted(set(left) & set(right))
    paired = sorted(set(latencies_left) & set(latencies_right))
    rng = random.Random(seed)
    def clusters(members):
        groups = defaultdict(list)
        for sid in members:
            groups[(game_keys or {}).get(sid) or sid].append(sid)
        return list(groups.values())
    quality_groups, time_groups = clusters(ids), clusters(paired)
    differences, ratios = [], []
    for _ in range(repetitions):
        if quality_groups:
            sampled = [sid for group in rng.choices(quality_groups,k=len(quality_groups)) for sid in group]
            a = scores(**aggregate_counts([left[sid] for sid in sampled]))["f1"]
            b = scores(**aggregate_counts([right[sid] for sid in sampled]))["f1"]
            differences.append(a-b)
        if time_groups:
            sampled = [sid for group in rng.choices(time_groups,k=len(time_groups)) for sid in group]
            denominator = sum(latencies_right[sid] for sid in sampled)
            if denominator > 0:
                ratios.append(sum(latencies_left[sid] for sid in sampled)/denominator)
    denominator = sum(latencies_right[sid] for sid in paired)
    difference = scores(**aggregate_counts(list(left.values())))["f1"]-scores(**aggregate_counts(list(right.values())))["f1"] if ids else None
    return dict(n_quality=len(ids), n_success_pairs=len(paired), f1_difference=difference,
        f1_difference_ci95=[quantile(differences,.025),quantile(differences,.975)],
        latency_ratio=sum(latencies_left[sid] for sid in paired)/denominator if denominator else None,
        latency_ratio_ci95=[quantile(ratios,.025),quantile(ratios,.975)],
        latency_ratio_reason=None if denominator else "Không có cặp thành công với thời gian dương",
        seed=seed, repetitions=repetitions, resampling="game_cluster" if game_keys else "document")

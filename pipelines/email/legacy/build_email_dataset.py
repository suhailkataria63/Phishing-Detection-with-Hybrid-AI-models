#!/usr/bin/env python3
"""Build a unified email phishing dataset from raw Enron, Nazario, and SpamAssassin sources.

Outputs:
- data/processed/email_dataset_v1.csv
- reports/email_dataset_v1_stats.md

Schema:
- subject
- body
- sender
- sender_domain
- urls (JSON list string)
- label (0=legitimate, 1=suspicious/phishing-like)
- source
"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import html
import json
import os
import random
import re
import sys
import tarfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from email import policy
from email.parser import BytesParser, Parser
from email.utils import parseaddr
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
RAW_DIR = os.path.join(ROOT, "data", "raw")
PROCESSED_DIR = os.path.join(ROOT, "data", "processed")
REPORTS_DIR = os.path.join(ROOT, "reports")

ENRON_CSV = os.path.join(RAW_DIR, "enron", "emails.csv")
NAZARIO_CSV = os.path.join(RAW_DIR, "nazario", "nazario.csv")
SPAMASSASSIN_DIR = os.path.join(RAW_DIR, "spamassassin")

OUT_CSV = os.path.join(PROCESSED_DIR, "email_dataset_v1.csv")
OUT_STATS_MD = os.path.join(REPORTS_DIR, "email_dataset_v1_stats.md")

RANDOM_SEED = 1337
DEFAULT_ENRON_SAMPLE = 1000

# Keeps extraction lightweight and predictable for noisy email text.
URL_RE = re.compile(r"(?i)\b((?:https?://|www\.)[^\s<>\"'()\]]+)")
NUMERIC_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d+)?|\.\d+)$")
TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")


@dataclass
class Record:
    subject: str
    body: str
    sender: str
    sender_domain: str
    urls: List[str]
    label: int
    source: str

    def to_csv_row(self) -> Dict[str, str]:
        return {
            "subject": self.subject,
            "body": self.body,
            "sender": self.sender,
            "sender_domain": self.sender_domain,
            "urls": json.dumps(self.urls, ensure_ascii=False),
            "label": str(self.label),
            "source": self.source,
        }


def safe_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value)
    text = text.replace("\x00", " ")
    text = WHITESPACE_RE.sub(" ", text).strip()
    return text


def cleanup_url(url: str) -> str:
    cleaned = url.strip().strip("\"'`<>{}[]")
    cleaned = cleaned.rstrip(".,;:!?))")
    if cleaned.lower().startswith("www."):
        cleaned = "http://" + cleaned
    return cleaned


def extract_urls(text: str) -> List[str]:
    if not text:
        return []
    out: List[str] = []
    seen = set()
    for match in URL_RE.finditer(text):
        url = cleanup_url(match.group(1))
        if not url or url in seen:
            continue
        seen.add(url)
        out.append(url)
    return out


def decode_payload(payload: Optional[bytes], charset: Optional[str]) -> str:
    if payload is None:
        return ""
    if not isinstance(payload, (bytes, bytearray)):
        return safe_text(payload)

    candidates = [charset, "utf-8", "latin-1"]
    for enc in candidates:
        if not enc:
            continue
        try:
            return payload.decode(enc, errors="replace")
        except LookupError:
            continue
    return payload.decode("utf-8", errors="replace")


def html_to_text(text: str) -> str:
    stripped = TAG_RE.sub(" ", text)
    return safe_text(html.unescape(stripped))


def extract_email_body(message) -> str:
    """Extract readable plain text from email message parts.

    Preference order:
    1) text/plain parts (non-attachments)
    2) text/html parts converted to text
    """
    plain_parts: List[str] = []
    html_parts: List[str] = []

    if message.is_multipart():
        parts = message.walk()
    else:
        parts = [message]

    for part in parts:
        if part.get_content_maintype() == "multipart":
            continue
        content_disposition = (part.get("Content-Disposition") or "").lower()
        if "attachment" in content_disposition:
            continue

        content_type = (part.get_content_type() or "").lower()
        payload = part.get_payload(decode=True)
        charset = part.get_content_charset()
        text = decode_payload(payload, charset)
        if not text:
            continue

        if content_type == "text/plain":
            plain_parts.append(safe_text(text))
        elif content_type == "text/html":
            html_parts.append(html_to_text(text))
        else:
            # For unknown text-ish content types, keep as fallback.
            if content_type.startswith("text/"):
                plain_parts.append(safe_text(text))

    if plain_parts:
        return safe_text("\n".join(p for p in plain_parts if p))
    if html_parts:
        return safe_text("\n".join(p for p in html_parts if p))
    return ""


def extract_sender_domain(sender: str) -> str:
    if not sender:
        return ""
    _, addr = parseaddr(sender)
    candidate = addr or sender
    candidate = candidate.strip().strip("<>").lower()
    if "@" not in candidate:
        return ""
    domain = candidate.rsplit("@", 1)[-1].strip().strip(".")
    if not domain or " " in domain:
        return ""
    return domain


def hash_record_key(subject: str, body: str, sender: str, label: int) -> str:
    material = "\u241f".join(
        [subject.lower(), body.lower(), sender.lower(), str(label)]
    ).encode("utf-8", errors="ignore")
    return hashlib.sha256(material).hexdigest()


def maybe_parse_nazario_urls(raw_urls: str, body: str) -> List[str]:
    """Parse Nazario urls field if it looks like a valid URL list.

    If missing/numeric/malformed, extract from body instead.
    """
    value = safe_text(raw_urls)
    if not value:
        return extract_urls(body)

    if NUMERIC_RE.match(value):
        # Common in this dataset for one class: numeric-like marker, not URL list.
        return extract_urls(body)

    if value.startswith("[") and value.endswith("]"):
        try:
            parsed = ast.literal_eval(value)
            if isinstance(parsed, (list, tuple)):
                urls: List[str] = []
                seen = set()
                for item in parsed:
                    item_text = safe_text(item)
                    if not item_text:
                        continue
                    for url in extract_urls(item_text):
                        if url not in seen:
                            seen.add(url)
                            urls.append(url)
                if urls:
                    return urls
        except Exception:
            pass
        return extract_urls(body)

    # Single URL string or malformed blob; fallback to extraction from combined text.
    return extract_urls(f"{value}\n{body}")


def reservoir_sample_enron_rows(path: str, target_size: int, rng: random.Random) -> List[str]:
    """Reservoir-sample Enron raw message blobs without loading full CSV into memory."""
    reservoir: List[str] = []
    seen = 0

    csv.field_size_limit(sys.maxsize)
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            message_blob = row.get("message", "")
            seen += 1
            if target_size <= 0:
                continue
            if len(reservoir) < target_size:
                reservoir.append(message_blob)
                continue
            j = rng.randint(1, seen)
            if j <= target_size:
                reservoir[j - 1] = message_blob

    return reservoir


def parse_enron_records(path: str, sample_size: int, rng: random.Random) -> List[Record]:
    sampled_blobs = reservoir_sample_enron_rows(path, sample_size, rng)
    records: List[Record] = []

    parser = Parser(policy=policy.default)
    for blob in sampled_blobs:
        try:
            msg = parser.parsestr(blob)
        except Exception:
            continue
        subject = safe_text(msg.get("Subject", ""))
        sender = safe_text(msg.get("From", ""))
        body = extract_email_body(msg)
        urls = extract_urls(body)
        record = Record(
            subject=subject,
            body=body,
            sender=sender,
            sender_domain=extract_sender_domain(sender),
            urls=urls,
            label=0,
            source="enron",
        )
        records.append(record)

    return records


def parse_nazario_records(path: str) -> Tuple[List[Record], Dict[int, List[str]]]:
    records: List[Record] = []
    samples: Dict[int, List[str]] = defaultdict(list)

    csv.field_size_limit(sys.maxsize)
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            subject = safe_text(row.get("subject", ""))
            body = safe_text(row.get("body", ""))
            sender = safe_text(row.get("sender", ""))

            raw_label = safe_text(row.get("label", ""))
            try:
                label = int(float(raw_label))
            except Exception:
                # Skip unusable label rows to keep exported labels consistent.
                continue
            if label not in (0, 1):
                continue

            urls = maybe_parse_nazario_urls(safe_text(row.get("urls", "")), body)

            record = Record(
                subject=subject,
                body=body,
                sender=sender,
                sender_domain=extract_sender_domain(sender),
                urls=urls,
                label=label,
                source="nazario",
            )
            records.append(record)

            if len(samples[label]) < 3:
                snippet = subject or body[:120]
                samples[label].append(safe_text(snippet)[:120])

    return records, samples


def iter_spamassassin_archives(directory: str) -> Iterable[str]:
    for name in sorted(os.listdir(directory)):
        if not name.lower().endswith(".tar.bz2"):
            continue
        yield os.path.join(directory, name)


def archive_sha256(path: str, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def infer_label_from_archive_name(path: str) -> Optional[int]:
    name = os.path.basename(path).lower()
    if "spam" in name:
        return 1
    if "ham" in name:
        return 0
    return None


def parse_spamassassin_records(directory: str) -> Tuple[List[Record], List[str]]:
    records: List[Record] = []
    skipped_duplicates: List[str] = []
    seen_hashes = set()
    parser = BytesParser(policy=policy.default)

    for archive_path in iter_spamassassin_archives(directory):
        digest = archive_sha256(archive_path)
        if digest in seen_hashes:
            skipped_duplicates.append(os.path.basename(archive_path))
            continue
        seen_hashes.add(digest)

        label = infer_label_from_archive_name(archive_path)
        if label is None:
            continue

        with tarfile.open(archive_path, mode="r:bz2") as tar:
            for member in tar:
                if not member.isfile():
                    continue
                extracted = tar.extractfile(member)
                if extracted is None:
                    continue
                try:
                    payload = extracted.read()
                    msg = parser.parsebytes(payload)
                except Exception:
                    continue

                subject = safe_text(msg.get("Subject", ""))
                sender = safe_text(msg.get("From", ""))
                body = extract_email_body(msg)
                urls = extract_urls(body)

                record = Record(
                    subject=subject,
                    body=body,
                    sender=sender,
                    sender_domain=extract_sender_domain(sender),
                    urls=urls,
                    label=label,
                    source="spamassassin",
                )
                records.append(record)

    return records, skipped_duplicates


def deduplicate_records(records: Sequence[Record]) -> Tuple[List[Record], int]:
    deduped: List[Record] = []
    seen = set()

    for record in records:
        key = hash_record_key(record.subject, record.body, record.sender, record.label)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)

    removed = len(records) - len(deduped)
    return deduped, removed


def apply_balancing_controls(
    records: Sequence[Record],
    rng: random.Random,
    max_rows_per_source: Optional[int] = None,
    max_rows_per_source_label: Optional[int] = None,
) -> List[Record]:
    """Apply optional deterministic balancing caps after deduplication."""
    if not max_rows_per_source and not max_rows_per_source_label:
        return list(records)

    shuffled = list(records)
    rng.shuffle(shuffled)

    source_counts: Counter = Counter()
    source_label_counts: Counter = Counter()
    kept: List[Record] = []

    for rec in shuffled:
        if max_rows_per_source is not None and source_counts[rec.source] >= max_rows_per_source:
            continue
        pair = (rec.source, rec.label)
        if (
            max_rows_per_source_label is not None
            and source_label_counts[pair] >= max_rows_per_source_label
        ):
            continue
        kept.append(rec)
        source_counts[rec.source] += 1
        source_label_counts[pair] += 1

    return kept


def write_dataset_csv(path: str, records: Sequence[Record]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fieldnames = [
        "subject",
        "body",
        "sender",
        "sender_domain",
        "urls",
        "label",
        "source",
    ]

    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow(record.to_csv_row())


def make_examples(records: Sequence[Record], limit: int = 5) -> List[Record]:
    return list(records[:limit])


def write_stats_markdown(
    path: str,
    records: Sequence[Record],
    rows_by_source: Counter,
    rows_by_label: Counter,
    rows_by_source_label: Counter,
    dedup_removed: int,
    skipped_archives: Sequence[str],
    nazario_label_samples: Dict[int, List[str]],
    enron_sample_size: int,
    max_rows_per_source: Optional[int],
    max_rows_per_source_label: Optional[int],
) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    examples = make_examples(records, limit=5)

    lines: List[str] = []
    lines.append("# Email Dataset v1 Stats")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- Total rows: **{len(records):,}**")
    lines.append(f"- Deduplicated rows removed: **{dedup_removed:,}**")
    lines.append(f"- Enron sample target: **{enron_sample_size:,}**")
    if max_rows_per_source is not None:
        lines.append(f"- Max rows per source: **{max_rows_per_source:,}**")
    if max_rows_per_source_label is not None:
        lines.append(f"- Max rows per source+label: **{max_rows_per_source_label:,}**")
    lines.append("")

    lines.append("## Rows by Source")
    for source, count in sorted(rows_by_source.items()):
        lines.append(f"- {source}: {count:,}")
    lines.append("")

    lines.append("## Rows by Label")
    for label, count in sorted(rows_by_label.items()):
        lines.append(f"- label={label}: {count:,}")
    lines.append("")

    lines.append("## Rows by Source+Label")
    for (source, label), count in sorted(rows_by_source_label.items()):
        lines.append(f"- source={source}, label={label}: {count:,}")
    lines.append("")

    lines.append("## Nazario Label Polarity Sanity Check")
    lines.append("- Assumption used: `label=1` is suspicious/phishing-like, `label=0` is legitimate.")
    for label in sorted(nazario_label_samples):
        snippets = nazario_label_samples.get(label, [])
        if snippets:
            lines.append(f"- label={label} sample subjects/snippets:")
            for snippet in snippets:
                lines.append(f"  - {snippet}")
    lines.append("")

    lines.append("## Duplicate Archive Handling")
    if skipped_archives:
        lines.append(
            "- Skipped duplicate SpamAssassin archives (same file hash): "
            + ", ".join(skipped_archives)
        )
    else:
        lines.append("- No duplicate SpamAssassin archives detected.")
    lines.append("")

    lines.append("## Parsed Output Examples")
    for idx, rec in enumerate(examples, start=1):
        subject = rec.subject[:80] if rec.subject else ""
        sender = rec.sender[:80] if rec.sender else ""
        body_preview = rec.body[:140] if rec.body else ""
        urls_preview = json.dumps(rec.urls[:3], ensure_ascii=False)
        lines.append(
            f"- Example {idx}: source={rec.source}, label={rec.label}, sender_domain={rec.sender_domain}"
        )
        lines.append(f"  - subject: {subject}")
        lines.append(f"  - sender: {sender}")
        lines.append(f"  - body_preview: {body_preview}")
        lines.append(f"  - urls: {urls_preview}")
    lines.append("")

    lines.append("## Assumptions and Limitations")
    lines.append("- Enron is treated as legitimate (`label=0`) and sampled instead of full ingestion.")
    lines.append(
        "- URL extraction is regex-based and lightweight; hidden links in complex HTML may be missed."
    )
    lines.append(
        "- Sender domain extraction uses header sender field and may be blank on malformed messages."
    )
    lines.append(
        "- SpamAssassin labels are inferred from archive names (`spam` vs `ham`)."
    )
    lines.append(
        "- Cross-source deduplication is content-hash based on subject/body/sender/label."
    )

    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build unified email dataset v1")
    parser.add_argument(
        "--enron-sample-size",
        type=int,
        default=DEFAULT_ENRON_SAMPLE,
        help="How many Enron messages to reservoir-sample",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=RANDOM_SEED,
        help="Random seed for deterministic sampling",
    )
    parser.add_argument(
        "--output-csv",
        type=str,
        default=OUT_CSV,
        help="Output CSV path",
    )
    parser.add_argument(
        "--stats-md",
        type=str,
        default=OUT_STATS_MD,
        help="Output markdown stats path",
    )
    parser.add_argument(
        "--max-rows-per-source",
        type=int,
        default=None,
        help="Optional cap applied to each source after dedup (deterministic with --seed)",
    )
    parser.add_argument(
        "--max-rows-per-source-label",
        type=int,
        default=None,
        help="Optional cap applied to each source+label pair after dedup (deterministic with --seed)",
    )
    args = parser.parse_args()

    rng = random.Random(args.seed)

    missing_inputs = [
        path
        for path in (ENRON_CSV, NAZARIO_CSV, SPAMASSASSIN_DIR)
        if not os.path.exists(path)
    ]
    if missing_inputs:
        missing_text = "\n".join(missing_inputs)
        raise FileNotFoundError(f"Missing required raw inputs:\n{missing_text}")

    enron_records = parse_enron_records(ENRON_CSV, args.enron_sample_size, rng)
    nazario_records, nazario_label_samples = parse_nazario_records(NAZARIO_CSV)
    spam_records, skipped_archives = parse_spamassassin_records(SPAMASSASSIN_DIR)

    all_records = enron_records + nazario_records + spam_records
    deduped_records, dedup_removed = deduplicate_records(all_records)
    balanced_records = apply_balancing_controls(
        deduped_records,
        rng,
        max_rows_per_source=args.max_rows_per_source,
        max_rows_per_source_label=args.max_rows_per_source_label,
    )

    rows_by_source: Counter = Counter(rec.source for rec in balanced_records)
    rows_by_label: Counter = Counter(rec.label for rec in balanced_records)
    rows_by_source_label: Counter = Counter(
        (rec.source, rec.label) for rec in balanced_records
    )

    write_dataset_csv(args.output_csv, balanced_records)
    write_stats_markdown(
        args.stats_md,
        balanced_records,
        rows_by_source,
        rows_by_label,
        rows_by_source_label,
        dedup_removed,
        skipped_archives,
        nazario_label_samples,
        args.enron_sample_size,
        args.max_rows_per_source,
        args.max_rows_per_source_label,
    )

    print(f"Wrote dataset CSV: {args.output_csv}")
    print(f"Wrote stats report: {args.stats_md}")
    print(f"Total rows: {len(balanced_records):,}")
    print(f"Rows by source: {dict(sorted(rows_by_source.items()))}")
    print(f"Rows by label: {dict(sorted(rows_by_label.items()))}")
    print(f"Rows by source+label: {dict(sorted(rows_by_source_label.items()))}")


if __name__ == "__main__":
    main()

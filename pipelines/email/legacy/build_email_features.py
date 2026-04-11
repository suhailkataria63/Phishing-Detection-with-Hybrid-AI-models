#!/usr/bin/env python3

"""
Build enriched email features for phishing detection.

Input:
data/processed/email_dataset_v1.csv

Output:
data/processed/email_dataset_v2_features.csv
"""

import os
import re
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

INPUT_CSV = os.path.join(ROOT, "data", "processed", "email_dataset_v1.csv")
OUTPUT_CSV = os.path.join(ROOT, "data", "processed", "email_dataset_v2_features.csv")


URL_REGEX = r'https?://[^\s]+'


SUSPICIOUS_TLDS = [
".top",".xyz",".click",".gq",".work",".support",".info",".country",
".stream",".download",".review",".racing",".party"
]


SHORTENERS = [
"bit.ly",
"tinyurl",
"goo.gl",
"t.co",
"ow.ly"
]


def extract_urls(text):
    return re.findall(URL_REGEX, text)


def has_ip_url(urls):

    ip_pattern = r'https?://\d+\.\d+\.\d+\.\d+'

    for url in urls:
        if re.search(ip_pattern, url):
            return 1

    return 0


def suspicious_tld_count(urls):

    count = 0

    for url in urls:
        for tld in SUSPICIOUS_TLDS:
            if url.lower().endswith(tld):
                count += 1

    return count


def shortener_count(urls):

    count = 0

    for url in urls:
        for short in SHORTENERS:
            if short in url.lower():
                count += 1

    return count


def url_length_stats(urls):

    if not urls:
        return 0

    lengths = [len(u) for u in urls]

    return sum(lengths) / len(lengths)


def formatting_features(text):

    length = len(text)

    if length == 0:
        return 0,0,0,0

    exclamation_count = text.count("!")

    digit_ratio = sum(c.isdigit() for c in text) / length

    capital_ratio = sum(c.isupper() for c in text) / length

    return exclamation_count, digit_ratio, capital_ratio, length


def main():

    print("Loading dataset...")

    df = pd.read_csv(INPUT_CSV)

    df["subject"] = df["subject"].fillna("")
    df["body"] = df["body"].fillna("")

    df["text"] = (df["subject"] + " " + df["body"]).str.strip()

    url_counts = []
    ip_flags = []
    avg_lengths = []
    suspicious_counts = []
    short_counts = []

    exclamations = []
    digit_ratios = []
    capital_ratios = []
    body_lengths = []

    print("Extracting features...")

    for text in df["text"]:

        urls = extract_urls(text)

        url_counts.append(len(urls))
        ip_flags.append(has_ip_url(urls))
        avg_lengths.append(url_length_stats(urls))
        suspicious_counts.append(suspicious_tld_count(urls))
        short_counts.append(shortener_count(urls))

        exc, dig, cap, length = formatting_features(text)

        exclamations.append(exc)
        digit_ratios.append(dig)
        capital_ratios.append(cap)
        body_lengths.append(length)


    df["url_count"] = url_counts
    df["has_ip_url"] = ip_flags
    df["avg_url_length"] = avg_lengths
    df["suspicious_tld_count"] = suspicious_counts
    df["shortener_count"] = short_counts

    df["exclamation_count"] = exclamations
    df["digit_ratio"] = digit_ratios
    df["capital_ratio"] = capital_ratios
    df["body_length"] = body_lengths


    df.to_csv(OUTPUT_CSV, index=False)

    print("Feature dataset saved to:", OUTPUT_CSV)
    print("Rows:", len(df))


if __name__ == "__main__":
    main()
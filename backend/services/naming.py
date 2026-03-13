"""
Workspace naming via TF-IDF keyword extraction + domain grouping.

Design rationale (from Tabs.do, Chang et al. UIST '21):
- URL/domain features alone achieve 86.4% grouping accuracy
- Semantic features alone: 76.3%
- Combined: 90.8%
TF-IDF on titles + domain clustering covers the dominant signal
without the 2GB PyTorch dependency of sentence-transformers.
"""

import re
from collections import Counter
from urllib.parse import urlparse

from sklearn.feature_extraction.text import TfidfVectorizer

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "has", "have", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "shall", "not", "no", "this", "that",
    "these", "those", "it", "its", "my", "your", "his", "her", "our",
    "their", "what", "which", "who", "whom", "how", "when", "where", "why",
}

WEB_NOISE = {
    "home", "page", "untitled", "new", "tab", "about", "index", "welcome",
    "loading", "search", "results", "google", "chrome", "extension",
    "document", "file", "error", "404", "login", "sign", "account",
}

DOMAIN_DISPLAY = {
    "github.com": "GitHub",
    "scholar.google.com": "Google Scholar",
    "arxiv.org": "arXiv",
    "stackoverflow.com": "Stack Overflow",
    "docs.google.com": "Google Docs",
    "mail.google.com": "Gmail",
    "calendar.google.com": "Google Calendar",
    "youtube.com": "YouTube",
    "reddit.com": "Reddit",
    "twitter.com": "Twitter",
    "x.com": "Twitter",
    "notion.so": "Notion",
    "figma.com": "Figma",
    "overleaf.com": "Overleaf",
    "semanticscholar.org": "Semantic Scholar",
    "medium.com": "Medium",
    "substack.com": "Substack",
    "wikipedia.org": "Wikipedia",
}


def _extract_domain(url: str) -> str:
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


def _clean_title(title: str) -> str:
    # Remove common suffixes like " - Google Search", " | Medium"
    title = re.sub(r"\s*[\-\|·]\s*[^-|·]{1,30}$", "", title)
    return title.strip()


def suggest_name(titles: list[str], urls: list[str] | None = None) -> str:
    if not titles:
        return "Untitled"

    # Filter empty/noise titles
    clean_titles = [_clean_title(t) for t in titles if t]
    clean_titles = [t for t in clean_titles if t.lower() not in WEB_NOISE]

    if not clean_titles:
        return "Untitled"

    # Strategy 1: Domain dominance
    if urls:
        domains = [_extract_domain(u) for u in urls]
        domain_counts = Counter(d for d in domains if d)
        if domain_counts:
            top_domain, top_count = domain_counts.most_common(1)[0]
            total = len(domains)
            # If >60% of tabs share a domain, use domain name
            if top_count / total > 0.6:
                display = DOMAIN_DISPLAY.get(top_domain)
                if display:
                    # Add a keyword qualifier if we have mixed content
                    keywords = _tfidf_keywords(clean_titles, n=1)
                    if keywords:
                        return f"{display}: {keywords[0]}"
                    return display
                # Use the domain itself, titlecased
                name = top_domain.split(".")[0].title()
                keywords = _tfidf_keywords(clean_titles, n=1)
                if keywords:
                    return f"{name}: {keywords[0]}"
                return name

    # Strategy 2: TF-IDF keyword extraction
    keywords = _tfidf_keywords(clean_titles, n=3)
    if keywords:
        return " & ".join(keywords[:2]) if len(keywords) >= 2 else keywords[0]

    # Fallback: first meaningful title, truncated
    return clean_titles[0][:40]


def _tfidf_keywords(titles: list[str], n: int = 3) -> list[str]:
    if not titles:
        return []

    all_stop = STOPWORDS | WEB_NOISE
    joined = " ".join(titles)
    words = re.findall(r"[a-zA-Z]{3,}", joined.lower())
    meaningful = [w for w in words if w not in all_stop]

    if not meaningful:
        return []

    if len(titles) < 2:
        # Not enough documents for TF-IDF, use frequency
        counts = Counter(meaningful)
        return [word.title() for word, _ in counts.most_common(n)]

    try:
        vectorizer = TfidfVectorizer(
            stop_words=list(all_stop),
            max_features=50,
            token_pattern=r"[a-zA-Z]{3,}",
        )
        tfidf_matrix = vectorizer.fit_transform(titles)
        feature_names = vectorizer.get_feature_names_out()

        # Sum TF-IDF scores across documents
        scores = tfidf_matrix.sum(axis=0).A1
        top_indices = scores.argsort()[-n:][::-1]
        return [feature_names[i].title() for i in top_indices if scores[i] > 0]
    except ValueError:
        # TF-IDF failed (empty vocabulary after stop words)
        counts = Counter(meaningful)
        return [word.title() for word, _ in counts.most_common(n)]

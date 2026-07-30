"""
Track normalization utilities
"""
import re
from dataclasses import dataclass
from typing import Optional, List


@dataclass
class ParsedTrack:
    """Parsed track components"""
    raw_input: str
    artist: Optional[str] = None
    title: Optional[str] = None
    context: Optional[str] = None
    parse_confidence: str = 'low'  # low, medium, high


def normalize_string(text: str) -> str:
    """Normalize string for matching"""
    if not text:
        return ""

    # Lowercase
    text = text.lower()

    # Normalize dash types
    text = text.replace('—', '-').replace('–', '-').replace('−', '-')

    # Remove quotes
    text = text.replace('"', '').replace('"', '').replace('"', '')
    text = text.replace("'", '').replace("'", '').replace("'", '')

    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text)

    # Strip
    text = text.strip()

    return text


def preprocess_input(raw: str) -> str:
    """Preprocess raw input before parsing"""
    # Keep original for reference
    text = raw.strip()

    # Remove file extensions
    text = re.sub(r'\.(mp3|flac|wav|m4a|ogg)$', '', text, flags=re.IGNORECASE)

    # Remove junk tokens
    junk_patterns = [
        r'\bofficial video\b',
        r'\blyrics?\b',
        r'\bHD\b',
        r'\baudio\b',
        r'\bofficial audio\b',
    ]
    for pattern in junk_patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)

    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    return text


def parse_track(raw_input: str) -> ParsedTrack:
    """Parse track into artist/title components"""
    preprocessed = preprocess_input(raw_input)

    # Try splitting on common separators
    separators = [' - ', ' : ', ' | ']

    for sep in separators:
        if sep in preprocessed:
            parts = preprocessed.split(sep, 1)
            if len(parts) == 2:
                artist = parts[0].strip()
                title = parts[1].strip()

                # Handle multiple featured artists in artist field
                # If artist contains multiple "/" separated names, take first as primary
                if '/' in artist:
                    # Check if this is multiple artists or a single artist name with /
                    # Count slashes - if more than 2, likely multiple artists
                    slash_count = artist.count('/')
                    if slash_count > 2:
                        # Multiple artists: "HUNTR/X/EJAE/AUDREY NUNA/REI AMI"
                        # Take first two parts if they're short (likely band name): "HUNTR/X"
                        parts = artist.split('/')
                        if len(parts[0]) < 10 and len(parts[1]) < 10:
                            # Short parts - likely "HUNTR/X" is the band name
                            artist = f"{parts[0]}/{parts[1]}".strip()
                        else:
                            # Long first part - just take it
                            artist = parts[0].strip()

                # Extract context from title
                title, context = extract_context(title)

                confidence = 'high' if sep == ' - ' else 'medium'

                return ParsedTrack(
                    raw_input=raw_input,
                    artist=artist,
                    title=title,
                    context=context,
                    parse_confidence=confidence
                )

    # No separator found - treat entire string as title
    title, context = extract_context(preprocessed)

    return ParsedTrack(
        raw_input=raw_input,
        artist=None,
        title=title,
        context=context,
        parse_confidence='low'
    )


def extract_context(title: str) -> tuple[str, Optional[str]]:
    """Extract contextual noise from title"""
    # Only use explicit context indicators
    # Let candidate generation handle ambiguous cases
    context_patterns = [
        (r'\s+from\s+(?:the\s+)?(?:netflix\s+)?(?:film|movie|series|show)\s+(.+)$', True),
        (r'\s+(?:original\s+)?(?:motion\s+picture\s+)?soundtrack$', False),
        (r'\s+feat(?:uring)?\.?\s+(.+)$', False),
        (r'\s+ft\.?\s+(.+)$', False),
    ]

    original_title = title
    extracted_context = None

    for pattern, capture_context in context_patterns:
        match = re.search(pattern, title, re.IGNORECASE)
        if match:
            if capture_context:
                extracted_context = match.group(1).strip()
            title = title[:match.start()].strip()
            break

    return title, extracted_context


def generate_search_candidates(parsed: ParsedTrack) -> List[dict]:
    """Generate search query candidates"""
    candidates = []

    if parsed.artist and parsed.title:
        # Primary: full artist + title
        candidates.append({
            'artist': parsed.artist,
            'title': parsed.title,
            'priority': 1
        })

        # Try with different title splits (in case context extraction was wrong)
        # For "What It Sounds Like KPop Demon Hunters", try:
        # - "What It Sounds Like" (remove last 3 words)
        # - "What It Sounds" (remove last 4 words)
        title_words = parsed.title.split()
        if len(title_words) > 3:
            # Try removing last 2-4 words
            for i in range(2, min(5, len(title_words))):
                shorter_title = ' '.join(title_words[:-i])
                if len(shorter_title) > 5:  # Minimum reasonable title length
                    candidates.append({
                        'artist': parsed.artist,
                        'title': shorter_title,
                        'priority': 2
                    })

        # With context if available
        if parsed.context:
            candidates.append({
                'artist': parsed.artist,
                'title': f"{parsed.title} {parsed.context}",
                'priority': 3
            })

        # Artist variants (handle special characters)
        artist_variants = generate_artist_variants(parsed.artist)
        for variant in artist_variants:
            if variant != parsed.artist:
                candidates.append({
                    'artist': variant,
                    'title': parsed.title,
                    'priority': 4
                })

    # Title-only fallback
    if parsed.title:
        candidates.append({
            'artist': None,
            'title': parsed.title,
            'priority': 5
        })

    # Whole string fallback
    candidates.append({
        'artist': None,
        'title': parsed.raw_input,
        'priority': 6
    })

    return candidates


def generate_artist_variants(artist: str) -> List[str]:
    """Generate artist name variants for fuzzy matching"""
    variants = [artist]

    # Remove/add slashes
    if '/' in artist:
        variants.append(artist.replace('/', ''))
    else:
        # Try adding slash in common positions
        if len(artist) > 3:
            for i in range(1, len(artist)):
                variants.append(artist[:i] + '/' + artist[i:])

    # Remove punctuation
    no_punct = re.sub(r'[^\w\s]', '', artist)
    if no_punct != artist:
        variants.append(no_punct)

    return list(set(variants))[:5]  # Limit to 5 variants


def calculate_string_similarity(s1: str, s2: str) -> float:
    """Calculate normalized similarity between two strings (0.0 to 1.0)"""
    if not s1 or not s2:
        return 0.0

    # Normalize both strings
    s1 = normalize_string(s1)
    s2 = normalize_string(s2)

    if s1 == s2:
        return 1.0

    # Simple Levenshtein-like similarity
    # For production, consider using python-Levenshtein or difflib
    from difflib import SequenceMatcher
    return SequenceMatcher(None, s1, s2).ratio()


def score_artist_match(input_artist: str, candidate_artist: str) -> float:
    """Score artist match (0.0 to 1.0)"""
    if not input_artist or not candidate_artist:
        return 0.0

    # Exact match
    if input_artist.lower() == candidate_artist.lower():
        return 1.0

    # Normalized match
    norm_input = normalize_string(input_artist)
    norm_candidate = normalize_string(candidate_artist)

    if norm_input == norm_candidate:
        return 0.95

    # Check if candidate is in variants
    variants = generate_artist_variants(input_artist)
    for variant in variants:
        if normalize_string(variant) == norm_candidate:
            return 0.90

    # Fuzzy similarity
    similarity = calculate_string_similarity(input_artist, candidate_artist)

    # High threshold for typos - be generous to catch common typos
    if similarity > 0.90:
        return 0.95  # Very high similarity, treat almost as exact match
    elif similarity > 0.85:
        return 0.90  # High similarity, likely a typo (e.g., HUNTRIX → HUNTR/X)
    elif similarity > 0.80:
        return 0.85  # Good similarity, possible typo
    elif similarity > 0.75:
        return similarity * 0.85
    else:
        return similarity * 0.5


def score_title_match(input_title: str, candidate_title: str, context: Optional[str] = None) -> float:
    """Score title match (0.0 to 1.0)"""
    if not input_title or not candidate_title:
        return 0.0

    # Exact match
    if input_title.lower() == candidate_title.lower():
        return 1.0

    # Normalized match
    norm_input = normalize_string(input_title)
    norm_candidate = normalize_string(candidate_title)

    if norm_input == norm_candidate:
        return 0.95

    # Check without context
    if context:
        title_without_context = input_title.replace(context, '').strip()
        if normalize_string(title_without_context) == norm_candidate:
            return 0.92

    # Remove common qualifiers and try again
    qualifiers = [r'\s*\([^)]*\)\s*$', r'\s*\[[^\]]*\]\s*$']
    for pattern in qualifiers:
        stripped_input = re.sub(pattern, '', input_title).strip()
        stripped_candidate = re.sub(pattern, '', candidate_title).strip()
        if normalize_string(stripped_input) == normalize_string(stripped_candidate):
            return 0.88

    # Fuzzy similarity
    similarity = calculate_string_similarity(input_title, candidate_title)

    # High threshold for typos
    if similarity > 0.85:
        return similarity * 0.85

    return similarity * 0.5

import requests
import re
from collections import Counter
import time

# "4.12.3"
from bs4 import BeautifulSoup #TODO: use built-ins, overkill for current html parsing task


def apply_percentile_threshold(word_frequency, percentile):
    """
    Filters words based on a percentile threshold for frequency.

    >>> apply_percentile_threshold({'python': (50, 43.47826086956522), 'programming': (30, 26.08695652173913), 'language': (25, 21.73913043478261), 'code': (10, 8.695652173913043)}, 25)
    {'python': (50, 43.47826086956522), 'programming': (30, 26.08695652173913)}
    """
    return {word: (count, perc) for word, (count, perc) in word_frequency.items() if perc >= percentile}

def get_word_frequency(text):
    """
    Given a text string, returns a dictionary of word frequencies.

    >>> get_word_frequency("Python is great! Python is fun.")
    Counter({'python': 2, 'is': 2, 'great': 1, 'fun': 1})
    >>> get_word_frequency("Hello world")
    Counter({'hello': 1, 'world': 1})
    >>> get_word_frequency("")
    Counter()
    """
    # Remove non-alphabetic characters (i.e., leave only words)
    words = re.findall(r'\b[a-zA-Z]+\b', text.lower())
    word_count = Counter(words)
    return word_count

def normalize_word_frequency(word_frequency):
    """
    Given a Counter of word frequencies, normalizes the counts as percentages.

    >>> res = normalize_word_frequency(Counter({'python': 50, 'programming': 30, 'language': 25, 'code': 10}))
    >>> res
    {'python': (50, 43.47826086956522), 'programming': (30, 26.08695652173913), 'language': (25, 21.73913043478261), 'code': (10, 8.695652173913043)}
    >>> round(sum(frequency_perc for _, frequency_perc in res.values()), 6) # validate sum, summing order does not matter due to small sample size
    100.0
    >>> normalize_word_frequency(Counter({'apple': 1, 'orange': 1}))
    {'apple': (1, 50.0), 'orange': (1, 50.0)}
    >>> normalize_word_frequency(Counter())
    {}
    """
    total_count = word_frequency.total()
    return {word: (count, (count / total_count) * 100) for word, count in word_frequency.items()}

def fetch_wikipedia_page(article):
    """
    Given a Wikipedia article title, fetches the page and extracts links and text.

    >>> text, links = fetch_wikipedia_page("Python_(programming_language)")
    >>> isinstance(text, str)
    True
    >>> isinstance(links, list)
    True
    >>> len(links) > 0
    True
    >>> fetch_wikipedia_page("NonExistentArticle")  # This should return None, None
    (None, None)
    """
    wiki_url = f'https://en.wikipedia.org/wiki/{article}'
    response = requests.get(wiki_url)

    if response.status_code != 200:
        return None, None  # In case the article doesn't exist or there's an error

    soup = BeautifulSoup(response.text, 'html.parser')
    text = soup.get_text()

    # Extract all valid links within the article
    links = [a['href'][6:] for a in soup.find_all('a', href=True) if a['href'].startswith('/wiki/')]

    # Filter internal links that are special articles (e.g. File:|Special:|Category:|Help:|Portal:|Wikipedia:|Talk:|Template_talk:)
    invalid_link_pattern = re.compile(r'^[A-Z][a-z_]*:')
    links = [link for link in links if not invalid_link_pattern.match(link)]

    return text, links

def crawl_wikipedia_article(article, depth, visited, word_frequency):
    """
    Recursively crawls a Wikipedia article and updates word frequencies. This function uses mockable
    `fetch_wikipedia_page` to fetch article content and links.

    >>> from unittest.mock import patch
    >>> word_freq = Counter()
    >>> visited = set()
    >>> with patch('__main__.fetch_wikipedia_page', side_effect=[
    ...     ("This is Python content.", ['Python_(programming_language)', 'List_of_programming_languages']),
    ...     ("This is List of programming languages content.", ['Programming_language', 'Python_(programming_language)'])
    ...     ]):
    ...     crawl_wikipedia_article('Python_(programming_language)', 2, visited, word_freq)
    ...     sorted(visited) # do not rely on unordered set, which may yield false positive test failure
    ...     word_freq
    ['List_of_programming_languages', 'Python_(programming_language)']
    Counter({'this': 2, 'is': 2, 'content': 2, 'python': 1, 'list': 1, 'of': 1, 'programming': 1, 'languages': 1})
    """
    if depth == 0:
        return

    # Avoid revisiting the same article
    if article in visited:
        return

    visited.add(article)

    # Logging
    print(f"Fetching: {article} (Depth {depth})")

    # Fetch the article and extract text and links
    text, links = fetch_wikipedia_page(article)
    if text is None:
        return  # Skip if the article doesn't exist

    # Get word frequencies for this page and update the overall frequency
    page_word_frequency = get_word_frequency(text)
    word_frequency.update(page_word_frequency)

    # Recursively crawl the linked articles (depth-first traversal)
    for link in links:
        # Avoid going back to the same article if it was already visited
        if link not in visited:
            crawl_wikipedia_article(link, depth - 1, visited, word_frequency)

    # Respect rate limits (Wikipedia requests may be rate-limited)
    #time.sleep(.1)  # Sleep between requests to avoid overloading the server


if __name__ == "__main__":
    import doctest

    doctest.testmod()

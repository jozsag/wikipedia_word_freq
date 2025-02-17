import http.server
import json
import urllib.parse
from collections import Counter

from word_frequency_count import crawl_wikipedia_article, normalize_word_frequency, apply_percentile_threshold


class WordCountRequestHandler(http.server.BaseHTTPRequestHandler):
    #TODO: missing features
    # - server response (esp. for increasing depth) speed up by
    #   - parallel network operations for article page loading, ideas
    #       - ThreadPoolExecutor workers (threads are suitable, problem is I/O bound), number of workers?
    #       - race condition on visited articles (old-school lock should be a good start)
    #       - word frequency aggregation alternatives
    #           - thread-local variable: seems convenient, but how to fetch thread-aggregated data from each worker after all articles are visited? smells like it'd require workaround
    #           - returned directly from article processing task: thread coordinator?
    #        - learn parallel graph traversal algorithms
    #   - cache management (neglecting article html content update use case)
    # - abort server side processing if connection is lost (socket polling?)
    # - robustness: error handling of user inputs (e.g. non-integer or negative depth), strong typing, etc.

    def do_GET(self):
        try:
            # Parse the URL and extract query parameters
            parsed_url = urllib.parse.urlparse(self.path)
            query_params = urllib.parse.parse_qs(parsed_url.query)

            # Get the 'title' and 'depth' parameters from the query string
            article = query_params.get('title', [None])[0]
            depth = int(query_params.get('depth', [1])[0])

            if article:
                visited = set() # O(1) lookup, no burden w/ exponentially growing article visits on increasing depth
                word_frequency = Counter()

                # Start crawling Wikipedia
                crawl_wikipedia_article(article, depth, visited, word_frequency)

                # Send the word frequency as a response
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()

                # Respond with the word frequency in JSON format
                normalized_word_frequency = normalize_word_frequency(word_frequency)
                self.wfile.write(str(normalized_word_frequency).encode())
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Error: Please provide a 'title' query parameter.")
        except Exception as e:
            print(f"Error: {e}")
            self.send_error(500, "Internal Server Error")

    def do_POST(self):
        try:
            # Extract the content-length and parse the body
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)

            # Parse the JSON data
            data = json.loads(post_data)

            # Extract 'article', 'depth', 'ignore_list', and 'percentile' from the POST data
            article = data.get('article')
            depth = data.get('depth', 1)  # Default depth is 1 if not provided
            ignore_list = data.get('ignore_list', [])
            percentile = data.get('percentile', 1)  # Default percentile is 1 if not provided

            # Validate that the article is provided
            if not article:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Article title is required"}).encode('utf-8'))
                return

            # Initialize variables
            visited = set()
            word_frequency = Counter()

            # Crawl the Wikipedia article and its linked pages
            crawl_wikipedia_article(article, depth, visited, word_frequency)

            # Filter out words in the (lowercased) ignore_list
            ignore_list = [ignore_word.lower() for ignore_word in ignore_list]
            for ignore_word in ignore_list:
                if ignore_word in word_frequency:
                    del word_frequency[ignore_word]

            # Normalize word count with total count (as percentage)
            normalized_filtered_word_frequency = normalize_word_frequency(word_frequency)

            # Apply the percentile threshold filter
            perc_limited_filtered_word_frequency = apply_percentile_threshold(normalized_filtered_word_frequency, percentile)

            # Sort the dictionary based on decreasing word count value (most popular words first)
            word_count_getter = lambda item: item[1][0]
            sorted_filtered_word_frequency = dict(sorted(perc_limited_filtered_word_frequency.items(),
                                                         key=word_count_getter,
                                                         reverse=True))

            # Prepare the response as JSON
            response = {"word_frequency": sorted_filtered_word_frequency}

            # Send response back as JSON
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode('utf-8'))
        except Exception as e:
            print(f"Error: {e}")
            self.send_error(500, "Internal Server Error")

# Create a localhost server and handle requests
def run(server_class=http.server.ThreadingHTTPServer, handler_class=WordCountRequestHandler, port=8080):
    server_address = ('localhost', port)
    httpd = server_class(server_address, handler_class)
    print(f'Serving on http://localhost:{port}...')
    httpd.serve_forever()

if __name__ == "__main__":
    # TODO: argparse
    run(port=8181)

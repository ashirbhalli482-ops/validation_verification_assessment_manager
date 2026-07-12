import re


class PartialNavMiddleware:
    """Mark partial-nav requests and return only #app-main HTML (smaller, faster)."""

    _MAIN_RE = re.compile(
        r'(<main\b[^>]*\bid=["\']app-main["\'][^>]*>.*?</main>)',
        re.DOTALL | re.IGNORECASE,
    )
    _TITLE_RE = re.compile(r'<title>(.*?)</title>', re.DOTALL | re.IGNORECASE)

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.partial_nav = request.headers.get('X-Partial-Nav') == '1'
        response = self.get_response(request)
        if not request.partial_nav:
            return response
        content_type = response.get('Content-Type', '')
        if response.status_code != 200 or 'text/html' not in content_type:
            return response
        charset = getattr(response, 'charset', None) or 'utf-8'
        try:
            html = response.content.decode(charset)
        except (UnicodeDecodeError, AttributeError):
            return response
        match = self._MAIN_RE.search(html)
        if not match:
            return response
        fragment = match.group(1)
        title_match = self._TITLE_RE.search(html)
        if title_match:
            title = title_match.group(1).strip()
            fragment = f'<!-- partial-title:{title} -->\n{fragment}'
        response.content = fragment.encode(charset)
        if 'Content-Length' in response:
            del response['Content-Length']
        return response

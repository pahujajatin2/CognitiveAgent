try:
    from duckduckgo_search import DDGS
except ImportError:
    class DDGS:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def text(self, *args, **kwargs):
            return []

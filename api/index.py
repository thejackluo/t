#!/usr/bin/env python3
"""Vercel WSGI entrypoint for the route studio."""
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlencode

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.rail_schedule.itinerary import RailNetwork
from frontend.map_editor.server import wsgi_application

network = RailNetwork()
wsgi = wsgi_application(network)


def application(environ, start_response):
    """Restore the original API path captured by the vercel.json rewrite."""
    query = parse_qs(environ.get('QUERY_STRING', ''), keep_blank_values=True)
    original = query.pop('__path', None)
    if original is not None:
        environ['PATH_INFO'] = '/api/' + original[0].lstrip('/')
        environ['QUERY_STRING'] = urlencode(query, doseq=True)
    return wsgi(environ, start_response)

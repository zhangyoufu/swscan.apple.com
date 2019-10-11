#!/usr/bin/env python3
import datetime
import gzip
import http.cookiejar
import logging
import pathlib
import plistlib
import requests
import urllib.parse
import wsgiref.handlers

cookie_policy = http.cookiejar.DefaultCookiePolicy()
cookie_policy.set_ok = lambda cookie, request: False
session = requests.Session()
session.cookies.set_policy(cookie_policy)

def main():
    logging.basicConfig(
        level=logging.INFO,
        format='[%(levelname)s] %(message)s',
    )
    process_all()

def process_all():
    for line in open('url.txt'):
        ## skip comment line
        if line.startswith('#'): continue

        ## skip empty line
        if line == '\n': continue

        url = line.rstrip('\n')
        logging.info('URL: %s', url)
        try:
            process_one(url)
        except Exception:
            logging.exception('unhandled exception')

def process_one(url):
    path = urllib.parse.urlsplit(url)[2].lstrip('/')
    assert path
    path = pathlib.Path(pathlib.PurePosixPath(path))

    try:
        last_modified = parse_index_date(path)
    except Exception:
        last_modified = None
    else:
        last_modified += datetime.timedelta(seconds=5)

    rsp = session.get(url + '.gz', allow_redirects=False, headers={
        'If-Modified-Since': get_http_date(last_modified),
    })
    status = f'{rsp.status_code} {rsp.reason}'

    if rsp.status_code == 200:
        logging.info(status)
        data = gzip.decompress(rsp.content)

        if len(path.parts) > 1:
            path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        with open(path, 'wb') as f:
            f.write(data)
    elif rsp.status_code == 304:
        logging.info(status)
    elif rsp.status_code == 404:
        logging.warning(status)
        if path.exists():
            path.unlink()
    else:
        logging.error(status)

def parse_index_date(path):
    with open(path, 'rb') as f:
        catalog = plistlib.load(f)
    return catalog['IndexDate'].replace(tzinfo=datetime.timezone.utc)

def get_http_date(dt):
    if dt is None:
        return
    return wsgiref.handlers.format_date_time(dt.timestamp())

if __name__ == '__main__':
    main()

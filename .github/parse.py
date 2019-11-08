#!/usr/bin/env python3
import json
import logging
import os
import plistlib
import re
import requests
import subprocess
import sys
import tempfile

def parse_catalog(path):
    with open(path, 'rb') as f:
        catalog = plistlib.load(f)

    assert catalog.pop('CatalogVersion') == 2
    catalog.pop('ApplePostURL')
    catalog.pop('IndexDate')
    products = catalog.pop('Products')
    assert not catalog

    for product_id, product in products.items():
        if 'ExtendedMetaInfo' not in product:
            continue
        post_date = product.pop('PostDate').isoformat() + 'Z'
        distributions = product.pop('Distributions')
        packages = product.pop('Packages')
        server_metadata_url = product.pop('ServerMetadataURL', None)
        extended_meta_info = product.pop('ExtendedMetaInfo')
        product.pop('State', None) # State: ramped
        assert not product

        if 'InstallAssistantPackageIdentifiers' not in extended_meta_info:
            continue
        ia_package_identifiers = extended_meta_info.pop('InstallAssistantPackageIdentifiers')
        assert not extended_meta_info

        assert ia_package_identifiers.pop('InstallInfo') == 'com.apple.plist.InstallInfo'
        ia_package_identifiers.pop('OSInstall', None)
        assert not ia_package_identifiers

        identifier = re.search(r'/content/downloads/\d{2}/\d{2}/[^/]*?/([0-9a-z]{34})/', server_metadata_url).group(1)

        yield {
            'Identifier': identifier,
            'PostDate': post_date,
            'DistributionURL': distributions['English'],
            'Packages': packages,
        }

def get_branches(repo, token=None):
    branches = set()
    headers = {'Authorization': f'token {token}'} if token else None
    url = f'https://api.github.com/repos/{repo}/branches'
    while 1:
        rsp = requests.get(url=url, headers=headers, allow_redirects=False)
        assert rsp.status_code == 200
        branches.update(item['name'] for item in rsp.json())
        if 'next' not in rsp.links:
            break
        url = rsp.links['next']['url']
    return branches

def new_branch(item):
    _id = item.pop('Identifier')
    logging.info(f'Processing {_id}...')
    subprocess.run(['git', 'checkout', 'master'], check=True)
    subprocess.run(['git', 'switch', '-c', _id], check=True)
    with open('product.json', 'w') as f:
        json.dump(item, f, indent=2)
    subprocess.run(['git', 'add', '--force', 'product.json'], check=True)
    subprocess.run(['git', 'commit', '--message', 'automatic commit'], check=True)
    subprocess.run(['git', 'push', 'origin', _id], check=True)

def main():
    repo = 'zhangyoufu/macOS'
    token = os.environ['GITHUB_PERSONAL_ACCESS_TOKEN']

    logging.basicConfig(
        level=logging.INFO,
        format='[%(levelname)s] %(message)s',
    )

    # accept a file list separated by NUL from stdin
    file_list = sys.stdin.detach().detach().readall().rstrip(b'\0').split(b'\0')

    # parse catalog indexes, filter out known builds
    todo = []
    logging.info('Getting list of branches...')
    branches = get_branches(repo=repo, token=token)
    for path in file_list:
        for item in parse_catalog(path):
            _id = item['Identifier']
            if _id not in branches:
                todo.append(item)
                branches.add(_id)

    if not todo:
        return

    tmpdir = tempfile.TemporaryDirectory()
    try:
        os.chdir(tmpdir.name)
        subprocess.run(['git', 'clone', '--depth', '1', f'https://{token}@github.com/{repo}.git', '.'], check=True)
        for item in todo:
            new_branch(item)
    finally:
        tmpdir.cleanup()

if __name__ == '__main__':
    main()

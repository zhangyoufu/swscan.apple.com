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

    if catalog == {}:
        return [], []

    assert catalog.pop('CatalogVersion') == 2
    catalog.pop('ApplePostURL')
    catalog.pop('IndexDate')
    products = catalog.pop('Products')
    assert not catalog

    macOS = []
    bridgeOS = []

    for product_id, product in products.items():
        if 'ExtendedMetaInfo' not in product:
            continue
        post_date = product.pop('PostDate').isoformat() + 'Z'
        distributions = product.pop('Distributions')
        packages = product.pop('Packages')
        extended_meta_info = product.pop('ExtendedMetaInfo')
        product.pop('DeferredSUEnablementDate', None) # DeferredSUEnablementDate: 2020-03-24T07:00:00Z
        product.pop('ServerMetadataURL', None) # not available for macOS1016Seed1
        product.pop('State', None) # State: ramped
        assert not product, product

        distribution_url = distributions['English']
        identifier = re.search(r'/content/downloads/\d{2}/\d{2}/[^/]*?/([0-9a-z]{34})/', distribution_url).group(1)

        if 'InstallAssistantPackageIdentifiers' in extended_meta_info:
            ia_package_identifiers = extended_meta_info.pop('InstallAssistantPackageIdentifiers')
            assert not extended_meta_info

            assert ia_package_identifiers.pop('InstallInfo') == 'com.apple.plist.InstallInfo'
            ia_package_identifiers.pop('OSInstall', None)
            ia_package_identifiers.pop('SharedSupport', None) # com.apple.pkg.InstallAssistant.Seed.macOS1016Seed1
            ia_package_identifiers.pop('Info', None) # com.apple.plist.Info
            ia_package_identifiers.pop('UpdateBrain', None) # com.apple.zip.UpdateBrain
            ia_package_identifiers.pop('BuildManifest', None) # com.apple.plist.BuildManifest
            assert not ia_package_identifiers

            macOS.append({
                'Identifier': identifier,
                'PostDate': post_date,
                'DistributionURL': distribution_url,
                'Packages': packages,
            })
        elif 'ProductType' in extended_meta_info:
            product_type = extended_meta_info.pop('ProductType')
            if product_type == 'macOS':
                extended_meta_info.pop('AutoUpdate', None)
                extended_meta_info.pop('ProductVersion')
                assert not extended_meta_info

                macOS.append({
                    'Identifier': identifier,
                    'PostDate': post_date,
                    'DistributionURL': distribution_url,
                    'Packages': packages,
                })
            elif product_type == 'bridgeOS':
                version = extended_meta_info.pop('BridgeOSPredicateProductOrdering')
                extended_meta_info.pop('BridgeOSSoftwareUpdateEventRecordingServiceURL')
                extended_meta_info.pop('ProductVersion')
                assert not extended_meta_info

                bridgeOS.append({
                    'Version': version,
                    'Identifier': identifier,
                    'PostDate': post_date,
                    'Packages': packages,
                })
            else:
                raise NotImplementedError(f'unknown ProductType {product_type}')
    return macOS, bridgeOS


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
    subprocess.run(['git', 'checkout', 'template'], check=True)
    subprocess.run(['git', 'switch', '-c', _id], check=True)
    with open('product.json', 'w') as f:
        json.dump(item, f, indent=2)
    subprocess.run(['git', 'add', '--force', 'product.json'], check=True)
    subprocess.run(['git', 'commit', '--message', 'automatic commit'], check=True)
    subprocess.run(['git', 'push', 'origin', _id], check=True)

def main():
    token = os.environ['GITHUB_PERSONAL_ACCESS_TOKEN']

    logging.basicConfig(
        level=logging.INFO,
        format='[%(levelname)s] %(message)s',
    )

    # accept a file list separated by NUL from stdin
    file_list = sys.stdin.detach().detach().readall().rstrip(b'\0').split(b'\0')

    logging.info('Getting list of branches...')
    branches  = get_branches(repo='zhangyoufu/macOS', token=token)
    branches |= get_branches(repo='zhangyoufu/bridgeOS', token=token)

    # parse catalog indexes, filter out known builds
    macOS = []
    bridgeOS = []
    for path in file_list:
        logging.info(f'Parsing {path}')
        _macOS, _bridgeOS = parse_catalog(path)
        for item in _macOS:
            _id = item['Identifier']
            if _id not in branches:
                macOS.append(item)
                branches.add(_id)
        for item in _bridgeOS:
            _id = item['Identifier']
            if _id not in branches:
                bridgeOS.append(item)
                branches.add(_id)

    if macOS:
        tmpdir = tempfile.TemporaryDirectory()
        try:
            os.chdir(tmpdir.name)
            subprocess.run(['git', 'clone', '--branch', 'template', '--depth', '1', f'https://{token}@github.com/zhangyoufu/macOS.git', '.'], check=True)
            for item in macOS:
                new_branch(item)
        finally:
            tmpdir.cleanup()

    if bridgeOS:
        tmpdir = tempfile.TemporaryDirectory()
        try:
            os.chdir(tmpdir.name)
            subprocess.run(['git', 'clone', '--branch', 'template', '--depth', '1', f'https://{token}@github.com/zhangyoufu/bridgeOS.git', '.'], check=True)
            for item in bridgeOS:
                new_branch(item)
        finally:
            tmpdir.cleanup()

if __name__ == '__main__':
    main()

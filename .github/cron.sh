#!/bin/bash
set -ex

pip3 install -r requirements.txt
./crawl.py

if [ -n "$(git status --porcelain)" ]; then
	git add --all
	git config user.name 'GitHub Actions'
	git commit --all --message 'automatic commit'
	git push "https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git" HEAD:master
fi

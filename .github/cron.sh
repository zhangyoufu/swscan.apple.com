#!/bin/bash
set -ex
set -o pipefail

pip3 install -r requirements.txt
./crawl.py

if [ -n "$(git status --porcelain)" ]; then
	git config --global user.name 'GitHub Actions'
	git config --global user.email "$(whoami)@$(hostname --fqdn)"
	git add --all
	git diff --cached --diff-filter=AM --name-only -z | ./parse.py
	git commit --all --message 'automatic commit'
	git push "https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git" HEAD:master
fi

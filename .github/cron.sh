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
	if [ "$(git log -1 --pretty=format:%B)" = "automatic commit" ]; then
		git commit --amend --no-edit
		git push -f "https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git" HEAD:master
	else
		git commit --message 'automatic commit'
		git push "https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git" HEAD:master
	fi
fi

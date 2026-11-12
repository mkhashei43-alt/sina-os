#!/usr/bin/env bash
# انتشار مخزن روی گیت‌هاب با یک دستور
#   ./publish-github.sh <github-username> <repo-name> [public|private]
set -euo pipefail
USER="${1:?نام کاربری گیت‌هاب را بدهید}"
REPO="${2:-sina-os}"
VIS="${3:-public}"

command -v git >/dev/null || { echo "git نصب نیست"; exit 1; }
[ -d .git ] || git init -b main
sed -i.bak "s|github.com/USERNAME/sina-os|github.com/$USER/$REPO|g" README.md docs/*.md 2>/dev/null || true
sed -i.bak "s|github.com/USERNAME/sina-os|github.com/$USER/$REPO|g" README.md 2>/dev/null || true
rm -f README.md.bak docs/*.md.bak

git add -A
git diff --cached --quiet && echo "چیزی برای کامیت نیست" || git commit -m "feat: Sina OS — open source autonomous agent (v1.0)"
git remote remove origin 2>/dev/null || true
git remote add origin "https://github.com/$USER/$REPO.git"

if command -v gh >/dev/null; then
  gh auth status >/dev/null 2>&1 || { echo "اول: gh auth login"; exit 1; }
  gh repo create "$USER/$REPO" --"$VIS" --source=. --push --description "عامل هوشمند خودمختار فارسی — یک دستور، هر سیستم‌عامل" || git push -u origin main
else
  echo "gh CLI نصب نیست؛ مخزن را دستی بسازید و سپس: git push -u origin main"
fi
echo "✓ منتشر شد: https://github.com/$USER/$REPO"

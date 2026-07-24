#!/bin/sh
set -eu

DATA_ROOT="${WIKI_PROJECT_ROOT:-/data}"
mkdir -p "$DATA_ROOT/company-handbook" "$DATA_ROOT/generated-wiki"

if [ ! -f "$DATA_ROOT/wiki-instructions.md" ]; then
  cat > "$DATA_ROOT/wiki-instructions.md" <<'EOF'
# 公司知识库说明

请根据管理员上传的资料生成和维护公司 Wiki。
EOF
fi

exec "$@"

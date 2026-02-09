#!/bin/bash
# VPS Image Structure Validation Script
# Tests that all required files are present and valid

set -euo pipefail

echo "=== VPS Image Structure Validation ==="
echo ""

ERRORS=0

# Check required files
REQUIRED_FILES=(
    "docker-compose.yml"
    "Dockerfile.mission-control"
    "requirements.txt"
    "init-db.sql"
    "scripts/api_server.py"
    ".env.example"
    "README.md"
)

echo "Checking required files..."
for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "  ✓ $file"
    else
        echo "  ✗ $file (MISSING)"
        ERRORS=$((ERRORS + 1))
    fi
done
echo ""

# Check docker-compose syntax
echo "Validating docker-compose.yml..."
if command -v docker &> /dev/null; then
    if docker compose config &> /dev/null; then
        echo "  ✓ docker-compose.yml is valid"
    else
        echo "  ✗ docker-compose.yml has syntax errors"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo "  ⚠ Docker not found, skipping validation"
fi
echo ""

# Check Python script syntax
echo "Validating Python scripts..."
if command -v python3 &> /dev/null; then
    if python3 -m py_compile scripts/api_server.py 2>/dev/null; then
        echo "  ✓ scripts/api_server.py is valid"
    else
        echo "  ✗ scripts/api_server.py has syntax errors"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo "  ⚠ Python3 not found, skipping validation"
fi
echo ""

# Check SQL syntax
echo "Validating SQL..."
if [ -f "init-db.sql" ]; then
    # Basic check for SQL keywords
    if grep -qi "CREATE TABLE" init-db.sql && grep -qi "CREATE INDEX" init-db.sql; then
        echo "  ✓ init-db.sql looks valid"
    else
        echo "  ✗ init-db.sql may be incomplete"
        ERRORS=$((ERRORS + 1))
    fi
fi
echo ""

# Summary
echo "=== Validation Complete ==="
if [ $ERRORS -eq 0 ]; then
    echo "✓ All checks passed!"
    exit 0
else
    echo "✗ $ERRORS error(s) found"
    exit 1
fi

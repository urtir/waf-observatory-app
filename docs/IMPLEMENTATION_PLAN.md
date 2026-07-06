# Rencana Implementasi Web Application WAF + LLM

## 1) Tujuan Sistem
Membangun aplikasi web yang memiliki dua mode utama:
1. Evaluasi metrik terhadap dataset uji ber-ground truth.
2. Analisis log WAF realtime tanpa ground truth, dengan ekspor PDF.

Stack yang dipakai:
- WSL2: Nginx + ModSecurity + Flask + SQLite.
- LM Studio server pada host Windows: http://192.168.56.1:1234.
- Model inferensi: google/gemma-3-4b dan qwen/qwen3-4b.
- Frontend: Bootstrap library (tanpa styling manual custom CSS).

## 2) Batasan Penting (HARUS)
Prompt untuk generate ringkasan harus sama persis:

Anda adalah analis keamanan siber yang menulis golden summary (maksimal 2–3 kalimat) tentang satu transaksi raw log permintaan HTTP berbahaya dari ModSecurity. Ringkasan harus menjelaskan tujuan serangan/aktivitas mencurigakan, jenis serangan jika terlihat, serta metode HTTP, endpoint penting, dan dampak potensial. Gunakan Bahasa Indonesia formal, tanpa bullet.

<RAW_LOG>
{log_text}
</RAW_LOG>

Tuliskan hanya ringkasannya.

Ketentuan tambahan yang harus dipertahankan:
- Potong raw log jika lebih dari 4000 karakter, lalu tambah suffix: "\n... [dipotong]".
- Tidak menambah atau mengurangi kalimat pada prompt.
- Tidak menambah parameter generasi yang tidak diperlukan, agar konsisten dengan pipeline pembanding.

## 3) Struktur Folder yang Disiapkan
- backend: Flask API, service LM Studio, evaluator metrik, parser log.
- frontend: halaman Bootstrap (dashboard + sidebar + tabel + filter + modal).
- infra/nginx: konfigurasi reverse proxy.
- infra/modsecurity: konfigurasi WAF dan audit log.
- data: symlink/konfigurasi sumber data dataset dan cache lokal.
- reports: file PDF hasil cetak analisis.
- scripts: utilitas setup dan migrasi.

## 4) Halaman Aplikasi
### A. Halaman Metrik Dataset Uji
Sumber data wajib:
- Raw log: DATASET/owasp/01-Aug-2025/modsec_audit.anon.log.
- Referensi ground truth: kolom golden_summary dari DATASET/owasp/01-Aug-2025/modsec_audit_golden_txid_summary.with_log_params_txid_normalized.csv.

Alur:
1. Parse transaksi dari raw log berdasarkan txid.
2. Join dengan golden_summary berdasarkan txid.
3. Untuk setiap txid, jalankan inferensi ke model terpilih (Gemma/Qwen) via LM Studio.
4. Hitung metrik per sampel dan agregat:
   - ROUGE-1 F1, ROUGE-2 F1, ROUGE-L F1
   - METEOR
   - BERTScore F1
   - Latensi inferensi (ms)
5. Tampilkan hasil pada tabel + ringkasan agregat.

Catatan:
- Data tidak boleh mock.
- Semua sampel harus berasal dari file riil dataset.

### B. Halaman Analisis Log Realtime WAF
Sumber data:
- Audit log ModSecurity aktif dari WSL2 (realtime append).

Alur:
1. Stream log realtime ke backend (tail log).
2. Tampilkan row log realtime di tabel dengan checkbox per row.
3. User pilih model (Gemma/Qwen) dan pilih banyak row.
4. Sistem generate summary tiap row terpilih dengan prompt exact.
5. Simpan hasil analisis dan latensi ms.
6. Ekspor hasil terpilih ke PDF.

Catatan:
- Di halaman realtime hanya tampil latency ms (tanpa ROUGE/METEOR/BERTScore), karena tidak ada ground truth.

## 5) Rencana API Backend (Flask)
- GET /api/health
- GET /api/models
  - Ambil dari LM Studio /v1/models.
- POST /api/evaluate/dataset
  - Body: model_key, limit, offset, mode.
  - Output: metrik agregat, metrik per txid, latency.
- GET /api/logs/realtime
  - SSE/WebSocket streaming baris log ModSecurity.
- POST /api/analyze/realtime
  - Body: model_key, selected_txids atau selected_rows.
  - Output: summary per row + latency ms.
- POST /api/reports/pdf
  - Body: selected analysis ids.
  - Output: file PDF.

## 6) Rencana Database SQLite
Tabel minimum:
- realtime_logs(id, txid, timestamp, raw_log, source_file)
- analyses(id, mode, model_key, txid, raw_log, summary, latency_ms, created_at)
- metrics(id, analysis_id, rouge1_f1, rouge2_f1, rougel_f1, meteor, bertscore_f1)
- reports(id, filename, created_at)

## 7) Integrasi LM Studio
Base URL:
- http://192.168.56.1:1234

Endpoint utama:
- GET /v1/models
- POST /v1/chat/completions

Strategi inferensi:
- Satu request per txid/row.
- Ukur latensi end-to-end per request (ms).
- Retry terkontrol untuk error jaringan sementara.

## 8) Integrasi WSL2
Komponen di WSL2:
- Nginx sebagai reverse proxy.
- ModSecurity aktif pada Nginx.
- Flask app berjalan di service internal.
- SQLite tersimpan di direktori aplikasi WSL.

Alur request:
Client -> Nginx + ModSecurity -> Flask API -> LM Studio host Windows.

## 9) Milestone Eksekusi
1. Bootstrap project Flask + Bootstrap frontend + SQLite migration.
2. Implement parser txid dari modsec_audit.anon.log.
3. Implement connector LM Studio dan endpoint models.
4. Implement halaman metrik dataset + evaluator ROUGE/METEOR/BERTScore + latency.
5. Implement realtime log ingestion dan tampilan tabel checkbox.
6. Implement analisis batch row terpilih dan penyimpanan hasil.
7. Implement ekspor PDF.
8. Hardening WAF/Nginx dan uji end-to-end.

## 10) Validasi Sukses
- Model Gemma dan Qwen tampil dari endpoint models.
- Halaman dataset menampilkan metrik riil dari data riil.
- Halaman realtime menerima log aktif dari WAF.
- Analisis multi-row berjalan dan menyimpan latensi ms.
- PDF dapat diunduh dengan isi sesuai row yang dipilih.
- Prompt summary terbukti identik 100% dengan versi yang ditetapkan.

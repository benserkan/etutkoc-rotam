"""Smoke: kişi adı standart biçimi (toplu/tekli öğrenci ekleme)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.services.name_format import format_person_name
from app.services.csv_import import parse_students_csv

CASES = [
    ("Güneş deridüzen", "Güneş Deridüzen"),
    ("İSMAİL EYMEN", "İsmail Eymen"),
    ("ışıl ılgaz", "Işıl Ilgaz"),
    ("IŞIL İLGAZ", "Işıl İlgaz"),
    ("doğa  kurtoğlu ", "Doğa Kurtoğlu"),
    ("ayşe-nur yılmaz", "Ayşe-Nur Yılmaz"),
    ("ZEYNEP ÇİĞDEM ŞAHİN", "Zeynep Çiğdem Şahin"),
    ("Esma", "Esma"),
    ("   ", None),
    (None, None),
]
fails = 0
for raw, want in CASES:
    got = format_person_name(raw)
    ok = got == want
    fails += not ok
    print(("OK  " if ok else "FAIL") + f" {raw!r} -> {got!r}" + ("" if ok else f" (beklenen {want!r})"))

r = parse_students_csv("Ad Soyad,E-posta,Veli Adı\nGÜNEŞ deridüzen,g@ornek.com,ercan DERİDÜZEN\n")
row = r.rows[0]
ok = row.full_name == "Güneş Deridüzen" and row.parent_name == "Ercan Deridüzen"
fails += not ok
print(("OK  " if ok else "FAIL") + f" CSV ayrıştırıcı: {row.full_name!r} / {row.parent_name!r}")
print(f"\n{len(CASES) + 1 - fails}/{len(CASES) + 1} passed")
raise SystemExit(1 if fails else 0)

# LGS Takip

Koçluk/dershane ölçeğinde LGS öğrencileri için haftalık çalışma programı + test kitabı envanter takip sistemi.

## Stack

- **Backend:** FastAPI + SQLAlchemy 2.0 + Alembic
- **Frontend:** Jinja2 + HTMX + Tailwind (Play CDN)
- **DB:** SQLite (geliştirme) / Postgres'e geçiş kolay
- **Auth:** Session cookie (passlib + bcrypt)

## İlk Kurulum

```bash
# 1) Sanal ortam ve bağımlılıklar
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt

# 2) .env oluştur
copy .env.example .env        # Windows
# veya: cp .env.example .env

# 3) Veritabanını oluştur + müfredatı ve demo öğretmeni seed et
python -m alembic upgrade head
python -m scripts.seed --teacher
```

Demo öğretmen: `ogretmen@lgs.local` / `ogretmen123`

## Geliştirme Sunucusu

```bash
uvicorn app.main:app --reload --port 8000
```

Sonra `http://localhost:8000` → giriş ekranı.

## Proje Durumu — Sprint 1 tamam

Tamamlananlar:

- Proje iskeleti, konfig, DB bağlantısı
- Tüm SQLAlchemy modelleri (User, AcademicYear, Subject, Topic, Book, BookSection, StudentBook, SectionProgress, Task, TaskBookItem)
- Alembic migration kurulumu + ilk şema
- LGS 8. sınıf müfredat seed (6 ders + üniteler)
- Session-cookie auth (login/logout, role guard)
- Base şablon + Tailwind + HTMX
- Öğretmen paneli:
  - Akademik yıllar CRUD
  - Öğrenci ekleme, geçici şifre üretimi, şifre sıfırlama, silme
  - Kitap kütüphanesi CRUD
  - Kitap ünite/test sayısı yönetimi
  - Kitap → öğrenci ataması (atama sırasında SectionProgress otomatik oluşur)

## Sonraki (Sprint 2)

- Haftalık program UI (öğretmen tarafı): günlük görev oluşturma, görev başına kitap + ünite + test adedi
- **Rezerv mekanizması:** görev oluşturulunca `SectionProgress.reserved_count += planned_count`
- Görev düzenleme/silme → rezerv iade

## Veri Modeli Özeti

```
User (teacher|student, teacher_id self-ref)
AcademicYear (teacher bazlı, sınav tarihi)
Subject / Topic (builtin + teacher-owned; Topic parent_id ile hiyerarşi)
Book (teacher_id, subject, type, avg_questions_per_test)
  └── BookSection (label, topic_id opsiyonel, test_count)
StudentBook (öğrenci ↔ kitap)
  └── SectionProgress (reserved_count, completed_count)
Task (student, date, title, status)
  └── TaskBookItem (book, section, planned_count, completed_count)
```

**Model C (Rezerv):** `kalan = test_count − reserved − completed`.
Görev atama → `reserved += N`. Tamamlama → `completed += N, reserved -= N`. Plan değişince rezerv iade.

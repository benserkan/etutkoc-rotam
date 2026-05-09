"""CSV toplu öğrenci içe aktarım — parse + validation katmanı.

Kullanım akışı:
1. UI'da öğretmen CSV'yi yapıştırır veya yükler
2. `parse_students_csv(text)` → ParseResult (her satır validate edilmiş)
3. UI preview tablo gösterir (✓ uygun / ⚠ hata)
4. Onay → `bulk_create_students(db, teacher, valid_rows)` çağrılır

Tasarım:
- UTF-8 zorunlu, BOM toleranslı
- Header lowercase normalize, esnek alias (örn 'sinif' = 'grade_level')
- Per-row hata gösterimi — kötü satır iyi satırı durdurmaz
- E-posta normalize (lowercase + strip)
- Strict column ordering YOK — header'a göre çözer

CSV format (örnek):
    full_name,email,grade_level,track,is_graduate,graduate_mode
    Ali Veli,ali@x.com,8,,,
    Ayşe Yılmaz,ayse@x.com,11,sayisal,,
    Ahmet Demir,ahmet@x.com,,sozel,yes,full_time
"""

from __future__ import annotations

import csv
import io
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable, TYPE_CHECKING

from app.models.user import GraduateMode, Track

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from app.models import User


logger = logging.getLogger(__name__)


# Header alias map — kullanıcı dostu yazımı kanonik isme çevirir
HEADER_ALIASES = {
    "full_name": "full_name",
    "fullname": "full_name",
    "ad soyad": "full_name",
    "adsoyad": "full_name",
    "isim": "full_name",
    "ad": "full_name",
    "name": "full_name",
    "email": "email",
    "e-posta": "email",
    "eposta": "email",
    "mail": "email",
    "grade_level": "grade_level",
    "grade": "grade_level",
    "sinif": "grade_level",
    "sınıf": "grade_level",
    "track": "track",
    "alan": "track",
    "is_graduate": "is_graduate",
    "graduate": "is_graduate",
    "mezun": "is_graduate",
    "graduate_mode": "graduate_mode",
    "calisma_modu": "graduate_mode",
    "calisma_sekli": "graduate_mode",
    "çalışma şekli": "graduate_mode",
    "calisma sekli": "graduate_mode",
    "mezun_modu": "graduate_mode",
}

REQUIRED_COLS = {"full_name", "email"}
KNOWN_COLS = {
    "full_name", "email", "grade_level", "track",
    "is_graduate", "graduate_mode",
}

# Track CSV value normalizasyonu
TRACK_ALIASES = {
    "sayisal": Track.SAYISAL,
    "sayısal": Track.SAYISAL,
    "say": Track.SAYISAL,
    "ea": Track.EA,
    "esit_agirlik": Track.EA,
    "eşit ağırlık": Track.EA,
    "sozel": Track.SOZEL,
    "sözel": Track.SOZEL,
    "soz": Track.SOZEL,
    "dil": Track.DIL,
}

GRADUATE_MODE_ALIASES = {
    "full_time": GraduateMode.FULL_TIME,
    "fulltime": GraduateMode.FULL_TIME,
    "tam": GraduateMode.FULL_TIME,
    "tam_zamanli": GraduateMode.FULL_TIME,
    "tam zamanlı": GraduateMode.FULL_TIME,
    "dershane": GraduateMode.DERSHANE,
    "etut": GraduateMode.DERSHANE,
    "etüt": GraduateMode.DERSHANE,
}

# Boolean parse (is_graduate)
BOOL_TRUE = {"yes", "true", "1", "evet", "e", "y", "x", "✓"}
BOOL_FALSE = {"no", "false", "0", "hayir", "hayır", "h", "n", "", "-"}

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


# ---------------------------- Veri yapıları ----------------------------


@dataclass
class ParsedStudent:
    """Tek bir CSV satırının parse + validate sonucu."""
    row_num: int                  # 1-indexed (header hariç)
    full_name: str | None = None
    email: str | None = None
    grade_level: int | None = None
    track: Track | None = None
    is_graduate: bool = False
    graduate_mode: GraduateMode | None = None
    raw: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.errors

    @property
    def display_name(self) -> str:
        return self.full_name or "(isim yok)"


@dataclass
class ParseResult:
    """CSV parse sonucu — toplam istatistik + satır listesi."""
    rows: list[ParsedStudent] = field(default_factory=list)
    header_errors: list[str] = field(default_factory=list)

    @property
    def valid_count(self) -> int:
        return sum(1 for r in self.rows if r.is_valid)

    @property
    def invalid_count(self) -> int:
        return sum(1 for r in self.rows if not r.is_valid)

    @property
    def has_fatal_error(self) -> bool:
        """Header eksik vs. — preview ekranı bile gösterilemez."""
        return bool(self.header_errors)


# ---------------------------- Parser ----------------------------


def _normalize_header(h: str) -> str:
    """Header'ı lowercase + boşluk/alias normalize eder."""
    h = (h or "").strip().lower()
    return HEADER_ALIASES.get(h, h)


def _parse_grade(value: str, errors: list[str]) -> tuple[int | None, bool]:
    """Returns (grade_level, is_graduate). Boş ise (None, False)."""
    v = (value or "").strip().lower()
    if not v:
        return (None, False)
    if v in ("graduate", "mezun", "mezun (yks)"):
        return (None, True)
    try:
        n = int(v)
        if n < 1 or n > 12:
            errors.append(f"sınıf {n} aralık dışı (1-12 olmalı)")
            return (None, False)
        return (n, False)
    except ValueError:
        errors.append(f"sınıf '{value}' sayı veya 'mezun' olmalı")
        return (None, False)


def _parse_track(value: str, errors: list[str]) -> Track | None:
    v = (value or "").strip().lower()
    if not v:
        return None
    if v in TRACK_ALIASES:
        return TRACK_ALIASES[v]
    errors.append(f"alan '{value}' tanınmadı (sayisal/ea/sozel/dil olmalı)")
    return None


def _parse_graduate_mode(value: str, errors: list[str]) -> GraduateMode | None:
    v = (value or "").strip().lower()
    if not v:
        return None
    if v in GRADUATE_MODE_ALIASES:
        return GRADUATE_MODE_ALIASES[v]
    errors.append(
        f"çalışma şekli '{value}' tanınmadı (full_time/dershane olmalı)"
    )
    return None


def _parse_bool(value: str, errors: list[str]) -> bool:
    v = (value or "").strip().lower()
    if v in BOOL_TRUE:
        return True
    if v in BOOL_FALSE:
        return False
    errors.append(f"mezun bayrağı '{value}' tanınmadı (evet/hayır)")
    return False


def _validate_combination(parsed: ParsedStudent) -> None:
    """Çapraz alan kontrolleri: 11+ track zorunlu, mezun graduate_mode zorunlu."""
    requires_track = (
        parsed.is_graduate or
        (parsed.grade_level is not None and parsed.grade_level >= 11)
    )
    if requires_track and parsed.track is None:
        parsed.errors.append("11+ sınıf ve mezun için alan zorunlu (sayisal/ea/sozel/dil)")
    if parsed.is_graduate and parsed.graduate_mode is None:
        parsed.errors.append("mezun için çalışma şekli zorunlu (full_time/dershane)")
    # Mezun + grade_level birlikte: çelişki
    if parsed.is_graduate and parsed.grade_level is not None:
        parsed.warnings.append(
            f"mezun=evet AMA sınıf={parsed.grade_level} verildi; sınıf yok sayılacak"
        )
        parsed.grade_level = None


def parse_students_csv(text: str) -> ParseResult:
    """CSV metnini parse edip ParseResult döner.

    Hata durumunda exception fırlatmaz — tüm hatalar ParseResult.rows[].errors'da.
    """
    result = ParseResult()
    if not text or not text.strip():
        result.header_errors.append("CSV içeriği boş")
        return result

    # UTF-8 BOM temizle (Excel sık ekler)
    if text.startswith("﻿"):
        text = text.lstrip("﻿")

    # csv.DictReader header'ı otomatik okur. Önce sniff ile ayırıcı denesin.
    sample = text[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        # Tek sütunlu olabilir — virgül varsay
        dialect = csv.excel

    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    raw_headers = reader.fieldnames or []
    headers = [_normalize_header(h) for h in raw_headers]

    # Required header kontrolü
    missing = REQUIRED_COLS - set(headers)
    if missing:
        result.header_errors.append(
            "Eksik zorunlu sütun(lar): " + ", ".join(sorted(missing))
            + ". CSV ilk satırda 'full_name' ve 'email' olmalı."
        )
        return result

    # Bilinmeyen sütunlar uyarı (devam ederiz)
    unknown_headers = [h for h in headers if h and h not in KNOWN_COLS]
    if unknown_headers:
        # Header_errors yerine result.rows[].warnings'e koyamıyoruz çünkü row'a özel değil
        # Genel uyarı için header_errors kullanmıyoruz (bu fatal). Toleranslı geçelim.
        logger.info("CSV unknown headers (yok sayıldı): %s", unknown_headers)

    # Header→canonical mapping (DictReader satır açar dict orijinal isimle)
    canonical_to_raw: dict[str, str] = {}
    for raw, canon in zip(raw_headers, headers):
        if canon in KNOWN_COLS and canon not in canonical_to_raw:
            canonical_to_raw[canon] = raw

    seen_emails: set[str] = set()
    row_num = 0
    for raw_row in reader:
        row_num += 1
        parsed = ParsedStudent(row_num=row_num, raw=dict(raw_row))

        def _get(canon: str) -> str:
            raw_key = canonical_to_raw.get(canon)
            if not raw_key:
                return ""
            return (raw_row.get(raw_key) or "").strip()

        # Boş satırı atla (tüm alanlar boş)
        if not any(_get(c) for c in KNOWN_COLS):
            continue

        # full_name
        full_name = _get("full_name")
        if not full_name:
            parsed.errors.append("ad soyad zorunlu")
        else:
            parsed.full_name = full_name

        # email
        email = _get("email").lower()
        if not email:
            parsed.errors.append("e-posta zorunlu")
        elif not EMAIL_RE.match(email):
            parsed.errors.append(f"e-posta formatı geçersiz: {email}")
        elif email in seen_emails:
            parsed.errors.append(f"bu CSV içinde mükerrer e-posta: {email}")
        else:
            parsed.email = email
            seen_emails.add(email)

        # grade
        parsed.grade_level, parsed.is_graduate = _parse_grade(
            _get("grade_level"), parsed.errors
        )

        # is_graduate (override grade-derived)
        is_grad_explicit = _get("is_graduate")
        if is_grad_explicit:
            parsed.is_graduate = _parse_bool(is_grad_explicit, parsed.errors)

        # track
        parsed.track = _parse_track(_get("track"), parsed.errors)

        # graduate_mode
        parsed.graduate_mode = _parse_graduate_mode(
            _get("graduate_mode"), parsed.errors
        )

        # Combination validation
        _validate_combination(parsed)

        result.rows.append(parsed)

    return result


# ---------------------------- Bulk create ----------------------------


@dataclass
class CreatedStudent:
    """Başarılı oluşturulan öğrenci — sonuç ekranında geçici şifre ile gösterilir."""
    row_num: int
    full_name: str
    email: str
    grade_label: str
    temp_password: str


@dataclass
class BulkCreateResult:
    """bulk_create_students sonucu — UI sonuç ekranı için."""
    created: list[CreatedStudent] = field(default_factory=list)
    skipped_existing_email: list[ParsedStudent] = field(default_factory=list)
    skipped_invalid: list[ParsedStudent] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)   # toplu hata (DB vs)

    @property
    def created_count(self) -> int:
        return len(self.created)

    @property
    def skipped_count(self) -> int:
        return len(self.skipped_existing_email) + len(self.skipped_invalid)


def bulk_create_students(
    db: "Session",
    *,
    teacher: "User",
    parsed_rows: Iterable[ParsedStudent],
    request=None,
) -> BulkCreateResult:
    """ParsedStudent listesindeki valid satırları User olarak oluşturur.

    Özellikler:
    - Her başarılı oluşturmada güçlü geçici şifre üretir + must_change_password=True
    - Audit log her satır için (USER_CREATE, target=new_user)
    - DB'de zaten var olan e-posta atlanır (parse aşamasında yakalansa da
      paralel race için defensive)
    - Tek transaction değil — her satır kendi commit'i (büyük import'larda
      bir hata diğerlerini durdurmasın)

    Args:
      teacher: Kuran öğretmen (institution_id inherit eder)
      parsed_rows: parse_students_csv'den gelen liste (genelde valid_count > 0)
      request: Audit log için (IP/UA çıkarımı)
    """
    from app.models import AuditAction, User, UserRole
    from app.services.audit import log_action
    from app.services.auth_security import generate_strong_password
    from app.services.security import hash_password

    out = BulkCreateResult()

    # Şifre üretimi sabit seed yok — gerçek random
    for parsed in parsed_rows:
        if not parsed.is_valid:
            out.skipped_invalid.append(parsed)
            continue

        # Defensive: DB'de e-posta var mı?
        existing = db.query(User).filter(User.email == parsed.email).first()
        if existing:
            parsed.errors.append(f"DB'de bu e-posta zaten var (id={existing.id})")
            out.skipped_existing_email.append(parsed)
            continue

        try:
            temp_pw = generate_strong_password(UserRole.STUDENT)
            student = User(
                email=parsed.email,
                password_hash=hash_password(temp_pw),
                full_name=parsed.full_name,
                role=UserRole.STUDENT,
                teacher_id=teacher.id,
                institution_id=teacher.institution_id,  # inherit
                grade_level=parsed.grade_level,
                track=parsed.track,
                is_graduate=parsed.is_graduate,
                graduate_mode=parsed.graduate_mode,
                is_active=True,
                password_changed_at=datetime.now(timezone.utc),
                must_change_password=True,
            )
            db.add(student)
            db.flush()
            log_action(
                db,
                action=AuditAction.USER_CREATE,
                actor_id=teacher.id,
                target_type="user",
                target_id=student.id,
                request=request,
                details={
                    "email": parsed.email,
                    "role": "student",
                    "via": "csv_import",
                    "row_num": parsed.row_num,
                    "institution_id": teacher.institution_id,
                    "temp_password_issued": True,
                },
                autocommit=False,
            )
            db.commit()

            # Grade label
            if parsed.is_graduate:
                grade_label = "🎓 Mezun"
            elif parsed.grade_level:
                grade_label = f"{parsed.grade_level}. sınıf"
            else:
                grade_label = "—"

            out.created.append(CreatedStudent(
                row_num=parsed.row_num,
                full_name=parsed.full_name,
                email=parsed.email,
                grade_label=grade_label,
                temp_password=temp_pw,
            ))
        except Exception as e:
            db.rollback()
            logger.exception("CSV import row %s hata: %s", parsed.row_num, e)
            parsed.errors.append(f"DB hatası: {type(e).__name__}")
            out.skipped_invalid.append(parsed)

    return out

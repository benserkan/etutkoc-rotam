from __future__ import annotations

import enum
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.academic import AcademicYear
    from app.models.book import Book
    from app.models.institution import Institution
    from app.models.progress import StudentBook
    from app.models.task import Task


class UserRole(str, enum.Enum):
    """Kullanıcı rolü.

    Hiyerarşi (Sprint 11+ multi-tenant):
        SUPER_ADMIN > INSTITUTION_ADMIN > TEACHER > STUDENT
                                                  > PARENT (yatay — öğrenciye bağlı)

    - SUPER_ADMIN: tüm sistemi yönetir, kurumlar arası görür, "imitate user" yapar
    - INSTITUTION_ADMIN: sadece kendi kurumunun roster + agrega verisini görür;
      öğretmen verilerine doğrudan erişimi YOK (gizlilik).
    - TEACHER: kendi öğrencilerini yönetir (kurum-altı veya bağımsız)
    - STUDENT, PARENT: mevcut davranış değişmedi
    """
    TEACHER = "teacher"
    STUDENT = "student"
    PARENT = "parent"
    INSTITUTION_ADMIN = "institution_admin"
    SUPER_ADMIN = "super_admin"


class Track(str, enum.Enum):
    """YKS alan seçimi — 11. sınıf+ ve mezunlar için zorunlu."""
    SAYISAL = "sayisal"
    EA = "ea"  # Eşit Ağırlık
    SOZEL = "sozel"
    DIL = "dil"


class GraduateMode(str, enum.Enum):
    """Mezun öğrencinin günlük programının çalışma şekli."""
    FULL_TIME = "full_time"      # Okul yok, 8-10 saat/gün tam-zamanlı
    DERSHANE = "dershane"         # Etüt merkezine gider, kalan zamanda program


TRACK_LABELS: dict[Track, str] = {
    Track.SAYISAL: "Sayısal",
    Track.EA: "Eşit Ağırlık",
    Track.SOZEL: "Sözel",
    Track.DIL: "Dil",
}

GRADUATE_MODE_LABELS: dict[GraduateMode, str] = {
    GraduateMode.FULL_TIME: "Tam-zamanlı (okul yok)",
    GraduateMode.DERSHANE: "Dershane / etüt merkezi",
}


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False)

    teacher_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Multi-tenant (Sprint 11+): kullanıcının bağlı olduğu kurum.
    # NULL = bağımsız (yalnız teacher rolü için anlamlı; admin/student için
    # her zaman dolu). Kurum kapatılırsa SET NULL — teacher bağımsız olur.
    institution_id: Mapped[int | None] = mapped_column(
        ForeignKey("institutions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    academic_year_id: Mapped[int | None] = mapped_column(
        ForeignKey("academic_years.id", ondelete="SET NULL"), nullable=True, index=True
    )
    grade_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Mezun (üniversiteye girecek) öğrenci işareti — grade_level NULL kalabilir.
    # is_graduate=True iken track zorunlu sayılır (UI/route düzeyinde).
    is_graduate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # YKS alan tercihi — 11. sınıf, 12. sınıf ve mezunlar için zorunlu;
    # 9-10. sınıf NULL (henüz seçilmemiş), 5-8 her zaman NULL (LGS).
    track: Mapped[Track | None] = mapped_column(Enum(Track), nullable=True)
    # Sadece is_graduate=True olduğunda anlamlı.
    graduate_mode: Mapped[GraduateMode | None] = mapped_column(
        Enum(GraduateMode), nullable=True
    )
    # 9. sınıfa giriş yılı (Eylül-yılı). Maarif/Klasik müfredat ayrımının
    # kohort bazlı türetilmesi için. 5-8. sınıf öğrencisi için NULL.
    # Mezunlar için 9'a giriş yılı (12'den geriye 3 yıl kuralıyla tahmin
    # edilebilir veya öğretmen elle girer).
    entry_year_grade9: Mapped[int | None] = mapped_column(Integer, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Uyarı susturma durumu (migration o3k0n2l3m11g) — is_active'ten AYRI.
    # is_active=True kalmaya devam eder (auth login açık), ama is_paused=True
    # iken at-risk panel + burnout + admin digest + veli bildirimi gibi alert
    # üreticileri bu kullanıcıyı atlar. Manuel veya otonom (inaktivite cron'u)
    # tetiklenir. pause_reason ile ayrılır: "manual" / "auto_inactivity".
    is_paused: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default=text("false"),
    )
    paused_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    # actor — sistem ise NULL (cron tetiklediği auto-pause)
    paused_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    # "manual" — koç/admin tarafından; "auto_inactivity" — cron tarafından
    pause_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # Manuel resume yapıldığında doldurulur — sticky override 7 günlük
    # cooldown ile cron bu süre içinde tekrar auto-pause yapmaz.
    last_manual_resume_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Güvenlik (Sprint 2 multi-tenant security):
    # Brute-force koruması: ardışık başarısız login sayısı + opsiyonel kilit
    # bitiş zamanı. Başarılı login'de sıfırlanır.
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Son başarılı giriş — UI'da kullanıcıya "son giriş" gösterimi + audit
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_login_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Şifre değişimi zaman damgası — diğer aktif oturumları geçersiz kılmak
    # için (session.password_stamp ile karşılaştırma yapılır).
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Admin tarafından oluşturulan veya şifresi sıfırlanan hesap için True;
    # ilk girişte kullanıcı /password/change'a zorunlu yönlendirilir. Şifre
    # değiştirilince False olur. İleride üyelik/davetiye akışında token-flow
    # bunu da temsil edecek (token kullanılıp şifre belirlenince True→False).
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default=text("false")
    )
    # E-posta doğrulama (Dalga 7 P3) — soft: NULL = doğrulanmamış (panelde banner),
    # dolu = doğrulandı. Mevcut kullanıcılar migration'da geriye dönük doğrulanır.
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # İki faktörlü doğrulama / TOTP (Dalga 7 P4) — yalnız Süper Admin + Kurum
    # Yöneticisi etkinleştirebilir. totp_secret: base32 (setup'ta üretilir,
    # pending); totp_enabled_at dolunca 2FA aktif (login'de kod istenir).
    totp_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    totp_enabled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # KS3 — bağımsız koç AI yakalama (ses/foto→metin) açık rızası. Dolunca koç
    # AI işleme + yurt dışı alt-işleyen (Anthropic/OpenAI) onayını vermiş sayılır.
    ai_capture_consent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    @property
    def two_factor_enabled(self) -> bool:
        return self.totp_enabled_at is not None and bool(self.totp_secret)

    # Stage 6 — bağımsız öğretmen için kredi planı (institution_id NULL ise
    # anlamlı). Kurumlu kullanıcılarda yok sayılır; onların planı
    # Institution.plan'dan okunur. Default 'free' başlangıç tier'ı.
    plan: Mapped[str] = mapped_column(
        String(32), nullable=False, default="free", server_default=text("'free'"),
    )

    # Stage 9 (Faz 2) — Reverse trial: yeni kayıtta 14 gün boyunca pro_solo
    # özellikleri açık; trial_ends_at geçince plan='solo_free'ye düşer.
    # Bağımsız öğretmenlere uygulanır; kurum kullanıcılarında Institution.trial_*
    # kullanılır. NULL = trial geçerli değil (zaten free veya başka bir plana
    # geçmiş).
    trial_ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Trial bittiğinde dönülecek plan (default 'solo_free')
    post_trial_plan: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )

    # Solo abonelik durumu (migration z7a9d2e3d11x) — bağımsız koç (institution_id
    # NULL) için. Kurum aboneliği Institution modelinde. status: active/past_due/
    # canceled (None = abonelik yok, trial/free). period_end: yenileme tarihi.
    # cycle: monthly | academic_year.
    subscription_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    subscription_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    subscription_cycle: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Öğrencinin "hafta anchor" tarihi. Set ise: haftalık view bu tarihi
    # bloğun başı sayar (ör. 24 Nisan Cuma → tüm haftalar Cuma-Perşembe).
    # NULL ise: öğrencinin en eski Task.date'i fallback olarak kullanılır;
    # o da yoksa bugünün ISO haftası (Pazartesi). Koçluk günü değişince
    # öğretmen UI'dan bu alanı yeniden ayarlar.
    program_anchor_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    teacher: Mapped["User | None"] = relationship(
        "User", remote_side="User.id", backref="students", foreign_keys=[teacher_id]
    )
    institution: Mapped["Institution | None"] = relationship(
        "Institution", back_populates="users", foreign_keys=[institution_id]
    )
    academic_year: Mapped["AcademicYear | None"] = relationship(
        "AcademicYear", back_populates="students", foreign_keys=[academic_year_id]
    )

    owned_books: Mapped[list["Book"]] = relationship(
        "Book", back_populates="owner", cascade="all, delete-orphan", foreign_keys="Book.teacher_id"
    )
    student_books: Mapped[list["StudentBook"]] = relationship(
        "StudentBook", back_populates="student", cascade="all, delete-orphan",
        foreign_keys="StudentBook.student_id",
    )
    tasks: Mapped[list["Task"]] = relationship(
        "Task", back_populates="student", cascade="all, delete-orphan",
        foreign_keys="Task.student_id",
    )

    @property
    def display_grade_label(self) -> str:
        """UI'da gösterilecek seviye etiketi: '8. sınıf' veya 'Mezun'."""
        if self.is_graduate:
            return "Mezun"
        if self.grade_level is None:
            return "—"
        return f"{self.grade_level}. sınıf"

    @property
    def effective_exam_target(self) -> str | None:
        """Öğrencinin hedef sınavı: 'LGS', 'YKS' veya None (ara sınıflar).

        - 8. sınıf → LGS
        - 12. sınıf → YKS
        - Mezun (is_graduate=True) → YKS
        - 5,6,7,9,10,11 → None (yıl sonu hedefli, sınav-spesifik tetik yok)
        """
        if self.is_graduate:
            return "YKS"
        if self.grade_level == 8:
            return "LGS"
        if self.grade_level == 12:
            return "YKS"
        return None

    @property
    def effective_exam_label(self) -> str:
        """UI rozet etiketi — 'LGS', 'YKS' veya 'Yıl Sonu' (ara sınıflar)."""
        t = self.effective_exam_target
        return t if t else "Yıl Sonu"

    @property
    def effective_exam_date(self):
        """Öğrenci-spesifik sınav tarihi (date | None).

        Akademik yıl seviyesinde tek bir 'sınav tarihi' tutmak yanıltıcı:
        bir öğretmenin aynı yılda hem LGS (Haziran başı) hem YKS (Haziran ortası)
        öğrencisi olabilir. Bu yüzden tarihi öğrenci seviyesinde, hedef sınav +
        akademik yılın bitiş yılına göre türetiyoruz. Tarihler her yıl MEB/ÖSYM
        takvimine göre değişebilir; aşağıdaki sabitler güncel takvime yaklaşık
        denk gelir, kesin tarih için öğretmen istisna girebilir (gelecekte).
        """
        from datetime import date as _date

        target = self.effective_exam_target
        if target is None or self.academic_year is None:
            return None
        end_year = (
            (self.academic_year.start_year + 1) if self.academic_year.start_year else None
        )
        if not end_year:
            return None
        # Yaklaşık takvim: LGS Haziran ilk Pazar, YKS Haziran üçüncü hafta sonu.
        # Kesinlik gerekirse ileride bir EXAM_CALENDAR sözlüğü eklenebilir.
        if target == "LGS":
            return _date(end_year, 6, 7)
        if target == "YKS":
            return _date(end_year, 6, 20)
        return None

    @property
    def effective_curriculum_model(self):
        """Müfredat modelini akademik yıl + sınıf bilgisinden türet.

        Öncelik:
          1. entry_year_grade9 elle girildiyse onu kullan (sınıf tekrarı vb.
             override durumlar için)
          2. Yoksa academic_year.start_year + grade_level'dan tahmin et
          3. Hiçbiri yoksa None (UI öğretmenden manuel seçmesini ister)
        """
        from app.models.curriculum import derive_curriculum_model

        ay_start = None
        if self.academic_year is not None:
            ay_start = self.academic_year.start_year

        return derive_curriculum_model(
            grade_level=self.grade_level,
            is_graduate=self.is_graduate,
            entry_year_grade9=self.entry_year_grade9,
            academic_year_start=ay_start,
        )

    @property
    def requires_track(self) -> bool:
        """Track (alan) seçimi bu öğrenci için zorunlu mu?

        Karar (2026-05-08): 11. sınıf+ ve mezunlar için zorunlu.
        9-10. sınıf opsiyonel; 5-8 hiç sorulmaz (LGS, alan kavramı yok).
        """
        if self.is_graduate:
            return True
        if self.grade_level is None:
            return False
        return self.grade_level >= 11

    def __repr__(self) -> str:
        return f"<User {self.id} {self.email} {self.role.value}>"

"""Panel hızlı erişim — davranıştan öğrenen kartlar (QA-1).

Üç katman: Topla → Skorla → Sun.

1) Topla: frontend shell'leri rota değişimlerini batch POST eder; burada
   ham path ROTA KATALOĞU ile normalize edilir (route_key + entity_id).
   Katalogda olmayan path SAYILMAZ (token'lı sayfalar, /payment, /login
   otomatik dışarıda — KVKK: ham URL hiçbir yerde saklanmaz).

2) Skorla: kullanıcı+rota+entity başına tek satır (PanelRouteStat) EWMA
   ile güncellenir — score = score * 0.5^(geçen_gün/14) + ağırlık.
   Kişi-düzeyi (entity) rotalar derin yol oldukları için 1.5 ağırlık alır.
   Cron gerekmez: okuma anında da skor bugüne indirgenir; kullanılmayan
   kart kendiliğinden söner.

3) Sun: quick_cards() yaşam döngüsünü uygular:
   ADAY → (skor ≥ 3.0 VE ≥3 farklı gün) → ÖNERİLEN
   ÖNERİLEN → (karta 3 tıklama VEYA elle sabitle) → KALICI
   Kaldırılan rota 90 gün önerilmez. Entity etiketi okuma anında çözülür;
   erişim hakkı düşen kayıt (silinen/pasif öğrenci, kurum-dışı koç) kartı
   otomatik düşürür.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import (
    Book,
    Institution,
    PanelRouteStat,
    PanelVisitEvent,
    ParentStudentLink,
    StudentBook,
    User,
    UserRole,
)

logger = logging.getLogger(__name__)

# ── Ayar sabitleri ──────────────────────────────────────────────────────────
HALF_LIFE_DAYS = 14.0          # EWMA yarılanma ömrü
SUGGEST_MIN_SCORE = 3.0        # öneri eşiği (≈ taze 3 ziyaret / 2 derin ziyaret)
SUGGEST_MIN_DAYS = 3           # en az 3 FARKLI günde ziyaret (tek günlük patlama önerilmez)
ESTABLISH_CLICKS = 3           # karta 3 tıklama → kalıcı
DISMISS_DAYS = 90              # kaldırılan rota bu kadar gün bastırılır
EVENT_RETENTION_DAYS = 180     # ham olay logu saklama süresi
STAT_RETENTION_DAYS = 180      # dokunulmamış agregat satırı saklama süresi
VISIT_DEDUP_SECONDS = 60       # aynı rota+entity'ye 60 sn içinde ikinci ziyaret sayılmaz
ENTITY_WEIGHT = 1.5            # kişi-düzeyi (derin) rota ziyaret ağırlığı
PAGE_WEIGHT = 1.0
MAX_BATCH_EVENTS = 50          # tek POST'ta kabul edilen olay sayısı
MAX_CARDS = 12                 # GET'in döndürdüğü aday sayısı (frontend 6 gösterir)

# Entity türleri: viewer rolüne göre erişim kontrolü _resolve_entity'de.
#   student      → koçun kendi öğrencisi (User, teacher_id == viewer)
#   child        → velinin bağlı çocuğu (ParentStudentLink)
#   teacher      → kurum yöneticisinin kendi kurumundaki koçu
#   institution  → süper admin için kurum
#   user         → süper admin için kullanıcı
#   book         → koçun kendi kitabı
#   student_book → öğrencinin kendine atanmış kitabı (StudentBook)


@dataclass(frozen=True)
class CatalogEntry:
    route_key: str
    template: str          # "/teacher/students/{id}/week" — {id} entity yakalar, {any} yakalamaz
    label: str
    entity_kind: str | None = None
    pattern: re.Pattern | None = None

    def href(self, entity_id: int | None) -> str:
        if "{id}" in self.template and entity_id:
            return self.template.replace("{id}", str(entity_id))
        # {any} fold'lu girişlerin kanonik linki — fold segmentini at
        return re.sub(r"/\{any\}.*$", "", self.template)

    @property
    def weight(self) -> float:
        return ENTITY_WEIGHT if self.entity_kind else PAGE_WEIGHT


def _compile(template: str) -> re.Pattern:
    rx = re.escape(template)
    rx = rx.replace(re.escape("{id}"), r"(?P<eid>\d+)")
    rx = rx.replace(re.escape("{any}"), r"\d+")
    return re.compile(f"^{rx}/?$")


def _E(route_key: str, template: str, label: str, entity_kind: str | None = None) -> CatalogEntry:
    return CatalogEntry(
        route_key=route_key,
        template=template,
        label=label,
        entity_kind=entity_kind,
        pattern=_compile(template),
    )


# ── Rota kataloğu (5 rol) ───────────────────────────────────────────────────
# Panel ana sayfaları (şeridin yaşadığı yer) katalogda YOK: /teacher/dashboard,
# /institution, /admin, /parent. Sihirbaz/form sayfaları (import, promote,
# library/new) ve token'lı public sayfalar da bilinçli olarak dışarıda.
_CATALOG: list[CatalogEntry] = [
    # ── Koç ──
    _E("teacher.students", "/teacher/students", "Öğrenciler"),
    _E("teacher.student_detail", "/teacher/students/{id}", "Öğrenci profili", "student"),
    _E("teacher.student_day", "/teacher/students/{id}/day", "Günlük Program", "student"),
    _E("teacher.student_week", "/teacher/students/{id}/week", "Haftalık Program", "student"),
    _E("teacher.student_dna", "/teacher/students/{id}/dna", "Çalışma DNA", "student"),
    _E("teacher.student_focus", "/teacher/students/{id}/focus", "Odak", "student"),
    _E("teacher.student_goals", "/teacher/students/{id}/goals", "Hedefler", "student"),
    _E("teacher.student_review", "/teacher/students/{id}/review", "Aralıklı Tekrar", "student"),
    _E("teacher.library", "/teacher/library", "Kütüphane"),
    _E("teacher.book_detail", "/teacher/library/books/{id}", "Kitap", "book"),
    _E("teacher.book_sets", "/teacher/library/book-sets", "Kitap Setleri"),
    _E("teacher.book_sets", "/teacher/library/book-sets/{any}", "Kitap Setleri"),
    _E("teacher.task_templates", "/teacher/library/task-templates", "Görev Şablonları"),
    _E("teacher.book_templates", "/teacher/library/templates", "Kitap Şablonları"),
    _E("teacher.billing", "/teacher/billing", "Tahsilat"),
    _E("teacher.bulk_wa", "/teacher/bulk-wa", "Toplu WhatsApp"),
    _E("teacher.requests", "/teacher/requests", "Talepler"),
    _E("teacher.requests", "/teacher/requests/{any}", "Talepler"),
    _E("teacher.support", "/teacher/support", "Destek"),
    _E("teacher.support_inbox", "/teacher/support-inbox", "Gelen Talepler"),
    _E("teacher.insights", "/teacher/insights", "İçgörüler"),
    _E("teacher.plan", "/teacher/plan", "Paketim"),
    _E("teacher.settings", "/teacher/settings", "Ayarlar"),
    _E("teacher.academic_years", "/teacher/academic-years", "Akademik Yıllar"),
    _E("teacher.academic_years", "/teacher/academic-years/{any}", "Akademik Yıllar"),
    _E("teacher.grade_advance", "/teacher/grade-advance", "Sınıf Yükseltme"),
    _E("teacher.burnout", "/teacher/burnout", "Tükenmişlik"),
    _E("teacher.review", "/teacher/review", "Tekrar Planlayıcı"),
    _E("teacher.usage", "/teacher/usage", "Kredi Kullanımı"),
    # ── Öğrenci ──
    _E("student.day", "/student/day", "Bugün"),
    _E("student.week", "/student/week", "Haftalık Program"),
    _E("student.books", "/student/books", "Kitaplarım"),
    _E("student.book_detail", "/student/books/{id}", "Kitap", "student_book"),
    _E("student.dna", "/student/dna", "Çalışma DNA"),
    _E("student.focus", "/student/focus", "Odak"),
    _E("student.goals", "/student/goals", "Hedefler"),
    _E("student.requests", "/student/requests", "Taleplerim"),
    _E("student.review", "/student/review", "Aralıklı Tekrar"),
    _E("student.topics", "/student/topics", "Konu Performansı"),
    # ── Veli ──
    _E("parent.child_detail", "/parent/students/{id}", "Çocuk detayı", "child"),
    _E("parent.child_week", "/parent/students/{id}/week", "Haftalık Program", "child"),
    _E("parent.child_report", "/parent/students/{id}/report", "Haftalık Rapor", "child"),
    _E("parent.child_exams", "/parent/students/{id}/exams", "Denemeler & Analiz", "child"),
    _E("parent.child_sessions", "/parent/students/{id}/sessions", "Seanslar", "child"),
    _E("parent.child_topics", "/parent/students/{id}/topics", "Konu Performansı", "child"),
    _E("parent.notifications", "/parent/notifications", "Bildirimler"),
    _E("parent.settings", "/parent/settings", "Ayarlar"),
    _E("parent.support", "/parent/support", "Destek"),
    # ── Kurum yöneticisi ──
    _E("institution.compliance", "/institution/compliance", "Program Uyumu"),
    _E("institution.action_center", "/institution/action-center", "Müdahale Merkezi"),
    _E("institution.academic", "/institution/academic", "Akademik Çıktı"),
    _E("institution.at_risk", "/institution/at-risk", "Risk Paneli"),
    _E("institution.burnout", "/institution/burnout", "Tükenmişlik"),
    _E("institution.cohorts", "/institution/cohorts", "Kohortlar"),
    _E("institution.activity_heatmap", "/institution/activity-heatmap", "Aktivite Haritası"),
    _E("institution.activity_stream", "/institution/activity-stream", "Aktivite Akışı"),
    _E("institution.teacher_scorecard", "/institution/teacher-scorecard", "Öğretmen Karnesi"),
    _E("institution.parent_trust", "/institution/parent-trust", "Veli Güveni"),
    _E("institution.goals", "/institution/goals", "Hedef Analizi"),
    _E("institution.roster", "/institution/roster", "Öğrenci Listesi"),
    _E("institution.teachers", "/institution/teachers", "Öğretmenler"),
    _E("institution.teacher_detail", "/institution/teachers/{id}", "Koç kartı", "teacher"),
    _E("institution.invitations", "/institution/invitations", "Davetiyeler"),
    _E("institution.admin_digest", "/institution/admin-digest", "Haftalık Özet"),
    _E("institution.admin_digest", "/institution/admin-digest/{any}", "Haftalık Özet"),
    _E("institution.subscription", "/institution/subscription", "Abonelik"),
    _E("institution.quota", "/institution/quota", "Limitler"),
    _E("institution.usage", "/institution/usage", "Kredi Kullanımı"),
    _E("institution.support", "/institution/support", "Taleplerim"),
    _E("institution.support_inbox", "/institution/support-inbox", "Gelen Talepler"),
    _E("institution.bulk_wa", "/institution/bulk-wa", "Toplu WhatsApp"),
    # ── Süper admin ──
    _E("admin.users", "/admin/users", "Kullanıcılar"),
    _E("admin.user_detail", "/admin/users/{id}", "Kullanıcı detayı", "user"),
    _E("admin.user_history", "/admin/users/{id}/account-history", "Hesap Hareketleri", "user"),
    _E("admin.institutions", "/admin/institutions", "Kurumlar"),
    _E("admin.institution_detail", "/admin/institutions/{id}", "Kurum detayı", "institution"),
    _E("admin.institution_history", "/admin/institutions/{id}/account-history", "Hesap Hareketleri", "institution"),
    _E("admin.independent_teachers", "/admin/independent-teachers", "Bağımsız Öğretmenler"),
    _E("admin.activity_stream", "/admin/activity-stream", "Aktivite Akışı"),
    _E("admin.audit", "/admin/audit", "Audit Log"),
    _E("admin.kvkk", "/admin/kvkk", "KVKK"),
    _E("admin.system_health", "/admin/system-health", "Sistem Sağlığı"),
    _E("admin.announcements", "/admin/announcements", "Duyurular"),
    _E("admin.contact_requests", "/admin/contact-requests", "İletişim Talepleri"),
    _E("admin.demo_sessions", "/admin/demo-sessions", "Demo Oturumları"),
    _E("admin.feature_catalog", "/admin/feature-catalog", "Vitrin Kartları"),
    _E("admin.feature_catalog", "/admin/feature-catalog/{any}", "Vitrin Kartları"),
    _E("admin.feature_catalog", "/admin/feature-catalog/new", "Vitrin Kartları"),
    _E("admin.fc_dashboard", "/admin/feature-catalog/dashboard", "Vitrin Yönetimi"),
    _E("admin.fc_discovery", "/admin/feature-catalog/discovery-queue", "Keşif Kuyruğu"),
    _E("admin.fc_experiments", "/admin/feature-catalog/experiments", "Deneyler"),
    _E("admin.fc_experiments", "/admin/feature-catalog/experiments/{any}", "Deneyler"),
    _E("admin.fc_experiments", "/admin/feature-catalog/experiments/new", "Deneyler"),
    _E("admin.feature_flags", "/admin/feature-flags", "Özellik Bayrakları"),
    _E("admin.feature_flags", "/admin/feature-flags/{any}", "Özellik Bayrakları"),
    _E("admin.quota", "/admin/quota", "Kotalar"),
    _E("admin.usage", "/admin/usage", "Kredi Kullanımı"),
    _E("admin.payment_links", "/admin/payment-links", "Ödeme Linkleri"),
    _E("admin.membership_offers", "/admin/membership-offers", "Üyelik Teklifleri"),
    _E("admin.pricing", "/admin/pricing", "Ücretlendirme"),
    _E("admin.settings", "/admin/settings", "AI Ayarları"),
    _E("admin.support", "/admin/support", "Talepler"),
    _E("admin.whatsapp_templates", "/admin/whatsapp-templates", "WhatsApp Şablonları"),
    _E("admin.whatsapp_dispatch_log", "/admin/whatsapp-dispatch-log", "WhatsApp Audit"),
    _E("admin.revenue_action_center", "/admin/revenue/action-center", "Aksiyon Merkezi"),
    _E("admin.revenue_forecast", "/admin/revenue/forecast", "Gelir Tahmini"),
    _E("admin.revenue_cohort", "/admin/revenue/cohort", "Kohort & LTV"),
    _E("admin.revenue_campaigns", "/admin/revenue/campaigns", "Kampanyalar"),
    _E("admin.revenue_campaigns", "/admin/revenue/campaigns/{any}", "Kampanyalar"),
    _E("admin.revenue_campaigns", "/admin/revenue/campaigns/new", "Kampanyalar"),
    _E("admin.revenue_action_templates", "/admin/revenue/action-templates", "Aksiyon Şablonları"),
    _E("admin.revenue_inst_360", "/admin/revenue/institutions/{id}", "Ticari 360", "institution"),
    _E("admin.revenue_user_360", "/admin/revenue/users/{id}", "Ticari 360", "user"),
    _E("admin.sm_overview", "/admin/security-monitor", "Güvenlik — Genel Bakış"),
    _E("admin.sm_revenue", "/admin/security-monitor/revenue", "Ticari Pano"),
    _E("admin.sm_invoices", "/admin/security-monitor/revenue/invoices", "Faturalar"),
    _E("admin.sm_activity", "/admin/security-monitor/activity", "Aktivite Kamerası"),
    _E("admin.sm_sessions", "/admin/security-monitor/sessions", "Oturumlar"),
    _E("admin.sm_live", "/admin/security-monitor/live", "Canlı Akış"),
    _E("admin.sm_alarms", "/admin/security-monitor/alarms", "Alarmlar"),
    _E("admin.sm_abuse", "/admin/security-monitor/abuse", "Suistimal"),
    _E("admin.sm_integrity", "/admin/security-monitor/integrity", "Veri Bütünlüğü"),
    _E("admin.sm_system", "/admin/security-monitor/system", "Sistem Hataları"),
    _E("admin.sm_notifications", "/admin/security-monitor/notifications", "Bildirim Sağlığı"),
]

# Uzun (spesifik) şablon önce eşleşsin — "/admin/users/{id}/account-history"
# "/admin/users/{id}"den önce denenmeli.
_CATALOG_ORDERED = sorted(_CATALOG, key=lambda e: len(e.template), reverse=True)
# Aynı route_key'in birden çok pattern'i olabilir (liste + detay fold) —
# kanonik giriş (href/label) listede İLK görünen, yani liste sayfası.
_CATALOG_BY_KEY: dict[str, CatalogEntry] = {}
for _entry in _CATALOG:
    _CATALOG_BY_KEY.setdefault(_entry.route_key, _entry)

# route_key prefix'i → bu rotayı ziyaret edebilecek rol
_PREFIX_ROLE: dict[str, UserRole] = {
    "teacher": UserRole.TEACHER,
    "student": UserRole.STUDENT,
    "parent": UserRole.PARENT,
    "institution": UserRole.INSTITUTION_ADMIN,
    "admin": UserRole.SUPER_ADMIN,
}


def normalize_path(path: str) -> tuple[CatalogEntry, int | None] | None:
    """Ham path'i katalog girdisine çevirir. Katalogda yoksa None (sayılmaz)."""
    if not path or not path.startswith("/"):
        return None
    clean = path.split("?", 1)[0].split("#", 1)[0].rstrip("/") or "/"
    for entry in _CATALOG_ORDERED:
        m = entry.pattern.match(clean)
        if m:
            eid = m.groupdict().get("eid")
            return entry, (int(eid) if eid else None)
    return None


def _role_allows(user: User, route_key: str) -> bool:
    prefix = route_key.split(".", 1)[0]
    expected = _PREFIX_ROLE.get(prefix)
    return expected is not None and user.role == expected


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _decayed(score: float, last_visit_at: datetime | None, now: datetime) -> float:
    last = _aware(last_visit_at)
    if last is None or score <= 0:
        return 0.0
    elapsed_days = max(0.0, (now - last).total_seconds() / 86400.0)
    return score * (0.5 ** (elapsed_days / HALF_LIFE_DAYS))


# ── 1. Topla ────────────────────────────────────────────────────────────────

def record_visits(
    db: Session,
    user: User,
    events: list[dict],
    *,
    source: str = "web",
    now: datetime | None = None,
) -> int:
    """Batch ziyaret kaydı. Her olay: {"path": str, "dwell_ms": int?}.

    Katalog-dışı / rol-dışı path sessizce atlanır. Aynı rota+entity'ye
    VISIT_DEDUP_SECONDS içinde ikinci ziyaret skor/sayaç artırmaz (ham
    olay da yazılmaz). Caller commit eder.
    """
    now = now or _utcnow()
    accepted = 0
    for raw in events[:MAX_BATCH_EVENTS]:
        path = str(raw.get("path") or "")
        normalized = normalize_path(path)
        if normalized is None:
            continue
        entry, entity_id = normalized
        if not _role_allows(user, entry.route_key):
            continue
        try:
            dwell_ms = max(0, min(int(raw.get("dwell_ms") or 0), 3_600_000))
        except (TypeError, ValueError):
            dwell_ms = 0

        eid = entity_id or 0
        stat = (
            db.query(PanelRouteStat)
            .filter(
                PanelRouteStat.user_id == user.id,
                PanelRouteStat.route_key == entry.route_key,
                PanelRouteStat.entity_id == eid,
            )
            .first()
        )
        if stat is not None:
            last = _aware(stat.last_visit_at)
            if last is not None:
                elapsed = (now - last).total_seconds()
                # çift sayım koruması — yalnız ileri yönde; geç gelen
                # (out-of-order) batch olayları sayılmaya devam eder
                if 0 <= elapsed < VISIT_DEDUP_SECONDS:
                    continue
        else:
            stat = PanelRouteStat(
                user_id=user.id,
                route_key=entry.route_key,
                entity_id=eid,
                score=0.0,
                visit_count=0,
                days_seen=0,
                dwell_ms_total=0,
                card_clicks=0,
            )
            db.add(stat)

        # EWMA: önce bugüne indir, sonra ziyaret ağırlığını ekle
        stat.score = _decayed(stat.score, stat.last_visit_at, now) + entry.weight
        stat.visit_count += 1
        stat.dwell_ms_total += dwell_ms
        visit_date = now.date()
        if stat.last_visit_date != visit_date:
            stat.days_seen += 1
        # last_visit_at geriye TAŞINMAZ (out-of-order olayda en yenisi kalır)
        prev = _aware(stat.last_visit_at)
        if prev is None or now >= prev:
            stat.last_visit_at = now
            stat.last_visit_date = visit_date

        db.add(
            PanelVisitEvent(
                user_id=user.id,
                role=user.role.value,
                route_key=entry.route_key,
                entity_id=entity_id,
                dwell_ms=dwell_ms,
                source=source,
                created_at=now,
            )
        )
        # autoflush kapalıyken aynı batch'te ikinci olay yeni satırı görsün
        # (UNIQUE ihlali / mükerrer INSERT koruması)
        db.flush()
        accepted += 1
    return accepted


# ── 2/3. Skorla + Sun ───────────────────────────────────────────────────────

def _resolve_entity(
    db: Session, viewer: User, kind: str, entity_id: int
) -> str | None:
    """Entity etiketini döndürür; viewer'ın erişimi yoksa None (kart düşer)."""
    if kind in ("student", "child", "teacher", "user"):
        u = db.query(User).filter(User.id == entity_id).first()
        if u is None:
            return None
        if kind == "student":
            if (
                viewer.role != UserRole.TEACHER
                or u.role != UserRole.STUDENT
                or u.teacher_id != viewer.id
                or not u.is_active
            ):
                return None
        elif kind == "child":
            if viewer.role != UserRole.PARENT or u.role != UserRole.STUDENT:
                return None
            link = (
                db.query(ParentStudentLink)
                .filter(
                    ParentStudentLink.parent_id == viewer.id,
                    ParentStudentLink.student_id == u.id,
                )
                .first()
            )
            if link is None:
                return None
        elif kind == "teacher":
            if (
                viewer.role != UserRole.INSTITUTION_ADMIN
                or u.role != UserRole.TEACHER
                or viewer.institution_id is None
                or u.institution_id != viewer.institution_id
            ):
                return None
        elif kind == "user":
            if viewer.role != UserRole.SUPER_ADMIN:
                return None
        return u.full_name
    if kind == "institution":
        if viewer.role != UserRole.SUPER_ADMIN:
            return None
        inst = db.query(Institution).filter(Institution.id == entity_id).first()
        return inst.name if inst is not None else None
    if kind == "book":
        if viewer.role != UserRole.TEACHER:
            return None
        book = (
            db.query(Book)
            .filter(Book.id == entity_id, Book.teacher_id == viewer.id)
            .first()
        )
        return book.name if book is not None else None
    if kind == "student_book":
        if viewer.role != UserRole.STUDENT:
            return None
        row = (
            db.query(Book)
            .join(StudentBook, StudentBook.book_id == Book.id)
            .filter(StudentBook.student_id == viewer.id, Book.id == entity_id)
            .first()
        )
        return row.name if row is not None else None
    return None


def quick_cards(
    db: Session, user: User, *, now: datetime | None = None, limit: int = MAX_CARDS
) -> list[dict]:
    """Kullanıcının hızlı erişim kartları (sabitlenen + kalıcı + önerilen).

    Sıra: sabitlenenler → kalıcılar → skor sırasıyla önerilenler.
    """
    now = now or _utcnow()
    rows = (
        db.query(PanelRouteStat)
        .filter(PanelRouteStat.user_id == user.id)
        .all()
    )
    cards: list[dict] = []
    for stat in rows:
        entry = _CATALOG_BY_KEY.get(stat.route_key)
        if entry is None:
            continue  # katalogdan kaldırılmış eski anahtar
        if not _role_allows(user, stat.route_key):
            continue
        dismissed = _aware(stat.dismissed_until)
        if dismissed is not None and dismissed > now:
            continue

        eff_score = _decayed(stat.score, stat.last_visit_at, now)
        pinned = stat.pinned_at is not None
        established = stat.card_clicks >= ESTABLISH_CLICKS
        suggested = eff_score >= SUGGEST_MIN_SCORE and stat.days_seen >= SUGGEST_MIN_DAYS
        if not (pinned or established or suggested):
            continue

        entity_id = stat.entity_id or None
        label = entry.label
        entity_label: str | None = None
        if entry.entity_kind and entity_id:
            entity_label = _resolve_entity(db, user, entry.entity_kind, entity_id)
            if entity_label is None:
                continue  # erişim düştü → kart düşer
        elif entry.entity_kind and not entity_id:
            continue  # entity rotası entity'siz olamaz (bozuk satır)

        state = "pinned" if pinned else ("established" if established else "suggested")
        cards.append(
            {
                "route_key": stat.route_key,
                "entity_id": entity_id,
                "href": entry.href(entity_id),
                "label": entity_label or label,
                "sublabel": label if entity_label else None,
                "state": state,
                "score": round(eff_score, 3),
                "card_clicks": stat.card_clicks,
            }
        )

    _state_rank = {"pinned": 0, "established": 1, "suggested": 2}
    cards.sort(key=lambda c: (_state_rank[c["state"]], -c["score"]))
    return cards[:limit]


# ── Kart kararları ──────────────────────────────────────────────────────────

def _get_stat(
    db: Session, user: User, route_key: str, entity_id: int | None
) -> PanelRouteStat | None:
    return (
        db.query(PanelRouteStat)
        .filter(
            PanelRouteStat.user_id == user.id,
            PanelRouteStat.route_key == route_key,
            PanelRouteStat.entity_id == (entity_id or 0),
        )
        .first()
    )


def register_card_click(
    db: Session, user: User, route_key: str, entity_id: int | None
) -> PanelRouteStat | None:
    """Hızlı erişim kartının KENDİSİNE tıklama — kalıcılaşma sayacı.

    Hedef sayfanın ziyareti tracker'dan zaten sayılır; burada yalnız
    card_clicks artar (3'te otomatik KALICI)."""
    stat = _get_stat(db, user, route_key, entity_id)
    if stat is None:
        return None
    stat.card_clicks += 1
    return stat


def set_pin(
    db: Session, user: User, route_key: str, entity_id: int | None, pinned: bool
) -> PanelRouteStat | None:
    stat = _get_stat(db, user, route_key, entity_id)
    if stat is None:
        return None
    stat.pinned_at = _utcnow() if pinned else None
    if pinned:
        stat.dismissed_until = None
    return stat


def dismiss_card(
    db: Session, user: User, route_key: str, entity_id: int | None
) -> PanelRouteStat | None:
    """Kartı kaldır — 90 gün önerilmez (alarm körlüğü: 'hayır'a saygı)."""
    stat = _get_stat(db, user, route_key, entity_id)
    if stat is None:
        return None
    stat.dismissed_until = _utcnow() + timedelta(days=DISMISS_DAYS)
    stat.pinned_at = None
    stat.card_clicks = 0  # kalıcılık sıfırlanır; tekrar kazanılması gerekir
    return stat


# ── Cron: saklama politikası ────────────────────────────────────────────────

def purge_old_events(db: Session, *, now: datetime | None = None) -> dict:
    """180 günden eski ham olayları + dokunulmamış agregat satırlarını siler.

    Sabitlenen/kalıcı kartların satırları SİLİNMEZ (kullanıcı kararı yaşar)."""
    now = now or _utcnow()
    event_cutoff = now - timedelta(days=EVENT_RETENTION_DAYS)
    stat_cutoff = now - timedelta(days=STAT_RETENTION_DAYS)
    deleted_events = (
        db.query(PanelVisitEvent)
        .filter(PanelVisitEvent.created_at < event_cutoff)
        .delete(synchronize_session=False)
    )
    deleted_stats = (
        db.query(PanelRouteStat)
        .filter(
            PanelRouteStat.last_visit_at.isnot(None),
            PanelRouteStat.last_visit_at < stat_cutoff,
            PanelRouteStat.pinned_at.is_(None),
            PanelRouteStat.card_clicks < ESTABLISH_CLICKS,
        )
        .delete(synchronize_session=False)
    )
    db.commit()
    return {"deleted_events": deleted_events, "deleted_stats": deleted_stats}

"""Katman 11.H — Tenant aktivite kamerası.

Aktif kullanım göstergeleri:
  - daily_active_users (DAU) — son 24 saatte LOGIN_SUCCESS olan distinct user
  - weekly_active_users (WAU) — son 7 gün
  - monthly_active_users (MAU) — son 30 gün
  - per_tenant_activity — tenant başına DAU/WAU/MAU
  - hour_day_heatmap — son 7 gün saat × hafta-içi-günü matrisi (login sayımı)
  - daily_dau_trend — son 14 gün DAU eğrisi
  - tenant_silence — son 7 günde aktivitesi düşen kurumlar (proxy: 0 login)

Kaynak: AuditLog LOGIN_SUCCESS olayları (actor_id'ye User.institution_id'den
tenant tespit edilir).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.models import (
    ActiveSession,
    AuditAction,
    AuditLog,
    Institution,
    User,
    UserRole,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


# ---------------------------- Toplu DAU/WAU/MAU ----------------------------


def _distinct_user_count(db: Session, *, hours: int) -> int:
    cutoff = _now() - timedelta(hours=hours)
    return int(
        (db.query(func.count(func.distinct(AuditLog.actor_id)))
         .filter(
             AuditLog.action == AuditAction.LOGIN_SUCCESS,
             AuditLog.actor_id.isnot(None),
             AuditLog.created_at >= cutoff,
         )
         .scalar()) or 0
    )


def aggregate_activity(db: Session) -> dict:
    """Toplu DAU/WAU/MAU."""
    return {
        "dau": _distinct_user_count(db, hours=24),
        "wau": _distinct_user_count(db, hours=24 * 7),
        "mau": _distinct_user_count(db, hours=24 * 30),
    }


# ---------------------------- Tenant başına ----------------------------


def per_tenant_activity(db: Session, *, top: int = 20) -> list[dict]:
    """Tenant başına DAU/WAU/MAU.

    AuditLog → User.institution_id join ile tenant tespit.
    Top N kurum (MAU descending).
    """
    now = _now()
    cutoff_day = now - timedelta(hours=24)
    cutoff_week = now - timedelta(days=7)
    cutoff_month = now - timedelta(days=30)

    def _per_tenant_distinct(cutoff):
        rows = (
            db.query(
                User.institution_id.label("tid"),
                func.count(func.distinct(AuditLog.actor_id)).label("c"),
            )
            .join(User, User.id == AuditLog.actor_id)
            .filter(
                AuditLog.action == AuditAction.LOGIN_SUCCESS,
                AuditLog.created_at >= cutoff,
                User.institution_id.isnot(None),
            )
            .group_by(User.institution_id)
            .all()
        )
        return {int(r.tid): int(r.c) for r in rows}

    dau = _per_tenant_distinct(cutoff_day)
    wau = _per_tenant_distinct(cutoff_week)
    mau = _per_tenant_distinct(cutoff_month)

    tenant_ids = set(dau) | set(wau) | set(mau)
    if not tenant_ids:
        return []

    insts = (
        db.query(Institution)
        .filter(Institution.id.in_(tenant_ids))
        .all()
    )
    out: list[dict] = []
    for inst in insts:
        out.append({
            "tenant_id": inst.id,
            "tenant_name": inst.name,
            "plan": inst.plan,
            "dau": dau.get(inst.id, 0),
            "wau": wau.get(inst.id, 0),
            "mau": mau.get(inst.id, 0),
        })
    out.sort(key=lambda r: (-r["mau"], -r["wau"]))
    return out[:top]


# ---------------------------- Heatmap (saat × gün) ----------------------------


# Hafta gün isimleri (Türkçe, Pazartesi=0)
_DAYS_TR = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]


def hour_day_heatmap(db: Session, *, days: int = 7) -> dict:
    """Son N gün için saat (0-23) × hafta günü (Pzt-Paz) login sayım matrisi."""
    cutoff = _now() - timedelta(days=days)
    rows = (
        db.query(AuditLog.created_at)
        .filter(
            AuditLog.action == AuditAction.LOGIN_SUCCESS,
            AuditLog.created_at >= cutoff,
        )
        .all()
    )
    # matrix[hour][day_idx] = count
    matrix: dict[int, dict[int, int]] = {h: {d: 0 for d in range(7)} for h in range(24)}
    for (created_at,) in rows:
        ts = _aware(created_at)
        if ts is None:
            continue
        # Türkiye dilimi olmasa bile UTC bazlı (gerçek lokal saatte minor sapma olur)
        h = ts.hour
        d = ts.weekday()  # 0 = Pzt, 6 = Paz
        matrix[h][d] += 1

    max_val = max(
        (matrix[h][d] for h in range(24) for d in range(7)),
        default=0,
    )
    return {
        "days_window": days,
        "matrix": matrix,
        "max_value": max_val,
        "day_labels": _DAYS_TR,
        "total": sum(matrix[h][d] for h in range(24) for d in range(7)),
    }


# ---------------------------- DAU trend ----------------------------


def daily_dau_trend(db: Session, *, days: int = 14) -> list[dict]:
    """Son N gün için günlük DAU eğrisi."""
    cutoff = _now() - timedelta(days=days)
    rows = (
        db.query(AuditLog.created_at, AuditLog.actor_id)
        .filter(
            AuditLog.action == AuditAction.LOGIN_SUCCESS,
            AuditLog.actor_id.isnot(None),
            AuditLog.created_at >= cutoff,
        )
        .all()
    )
    now = _now()
    by_day: dict[str, set[int]] = {}
    for i in range(days):
        day = (now - timedelta(days=days - 1 - i)).date().isoformat()
        by_day[day] = set()
    for ca, uid in rows:
        ts = _aware(ca)
        if ts is None:
            continue
        day = ts.date().isoformat()
        if day in by_day:
            by_day[day].add(int(uid))
    return [{"day": d, "dau": len(users)} for d, users in by_day.items()]


# ---------------------------- Sessiz tenant uyarısı ----------------------------


def silent_tenants(db: Session, *, days: int = 7) -> list[dict]:
    """Son N gün içinde 0 LOGIN_SUCCESS olan aktif kurumlar."""
    cutoff = _now() - timedelta(days=days)
    # AuditLog'da aktif olan tenant id'leri
    active_tenant_ids = {
        int(r[0]) for r in
        db.query(User.institution_id)
        .join(AuditLog, AuditLog.actor_id == User.id)
        .filter(
            AuditLog.action == AuditAction.LOGIN_SUCCESS,
            AuditLog.created_at >= cutoff,
            User.institution_id.isnot(None),
        )
        .distinct()
        .all()
    }
    insts = (
        db.query(Institution)
        .filter(
            Institution.is_active.is_(True),
            ~Institution.id.in_(active_tenant_ids) if active_tenant_ids else (1 == 1),
        )
        .order_by(Institution.name)
        .all()
    )
    return [
        {
            "owner_type": "institution",
            "owner_id": i.id,
            "tenant_id": i.id,
            "tenant_name": i.name,
            "plan": i.plan,
            "detail_url": f"/admin/revenue/institutions/{i.id}",
        }
        for i in insts
    ]


# ---------------------------- Rol kırılımı (Sprint 1 Faz B) ----------------------------


def _distinct_users_with_role(
    db: Session, *, cutoff: datetime, role: UserRole,
) -> int:
    return int(
        (db.query(func.count(func.distinct(AuditLog.actor_id)))
         .join(User, User.id == AuditLog.actor_id)
         .filter(
             AuditLog.action == AuditAction.LOGIN_SUCCESS,
             AuditLog.actor_id.isnot(None),
             AuditLog.created_at >= cutoff,
             User.role == role,
         )
         .scalar()) or 0
    )


def role_breakdown_today(db: Session) -> dict:
    """Bugün vs dün aktif kullanıcı sayısı, rol kırılımlı."""
    now = _now()
    today_cut = now - timedelta(hours=24)
    yest_start = now - timedelta(hours=48)

    def _yest_count(role: UserRole) -> int:
        # Dün = [now-48h, now-24h) penceresi
        return int(
            (db.query(func.count(func.distinct(AuditLog.actor_id)))
             .join(User, User.id == AuditLog.actor_id)
             .filter(
                 AuditLog.action == AuditAction.LOGIN_SUCCESS,
                 AuditLog.actor_id.isnot(None),
                 AuditLog.created_at >= yest_start,
                 AuditLog.created_at < today_cut,
                 User.role == role,
             )
             .scalar()) or 0
        )

    roles = [
        (UserRole.TEACHER, "Öğretmen", "indigo", "🎓"),
        (UserRole.STUDENT, "Öğrenci", "sky", "🎒"),
        (UserRole.PARENT, "Veli", "purple", "👨‍👩"),
        (UserRole.INSTITUTION_ADMIN, "Kurum Yöneticisi", "amber", "🔑"),
    ]
    out: list[dict] = []
    for role, label, color, icon in roles:
        today = _distinct_users_with_role(db, cutoff=today_cut, role=role)
        yest = _yest_count(role)
        delta = today - yest
        delta_pct = (
            round(100 * delta / yest) if yest > 0 else (100 if today > 0 else 0)
        )
        out.append({
            "role": role.value,
            "label": label,
            "color": color,
            "icon": icon,
            "today": today,
            "yesterday": yest,
            "delta": delta,
            "delta_pct": delta_pct,
        })
    return {"rows": out, "generated_at": now}


# ---------------------------- Kurum kalp atışı (Sprint 1 Faz B) ----------------------------


def _classify_band(days_ago: int | None) -> tuple[str, str, str]:
    """Son giriş gün sayısına göre 5-bantlı sınıflama.

    Returns (band_key, color, label_tr).
    """
    if days_ago is None:
        return ("no_login", "slate", "hiç giriş yok")
    if days_ago >= 30:
        return ("dead", "slate", "kayıp/ölü")
    if days_ago >= 14:
        return ("critical", "rose", "risk")
    if days_ago >= 7:
        return ("warning", "amber", "dikkat")
    if days_ago >= 3:
        return ("watch", "yellow", "izle")
    return ("healthy", "emerald", "sağlıklı")


def _solo_teachers(db: Session, *, limit: int = 200) -> list[User]:
    """Bağımsız öğretmenler — `institution_id IS NULL` ve `role=TEACHER`.

    Bunlar Owner-pattern'de "tek-kişilik tenant" gibi davranır; her birinin
    kendi öğrencileri (User.teacher_id) ve kendi planı (User.plan) vardır.
    """
    return (
        db.query(User)
        .filter(
            User.role == UserRole.TEACHER,
            User.institution_id.is_(None),
            User.is_active.is_(True),
        )
        .order_by(User.full_name, User.email)
        .limit(limit)
        .all()
    )


def _solo_student_ids(db: Session, teacher_ids: list[int]) -> dict[int, list[int]]:
    """Her bağımsız öğretmen için öğrenci ID listesi."""
    if not teacher_ids:
        return {}
    rows = (
        db.query(User.teacher_id, User.id)
        .filter(
            User.role == UserRole.STUDENT,
            User.teacher_id.in_(teacher_ids),
        )
        .all()
    )
    out: dict[int, list[int]] = {tid: [] for tid in teacher_ids}
    for tid, sid in rows:
        out.setdefault(int(tid), []).append(int(sid))
    return out


def _solo_owner_label(u: User) -> str:
    return u.full_name or u.email or f"#{u.id}"


def _solo_plan(u: User) -> str:
    return u.plan or "free"


def solo_heartbeats(db: Session, *, limit: int = 200) -> list[dict]:
    """Bağımsız öğretmenler için kalp atışı listesi.

    Heartbeat tanımı: öğretmenin kendi son girişi VEYA öğrencilerinin
    son girişlerinin max'ı (sistem hâlâ canlı sayılır).
    Bantlar `institution_heartbeats` ile aynı (5-band).
    """
    now = _now()
    teachers = _solo_teachers(db, limit=limit)
    if not teachers:
        return []
    teacher_ids = [t.id for t in teachers]
    stu_map = _solo_student_ids(db, teacher_ids)
    all_student_ids = [sid for sids in stu_map.values() for sid in sids]

    # Öğretmen son girişleri
    t_rows = (
        db.query(
            AuditLog.actor_id.label("uid"),
            func.max(AuditLog.created_at).label("last"),
        )
        .filter(
            AuditLog.action == AuditAction.LOGIN_SUCCESS,
            AuditLog.actor_id.in_(teacher_ids),
        )
        .group_by(AuditLog.actor_id)
        .all()
    )
    teacher_last = {int(r.uid): _aware(r.last) for r in t_rows if r.last}

    # Öğrenci son girişleri (her öğretmen için max)
    student_last_by_teacher: dict[int, datetime] = {}
    if all_student_ids:
        s_rows = (
            db.query(
                AuditLog.actor_id.label("uid"),
                func.max(AuditLog.created_at).label("last"),
            )
            .filter(
                AuditLog.action == AuditAction.LOGIN_SUCCESS,
                AuditLog.actor_id.in_(all_student_ids),
            )
            .group_by(AuditLog.actor_id)
            .all()
        )
        student_last_map = {int(r.uid): _aware(r.last) for r in s_rows if r.last}
        for tid, sids in stu_map.items():
            best = None
            for sid in sids:
                v = student_last_map.get(sid)
                if v and (best is None or v > best):
                    best = v
            if best:
                student_last_by_teacher[tid] = best

    out: list[dict] = []
    for t in teachers:
        last_self = teacher_last.get(t.id)
        last_students = student_last_by_teacher.get(t.id)
        # Heartbeat = max(öğretmen, öğrenciler)
        if last_self and last_students:
            last = max(last_self, last_students)
        else:
            last = last_self or last_students
        if last is last_self and last_self:
            source = "teacher_self"
        elif last is last_students and last_students:
            source = "students"
        else:
            source = None
        days_ago = (now - last).days if last else None
        band, band_color, _ = _classify_band(days_ago)
        if days_ago is None:
            label = "hiç giriş yok"
        elif days_ago == 0:
            label = "bugün"
        else:
            label = f"{days_ago}g önce"
        out.append({
            "owner_type": "solo",
            "owner_id": t.id,
            "institution_id": None,
            "institution_name": _solo_owner_label(t),
            "plan": _solo_plan(t),
            "last_login_at": last,
            "last_source": source,
            "days_since_login": days_ago,
            "band": band,
            "band_color": band_color,
            "label": label,
            "detail_url": f"/admin/revenue/users/{t.id}",
            "student_count": len(stu_map.get(t.id, [])),
        })

    band_order = {"no_login": 0, "dead": 1, "critical": 2,
                  "warning": 3, "watch": 4, "healthy": 5}
    out.sort(key=lambda r: (band_order.get(r["band"], 9),
                             -(r["days_since_login"] or 9999)))
    return out


def institution_heartbeats(db: Session, *, limit: int = 200) -> list[dict]:
    """Her aktif kurumun yetkili son giriş zamanı + 5-bantlı uyarı sınıflaması.

    Bantlar (Sprint 2 Faz G):
      • healthy  (0-2 gün)   — sağlıklı
      • watch    (3-6 gün)   — izle
      • warning  (7-13 gün)  — dikkat
      • critical (14-29 gün) — risk
      • dead     (30+ gün)   — kayıp/ölü
      • no_login (NULL)      — hiç giriş yok

    Yetkili = INSTITUTION_ADMIN. Eğer hiç INST_ADMIN yoksa fallback: en son
    giriş yapan TEACHER.
    """
    now = _now()
    insts = (
        db.query(Institution)
        .filter(Institution.is_active.is_(True))
        .order_by(Institution.name)
        .limit(limit)
        .all()
    )
    if not insts:
        return []

    inst_ids = [i.id for i in insts]
    admin_rows = (
        db.query(
            User.institution_id.label("tid"),
            func.max(AuditLog.created_at).label("last"),
        )
        .join(AuditLog, AuditLog.actor_id == User.id)
        .filter(
            AuditLog.action == AuditAction.LOGIN_SUCCESS,
            User.institution_id.in_(inst_ids),
            User.role == UserRole.INSTITUTION_ADMIN,
        )
        .group_by(User.institution_id)
        .all()
    )
    admin_last: dict[int, datetime] = {
        int(r.tid): _aware(r.last) for r in admin_rows if r.last
    }
    teacher_rows = (
        db.query(
            User.institution_id.label("tid"),
            func.max(AuditLog.created_at).label("last"),
        )
        .join(AuditLog, AuditLog.actor_id == User.id)
        .filter(
            AuditLog.action == AuditAction.LOGIN_SUCCESS,
            User.institution_id.in_(inst_ids),
            User.role == UserRole.TEACHER,
        )
        .group_by(User.institution_id)
        .all()
    )
    teacher_last: dict[int, datetime] = {
        int(r.tid): _aware(r.last) for r in teacher_rows if r.last
    }

    out: list[dict] = []
    for inst in insts:
        last_admin = admin_last.get(inst.id)
        last_teacher = teacher_last.get(inst.id)
        last = last_admin or last_teacher
        source = "admin" if last_admin else ("teacher" if last_teacher else None)
        days_ago = (now - last).days if last else None
        band, band_color, _band_lbl = _classify_band(days_ago)
        if days_ago is None:
            label = "hiç giriş yok"
        elif days_ago == 0:
            label = "bugün"
        else:
            label = f"{days_ago}g önce"

        out.append({
            "owner_type": "institution",
            "owner_id": inst.id,
            "institution_id": inst.id,
            "institution_name": inst.name,
            "plan": inst.plan,
            "last_login_at": last,
            "last_source": source,
            "days_since_login": days_ago,
            "band": band,
            "band_color": band_color,
            "label": label,
            "detail_url": f"/admin/revenue/institutions/{inst.id}",
        })

    band_order = {"no_login": 0, "dead": 1, "critical": 2,
                  "warning": 3, "watch": 4, "healthy": 5}
    out.sort(key=lambda r: (band_order.get(r["band"], 9),
                             -(r["days_since_login"] or 9999)))
    return out


def combined_heartbeats(db: Session, *, segment: str = "all",
                          limit: int = 200) -> list[dict]:
    """Segment'e göre kurum ve/veya bağımsız öğretmen kalp atışı listesi."""
    if segment == "institution":
        return institution_heartbeats(db, limit=limit)
    if segment == "solo":
        return solo_heartbeats(db, limit=limit)
    insts = institution_heartbeats(db, limit=limit)
    solos = solo_heartbeats(db, limit=limit)
    merged = insts + solos
    band_order = {"no_login": 0, "dead": 1, "critical": 2,
                  "warning": 3, "watch": 4, "healthy": 5}
    merged.sort(key=lambda r: (band_order.get(r["band"], 9),
                                -(r["days_since_login"] or 9999)))
    return merged


def heartbeat_summary(rows: list[dict]) -> dict:
    """Kalp atışı listesinden özet sayılar (rozet için)."""
    summary = {"healthy": 0, "watch": 0, "warning": 0, "critical": 0,
                "dead": 0, "no_login": 0}
    for r in rows:
        summary[r["band"]] = summary.get(r["band"], 0) + 1
    summary["total"] = len(rows)
    summary["unhealthy"] = summary["critical"] + summary["dead"] + summary["no_login"]
    return summary


# ---------------------------- Kurum bazlı heatmap (Sprint 1 Faz F) ----------------------------


def institution_hour_day_heatmap(
    db: Session, *, institution_id: int, days: int = 7,
) -> dict:
    """Tek bir kurumun son N gün saat × gün login matrisi + örüntü etiketi."""
    inst = db.get(Institution, institution_id)
    if inst is None:
        return {
            "institution_id": institution_id,
            "institution_name": None,
            "days_window": days,
            "matrix": {h: {d: 0 for d in range(7)} for h in range(24)},
            "max_value": 0,
            "total": 0,
            "day_labels": _DAYS_TR,
            "patterns": [],
        }

    cutoff = _now() - timedelta(days=days)
    rows = (
        db.query(AuditLog.created_at)
        .join(User, User.id == AuditLog.actor_id)
        .filter(
            AuditLog.action == AuditAction.LOGIN_SUCCESS,
            AuditLog.created_at >= cutoff,
            User.institution_id == institution_id,
        )
        .all()
    )
    matrix: dict[int, dict[int, int]] = {h: {d: 0 for d in range(7)} for h in range(24)}
    for (created_at,) in rows:
        ts = _aware(created_at)
        if ts is None:
            continue
        matrix[ts.hour][ts.weekday()] += 1

    max_val = max(
        (matrix[h][d] for h in range(24) for d in range(7)), default=0,
    )
    total = sum(matrix[h][d] for h in range(24) for d in range(7))

    patterns = _detect_heatmap_patterns(matrix, total)

    return {
        "institution_id": institution_id,
        "institution_name": inst.name,
        "plan": inst.plan,
        "days_window": days,
        "matrix": matrix,
        "max_value": max_val,
        "total": total,
        "day_labels": _DAYS_TR,
        "patterns": patterns,
    }


def _detect_heatmap_patterns(
    matrix: dict[int, dict[int, int]], total: int,
) -> list[dict]:
    """Heatmap'ten otomatik örüntü etiketi tespit et."""
    if total == 0:
        return [{"label": "Veri yok", "tone": "slate"}]

    # Hafta günü dağılımı
    by_day = {d: sum(matrix[h][d] for h in range(24)) for d in range(7)}
    weekend = by_day.get(5, 0) + by_day.get(6, 0)
    weekend_pct = round(100 * weekend / total)

    # Saat dağılımı
    morning = sum(matrix[h][d] for h in range(6, 12) for d in range(7))
    afternoon = sum(matrix[h][d] for h in range(12, 18) for d in range(7))
    evening = sum(matrix[h][d] for h in range(18, 24) for d in range(7))
    night = sum(matrix[h][d] for h in (0, 1, 2, 3, 4, 5) for d in range(7))

    patterns: list[dict] = []

    if weekend_pct < 10:
        patterns.append({"label": "Hafta sonu boş", "tone": "amber",
                          "detail": f"Tüm girişin yalnız %{weekend_pct}'i hafta sonu"})
    elif weekend_pct > 40:
        patterns.append({"label": "Hafta sonu yoğun", "tone": "emerald",
                          "detail": f"%{weekend_pct} hafta sonu — esnek kullanım"})

    parts = [(morning, "Sabah"), (afternoon, "Öğleden sonra"),
             (evening, "Akşam"), (night, "Gece")]
    parts.sort(reverse=True)
    if parts[0][0] > 0 and parts[0][0] >= 0.5 * total:
        patterns.append({"label": f"{parts[0][1]} ağırlıklı", "tone": "indigo",
                          "detail": f"%{round(100 * parts[0][0] / total)} bu zaman diliminde"})

    # Cuma çöküşü / Pazartesi sendromu
    avg_weekday = sum(by_day[d] for d in range(5)) / 5 if any(by_day[d] for d in range(5)) else 0
    if avg_weekday > 0:
        if by_day.get(4, 0) < 0.5 * avg_weekday:
            patterns.append({"label": "Cuma çöküşü", "tone": "rose",
                              "detail": "Cuma günleri belirgin düşüş"})
        if by_day.get(0, 0) < 0.5 * avg_weekday:
            patterns.append({"label": "Pazartesi sendromu", "tone": "rose",
                              "detail": "Pazartesi günleri belirgin düşüş"})

    if not patterns:
        patterns.append({"label": "Düzenli dağılım", "tone": "emerald",
                          "detail": "Belirgin tepe veya boşluk yok"})
    return patterns


# ---------------------------- Bu hafta vs geçen hafta (Sprint 1 Faz B) ----------------------------


def dau_week_over_week(db: Session) -> dict:
    """Bu hafta vs geçen hafta günlük DAU karşılaştırma — overlay grafik için."""
    now = _now()
    # 14 günü tek seferde çek, sonra iki haftaya böl
    rows = (
        db.query(AuditLog.created_at, AuditLog.actor_id)
        .filter(
            AuditLog.action == AuditAction.LOGIN_SUCCESS,
            AuditLog.actor_id.isnot(None),
            AuditLog.created_at >= now - timedelta(days=14),
        )
        .all()
    )
    today = now.date()
    # this_week: 6 gün önce ... bugün (7 gün); last_week: 13g önce ... 7g önce
    this_dates = [(today - timedelta(days=6 - i)) for i in range(7)]
    last_dates = [(today - timedelta(days=13 - i)) for i in range(7)]
    this_users: dict[str, set[int]] = {d.isoformat(): set() for d in this_dates}
    last_users: dict[str, set[int]] = {d.isoformat(): set() for d in last_dates}
    for ca, uid in rows:
        ts = _aware(ca)
        if ts is None:
            continue
        key = ts.date().isoformat()
        if key in this_users:
            this_users[key].add(int(uid))
        elif key in last_users:
            last_users[key].add(int(uid))
    # Hafta günleri etiketleri (Pzt, Sal, ...)
    day_labels = [_DAYS_TR[d.weekday()] for d in this_dates]
    this_series = [len(this_users[d.isoformat()]) for d in this_dates]
    last_series = [len(last_users[d.isoformat()]) for d in last_dates]
    this_total = sum(this_series)
    last_total = sum(last_series)
    delta = this_total - last_total
    delta_pct = round(100 * delta / last_total) if last_total > 0 else (
        100 if this_total > 0 else 0
    )
    return {
        "day_labels": day_labels,
        "this_dates": [d.isoformat() for d in this_dates],
        "last_dates": [d.isoformat() for d in last_dates],
        "this_series": this_series,
        "last_series": last_series,
        "this_total": this_total,
        "last_total": last_total,
        "delta": delta,
        "delta_pct": delta_pct,
        "max_value": max(max(this_series, default=0), max(last_series, default=0)),
    }


# ---------------------------- Drill-down: aktif kullanıcılar (Sprint 1 Faz I) ----------------------------


def active_users_window(
    db: Session, *,
    window: str = "dau",            # 'dau' | 'wau' | 'mau'
    role: str | None = None,        # 'teacher'|'student'|'parent'|'institution_admin'
    institution_id: int | None = None,
    limit: int = 50,
) -> list[dict]:
    """Belirtilen pencerede aktif olmuş distinct user listesi (en son giriş ile)."""
    hours_map = {"dau": 24, "wau": 24 * 7, "mau": 24 * 30}
    hrs = hours_map.get(window, 24)
    cutoff = _now() - timedelta(hours=hrs)

    q = (
        db.query(
            User.id, User.full_name, User.email, User.role,
            User.institution_id,
            func.max(AuditLog.created_at).label("last_login"),
        )
        .join(AuditLog, AuditLog.actor_id == User.id)
        .filter(
            AuditLog.action == AuditAction.LOGIN_SUCCESS,
            AuditLog.created_at >= cutoff,
        )
        .group_by(
            User.id, User.full_name, User.email, User.role, User.institution_id,
        )
    )
    if role:
        try:
            q = q.filter(User.role == UserRole(role))
        except ValueError:
            pass
    if institution_id is not None:
        q = q.filter(User.institution_id == institution_id)

    rows = q.order_by(desc("last_login")).limit(limit).all()
    out: list[dict] = []
    inst_ids = {r.institution_id for r in rows if r.institution_id}
    inst_map: dict[int, str] = {}
    if inst_ids:
        for i in db.query(Institution).filter(Institution.id.in_(inst_ids)).all():
            inst_map[i.id] = i.name
    for r in rows:
        out.append({
            "user_id": int(r.id),
            "name": r.full_name or r.email,
            "email": r.email,
            "role": r.role.value if r.role else None,
            "institution_id": r.institution_id,
            "institution_name": inst_map.get(r.institution_id) if r.institution_id else None,
            "last_login_at": _aware(r.last_login),
        })
    return out


# ---------------------------- Faz C: Tutunma metrikleri (Sprint 2) ----------------------------


def stickiness_metric(db: Session) -> dict:
    """DAU/MAU oranı = kullanıcıların yüzde kaçı bugün de geldi.

    Bantlar:
      >= 30%  → 'healthy' (sağlıklı)
      20-30%  → 'medium'  (orta)
      < 20%   → 'low'     (zayıf)
    """
    dau = _distinct_user_count(db, hours=24)
    mau = _distinct_user_count(db, hours=24 * 30)
    pct = round(100 * dau / mau, 1) if mau > 0 else 0.0
    if pct >= 30:
        band = "healthy"; color = "emerald"; label = "sağlıklı"
    elif pct >= 20:
        band = "medium"; color = "amber"; label = "orta — geliştirilebilir"
    else:
        band = "low"; color = "rose"; label = "zayıf — kullanıcılar geri dönmüyor"
    return {
        "dau": dau,
        "mau": mau,
        "ratio_pct": pct,
        "band": band,
        "color": color,
        "label": label,
    }


def stickiness_trend(db: Session, *, days: int = 30) -> list[dict]:
    """Son N gün için günlük DAU/MAU oranı serisi."""
    now = _now()
    rows = (
        db.query(AuditLog.created_at, AuditLog.actor_id)
        .filter(
            AuditLog.action == AuditAction.LOGIN_SUCCESS,
            AuditLog.actor_id.isnot(None),
            AuditLog.created_at >= now - timedelta(days=days + 30),
        )
        .all()
    )
    # tek pass'te tüm günler → tarih -> set(user_id)
    by_day: dict[str, set[int]] = {}
    for ca, uid in rows:
        ts = _aware(ca)
        if ts is None:
            continue
        d = ts.date().isoformat()
        by_day.setdefault(d, set()).add(int(uid))

    out: list[dict] = []
    today = now.date()
    for i in range(days):
        day = today - timedelta(days=days - 1 - i)
        # DAU = o gün
        dau = len(by_day.get(day.isoformat(), set()))
        # MAU = [day-29 ... day]
        mau_users: set[int] = set()
        for j in range(30):
            d2 = (day - timedelta(days=j)).isoformat()
            mau_users.update(by_day.get(d2, set()))
        mau = len(mau_users)
        ratio = round(100 * dau / mau, 1) if mau > 0 else 0.0
        out.append({"day": day.isoformat(), "dau": dau, "mau": mau, "ratio": ratio})
    return out


def week1_retention(db: Session) -> dict:
    """Bu hafta kayıt olan kullanıcının kaçı 7 gün sonra hâlâ aktif.

    Pencere: 14 gün önce kayıt olmuş kullanıcılar (artık 7g doldurmuş);
    bunlardan kaçı son 7 günde giriş yaptı.
    """
    now = _now()
    signup_from = now - timedelta(days=14)
    signup_to = now - timedelta(days=7)
    actives_cutoff = now - timedelta(days=7)

    signup_rows = (
        db.query(User.id)
        .filter(
            User.created_at >= signup_from,
            User.created_at < signup_to,
        )
        .all()
    )
    signup_ids = {int(r.id) for r in signup_rows}
    total = len(signup_ids)
    if total == 0:
        return {"total": 0, "active": 0, "ratio_pct": None}

    active_rows = (
        db.query(AuditLog.actor_id)
        .filter(
            AuditLog.action == AuditAction.LOGIN_SUCCESS,
            AuditLog.actor_id.in_(signup_ids),
            AuditLog.created_at >= actives_cutoff,
        )
        .distinct()
        .all()
    )
    active_ids = {int(r.actor_id) for r in active_rows}
    return {
        "total": total,
        "active": len(active_ids),
        "ratio_pct": round(100 * len(active_ids) / total),
    }


def day30_survival(db: Session) -> dict:
    """Bir kullanıcının kayıt olduktan 30 gün sonra hâlâ aktif olma oranı.

    Pencere: 30-37 gün önce kayıt olmuş kullanıcılar (30g doldurmuş);
    bunlardan kaçı son 7 günde giriş yaptı.
    %50'nin altı = onboarding problemi sinyali.
    """
    now = _now()
    signup_from = now - timedelta(days=37)
    signup_to = now - timedelta(days=30)
    actives_cutoff = now - timedelta(days=7)

    signup_rows = (
        db.query(User.id)
        .filter(
            User.created_at >= signup_from,
            User.created_at < signup_to,
        )
        .all()
    )
    signup_ids = {int(r.id) for r in signup_rows}
    total = len(signup_ids)
    if total == 0:
        return {"total": 0, "active": 0, "ratio_pct": None, "health": "unknown"}

    active_rows = (
        db.query(AuditLog.actor_id)
        .filter(
            AuditLog.action == AuditAction.LOGIN_SUCCESS,
            AuditLog.actor_id.in_(signup_ids),
            AuditLog.created_at >= actives_cutoff,
        )
        .distinct()
        .all()
    )
    active_ids = {int(r.actor_id) for r in active_rows}
    ratio = round(100 * len(active_ids) / total)
    if ratio >= 70:
        health = "healthy"; color = "emerald"
    elif ratio >= 50:
        health = "medium"; color = "amber"
    else:
        health = "low"; color = "rose"
    return {
        "total": total,
        "active": len(active_ids),
        "ratio_pct": ratio,
        "health": health,
        "color": color,
    }


def resurrected_users(
    db: Session, *, silent_days: int = 14, return_days: int = 7, limit: int = 50,
) -> list[dict]:
    """N+ gün sessiz olup son M günde dönen kullanıcılar.

    Kayıt olduktan sonra >= silent_days hareketsiz kalıp şimdi son return_days
    içinde tekrar giriş yapan kullanıcıları döndürür — en güzel onboarding/
    kampanya başarı sinyali.
    """
    now = _now()
    return_cutoff = now - timedelta(days=return_days)
    silent_cutoff = return_cutoff - timedelta(days=silent_days)

    # Son return_days içinde girişi olanlar
    recent_rows = (
        db.query(
            AuditLog.actor_id,
            func.min(AuditLog.created_at).label("first_return"),
        )
        .filter(
            AuditLog.action == AuditAction.LOGIN_SUCCESS,
            AuditLog.actor_id.isnot(None),
            AuditLog.created_at >= return_cutoff,
        )
        .group_by(AuditLog.actor_id)
        .all()
    )
    recent_ids = [int(r.actor_id) for r in recent_rows]
    if not recent_ids:
        return []
    first_return_map = {int(r.actor_id): _aware(r.first_return) for r in recent_rows}

    # Bu kullanıcıların önceki son girişlerini bul (return_cutoff'tan ÖNCE)
    prev_rows = (
        db.query(
            AuditLog.actor_id,
            func.max(AuditLog.created_at).label("prev_last"),
        )
        .filter(
            AuditLog.action == AuditAction.LOGIN_SUCCESS,
            AuditLog.actor_id.in_(recent_ids),
            AuditLog.created_at < return_cutoff,
        )
        .group_by(AuditLog.actor_id)
        .all()
    )
    prev_last_map = {int(r.actor_id): _aware(r.prev_last) for r in prev_rows}

    # Kullanıcıların temel bilgileri
    users = (
        db.query(User)
        .filter(User.id.in_(recent_ids))
        .all()
    )
    user_map = {u.id: u for u in users}

    out: list[dict] = []
    for uid in recent_ids:
        u = user_map.get(uid)
        if u is None:
            continue
        prev_last = prev_last_map.get(uid)
        if prev_last is None:
            # Hiç önceki giriş yok = ilk girişi sayılır, resurrection değil
            continue
        gap_days = (return_cutoff - prev_last).days
        if gap_days < silent_days:
            continue
        first_ret = first_return_map.get(uid) or now
        out.append({
            "user_id": uid,
            "name": u.full_name or u.email,
            "email": u.email,
            "role": u.role.value if u.role else None,
            "institution_id": u.institution_id,
            "previous_last_login": prev_last,
            "returned_at": first_ret,
            "gap_days": gap_days,
        })
    out.sort(key=lambda r: -r["gap_days"])
    return out[:limit]


# ---------------------------- Faz G: Sönüş hızı + Plan×Aktivite (Sprint 2) ----------------------------


def institution_decay_rates(db: Session, *, limit: int = 200) -> list[dict]:
    """Her kurumun son 7g vs önceki 7g aktivite değişim %'si.

    Sert düşüş (>=%50) → 'sharp_drop', kritik uyarı.
    Yavaş düşüş (%20-50) → 'slow_drop'.
    Sabit ya da artış → 'stable' veya 'growing'.
    """
    now = _now()
    cut_recent = now - timedelta(days=7)
    cut_prev = now - timedelta(days=14)

    # Aktif kurumlar
    insts = (
        db.query(Institution)
        .filter(Institution.is_active.is_(True))
        .limit(limit)
        .all()
    )
    if not insts:
        return []
    inst_ids = [i.id for i in insts]

    def _bucket(cut_from: datetime, cut_to: datetime | None) -> dict[int, int]:
        q = (
            db.query(
                User.institution_id.label("tid"),
                func.count(func.distinct(AuditLog.actor_id)).label("c"),
            )
            .join(User, User.id == AuditLog.actor_id)
            .filter(
                AuditLog.action == AuditAction.LOGIN_SUCCESS,
                User.institution_id.in_(inst_ids),
                AuditLog.created_at >= cut_from,
            )
        )
        if cut_to is not None:
            q = q.filter(AuditLog.created_at < cut_to)
        q = q.group_by(User.institution_id)
        return {int(r.tid): int(r.c) for r in q.all()}

    recent = _bucket(cut_recent, None)
    prev = _bucket(cut_prev, cut_recent)

    out: list[dict] = []
    for inst in insts:
        r = recent.get(inst.id, 0)
        p = prev.get(inst.id, 0)
        # Hesap: yüzde değişim. p=0 ise +∞ değil; özel case.
        if p == 0 and r == 0:
            change_pct = 0
            band = "no_activity"; color = "slate"; label = "iki haftadır aktivite yok"
        elif p == 0 and r > 0:
            change_pct = 100  # Önceki sıfır, şimdi var → büyüme
            band = "growing"; color = "emerald"; label = "yeni aktivite başladı"
        elif r == 0:
            change_pct = -100
            band = "sharp_drop"; color = "rose"; label = "tamamen durdu"
        else:
            change_pct = round(100 * (r - p) / p)
            if change_pct <= -50:
                band = "sharp_drop"; color = "rose"; label = f"sert düşüş %{change_pct}"
            elif change_pct <= -20:
                band = "slow_drop"; color = "amber"; label = f"yavaş düşüş %{change_pct}"
            elif change_pct >= 20:
                band = "growing"; color = "emerald"; label = f"büyüme %+{change_pct}"
            else:
                band = "stable"; color = "slate"; label = f"sabit %{change_pct:+d}"
        out.append({
            "institution_id": inst.id,
            "institution_name": inst.name,
            "plan": inst.plan,
            "recent_7d": r,
            "previous_7d": p,
            "change_pct": change_pct,
            "band": band,
            "color": color,
            "label": label,
            "detail_url": f"/admin/revenue/institutions/{inst.id}",
        })

    # Önce en kötü düşüş, sonra yavaş düşüş, sonra sabit, sonra büyüme
    band_order = {"sharp_drop": 0, "slow_drop": 1, "no_activity": 2,
                  "stable": 3, "growing": 4}
    out.sort(key=lambda r: (band_order.get(r["band"], 9), r["change_pct"]))
    return out


def _is_paid_plan(plan: str | None) -> bool:
    if not plan:
        return False
    try:
        from app.services.plans import PLAN_CATALOG
    except ImportError:
        return False
    info = PLAN_CATALOG.get(plan)
    if info is None:
        return False
    return (getattr(info, "price_monthly_try", 0) or 0) > 0


def plan_activity_matrix(db: Session, *, active_days: int = 14) -> dict:
    """4-quadrant tablo: plan (ödeyen/free) × aktivite (aktif/pasif).

    • Ödeyen × Aktif    = champion (referans iste)
    • Ödeyen × Pasif    = KRİTİK (terk riski, ödüyor ama kullanmıyor)
    • Free × Aktif      = upgrade adayı
    • Free × Pasif      = ihmal/yeniden aktivasyon

    Kurum başına: yetkilinin (admin/teacher) son giriş tarihine bakılır;
    `active_days` içinde girmiş = "aktif".
    """
    insts = (
        db.query(Institution)
        .filter(Institution.is_active.is_(True))
        .all()
    )
    if not insts:
        return {
            "paying_active": [], "paying_idle": [],
            "free_active": [], "free_idle": [],
            "totals": {"paying_active": 0, "paying_idle": 0,
                        "free_active": 0, "free_idle": 0, "total": 0},
            "active_days": active_days,
        }

    # institution_heartbeats'i yeniden kullan
    hbs = institution_heartbeats(db, limit=len(insts) + 100)
    hb_by_id = {h["institution_id"]: h for h in hbs}

    quads = {
        "paying_active": [], "paying_idle": [],
        "free_active": [], "free_idle": [],
    }
    for inst in insts:
        hb = hb_by_id.get(inst.id, {})
        days_since = hb.get("days_since_login")
        is_active = (days_since is not None and days_since < active_days)
        is_paying = _is_paid_plan(inst.plan)

        if is_paying and is_active:
            key = "paying_active"
        elif is_paying and not is_active:
            key = "paying_idle"
        elif not is_paying and is_active:
            key = "free_active"
        else:
            key = "free_idle"

        quads[key].append({
            "institution_id": inst.id,
            "institution_name": inst.name,
            "plan": inst.plan,
            "days_since_login": days_since,
            "label": hb.get("label", "—"),
            "band_color": hb.get("band_color", "slate"),
            "detail_url": f"/admin/revenue/institutions/{inst.id}",
        })

    # Her quadrant'ı kötüden iyiye sırala
    for k in quads:
        if "active" in k:
            quads[k].sort(key=lambda r: (r["days_since_login"] or 999))
        else:
            quads[k].sort(key=lambda r: -(r["days_since_login"] or 0))

    totals = {k: len(v) for k, v in quads.items()}
    totals["total"] = sum(totals.values())
    return {**quads, "totals": totals, "active_days": active_days}


# ---------------------------- Faz D: Oturum derinliği (Sprint 3) ----------------------------


def session_duration_distribution(db: Session, *, days: int = 30) -> dict:
    """Son N gün içinde sonlanmış oturumların süre dağılımı.

    `ActiveSession.last_seen_at - login_at` üzerinden hesap. Aktif (terminated_at
    NULL) olanlar dahil edilmez — süreleri kesin değil. Bantlar:
      < 1 dk     = "açtı kapattı" (zayıf ilgi)
      1-5 dk     = kısa
      5-15 dk    = orta
      15-30 dk   = uzun
      > 30 dk    = "çalışıyor" (yoğun kullanım)
    """
    cutoff = _now() - timedelta(days=days)
    rows = (
        db.query(ActiveSession.login_at, ActiveSession.last_seen_at)
        .filter(
            ActiveSession.terminated_at.isnot(None),
            ActiveSession.terminated_at >= cutoff,
        )
        .all()
    )
    durations: list[float] = []  # dakika
    for login_at, last_seen in rows:
        if login_at is None or last_seen is None:
            continue
        la = _aware(login_at); ls = _aware(last_seen)
        secs = (ls - la).total_seconds()
        if secs < 0 or secs > 24 * 3600:
            continue
        durations.append(secs / 60.0)

    if not durations:
        return {
            "count": 0, "avg_min": 0, "median_min": 0,
            "under_1min": 0, "over_30min": 0,
            "bands": {"under_1": 0, "min_1_5": 0, "min_5_15": 0,
                       "min_15_30": 0, "over_30": 0},
            "days_window": days,
        }
    durations.sort()
    n = len(durations)
    avg_min = round(sum(durations) / n, 1)
    median_min = round(durations[n // 2], 1)
    bands = {
        "under_1": sum(1 for d in durations if d < 1),
        "min_1_5": sum(1 for d in durations if 1 <= d < 5),
        "min_5_15": sum(1 for d in durations if 5 <= d < 15),
        "min_15_30": sum(1 for d in durations if 15 <= d < 30),
        "over_30": sum(1 for d in durations if d >= 30),
    }
    return {
        "count": n,
        "avg_min": avg_min,
        "median_min": median_min,
        "under_1min": bands["under_1"],
        "under_1_pct": round(100 * bands["under_1"] / n),
        "over_30min": bands["over_30"],
        "over_30_pct": round(100 * bands["over_30"] / n),
        "bands": bands,
        "days_window": days,
    }


def teacher_student_ratios(db: Session, *, active_days: int = 14) -> list[dict]:
    """Kurum başına aktif öğretmen ↔ aktif öğrenci oranı.

    "Kurum gerçekten kullanıyor mu" göstergesi: öğretmen başına aktif öğrenci
    sayısı düşükse öğretmenler öğrencilerini sisteme almıyor demektir.
    """
    cutoff = _now() - timedelta(days=active_days)
    # Aktif kullanıcılar — son N günde giriş yapanlar
    active_rows = (
        db.query(User.id, User.role, User.institution_id)
        .join(AuditLog, AuditLog.actor_id == User.id)
        .filter(
            AuditLog.action == AuditAction.LOGIN_SUCCESS,
            AuditLog.created_at >= cutoff,
            User.institution_id.isnot(None),
            User.role.in_([UserRole.TEACHER, UserRole.STUDENT]),
        )
        .distinct()
        .all()
    )
    by_inst: dict[int, dict] = {}
    for uid, role, inst_id in active_rows:
        bucket = by_inst.setdefault(int(inst_id),
                                     {"teachers": 0, "students": 0})
        if role == UserRole.TEACHER:
            bucket["teachers"] += 1
        else:
            bucket["students"] += 1

    insts = (
        db.query(Institution)
        .filter(Institution.id.in_(by_inst.keys()))
        .all()
    )
    out: list[dict] = []
    for inst in insts:
        b = by_inst[inst.id]
        t = b["teachers"]
        s = b["students"]
        ratio = round(s / t, 1) if t > 0 else None
        if ratio is None:
            band = "no_teacher"; color = "slate"; label = "aktif öğretmen yok"
        elif ratio >= 5:
            band = "high"; color = "emerald"; label = f"{ratio} öğr/öğret"
        elif ratio >= 2:
            band = "medium"; color = "amber"; label = f"{ratio} öğr/öğret"
        else:
            band = "low"; color = "rose"; label = f"sadece {ratio} öğr/öğret"
        out.append({
            "institution_id": inst.id,
            "institution_name": inst.name,
            "plan": inst.plan,
            "active_teachers": t,
            "active_students": s,
            "ratio": ratio,
            "band": band,
            "color": color,
            "label": label,
            "detail_url": f"/admin/revenue/institutions/{inst.id}",
        })
    band_order = {"low": 0, "no_teacher": 1, "medium": 2, "high": 3}
    out.sort(key=lambda r: (band_order.get(r["band"], 9), -(r["ratio"] or 0)))
    return out


def power_users(db: Session, *, days: int = 30, top: int = 10) -> dict:
    """Son N gün'de en aktif top N + en sessiz aktif bottom N kullanıcılar.

    "Aktif" = en az 1 login yapmış. Sıralama: distinct login günü sayısı.
    Power = top, çoğunlukla referans/case study adayı.
    Bottom = sessiz aktif, "intervention" listesi.
    """
    cutoff = _now() - timedelta(days=days)
    rows = (
        db.query(AuditLog.actor_id, AuditLog.created_at)
        .filter(
            AuditLog.action == AuditAction.LOGIN_SUCCESS,
            AuditLog.actor_id.isnot(None),
            AuditLog.created_at >= cutoff,
        )
        .all()
    )
    by_user: dict[int, set[str]] = {}
    for uid, ca in rows:
        ts = _aware(ca)
        if ts is None:
            continue
        by_user.setdefault(int(uid), set()).add(ts.date().isoformat())

    if not by_user:
        return {"top": [], "bottom": [], "days_window": days}

    user_ids = list(by_user.keys())
    users = db.query(User).filter(User.id.in_(user_ids)).all()
    inst_ids = {u.institution_id for u in users if u.institution_id}
    inst_map = {}
    if inst_ids:
        inst_map = {
            i.id: i.name for i in
            db.query(Institution).filter(Institution.id.in_(inst_ids)).all()
        }
    user_map = {u.id: u for u in users}

    rows_out: list[dict] = []
    for uid, days_set in by_user.items():
        u = user_map.get(uid)
        if u is None:
            continue
        rows_out.append({
            "user_id": uid,
            "name": u.full_name or u.email,
            "email": u.email,
            "role": u.role.value if u.role else None,
            "institution_id": u.institution_id,
            "institution_name": inst_map.get(u.institution_id),
            "active_days": len(days_set),
            "activity_pct": round(100 * len(days_set) / days),
        })
    rows_out.sort(key=lambda r: -r["active_days"])
    return {
        "top": rows_out[:top],
        "bottom": rows_out[-top:][::-1],  # en az aktif öne
        "days_window": days,
        "total_active_users": len(rows_out),
    }


# ---------------------------- Faz E: Özellik benimseme (Sprint 3) ----------------------------


def _feature_event_specs() -> list[dict]:
    """Hangi domain tabloları "feature usage" sayılıyor — proxy listesi.

    Her event'in actor sütununa (ör. student_id veya invited_by_id) bağlı kullanıcının
    `institution_id`'si kuruma atfedilir. Bağımsız öğretmen (institution_id=NULL)
    altındaki olaylar bu matriste sayılmaz (yalnız kurumsal kullanım).
    """
    return [
        {"key": "task_create", "label": "Görev/Plan Oluşturma",
         "icon": "📝", "model": "Task", "ts": "created_at", "actor": "student_id"},
        {"key": "week_note", "label": "Haftalık Not",
         "icon": "📒", "model": "WeekNote", "ts": "created_at", "actor": "student_id"},
        {"key": "parent_invitation", "label": "Veli Daveti",
         "icon": "👨‍👩", "model": "ParentInvitation", "ts": "created_at", "actor": "invited_by_id"},
        {"key": "pomodoro", "label": "Pomodoro Çalışma",
         "icon": "🍅", "model": "PomodoroSession", "ts": "started_at", "actor": "student_id"},
        {"key": "review", "label": "Tekrar (SR)",
         "icon": "🧠", "model": "ReviewLog", "ts": "reviewed_at", "actor": "student_id"},
    ]


def _feature_usage_counts(db: Session, *, days: int = 30) -> dict[str, dict]:
    """Her feature için son N gün'de: toplam event + distinct kurum + distinct user."""
    from app.models import (
        ParentInvitation,
        PomodoroSession,
        ReviewLog,
        Task,
        WeekNote,
    )
    cutoff = _now() - timedelta(days=days)
    model_map = {
        "Task": Task, "WeekNote": WeekNote,
        "ParentInvitation": ParentInvitation,
        "PomodoroSession": PomodoroSession,
        "ReviewLog": ReviewLog,
    }
    out: dict[str, dict] = {}
    for spec in _feature_event_specs():
        Model = model_map.get(spec["model"])
        if Model is None:
            continue
        ts_col = getattr(Model, spec["ts"], None)
        actor_col = getattr(Model, spec["actor"], None)
        if ts_col is None or actor_col is None:
            continue
        try:
            rows = (
                db.query(actor_col, User.institution_id)
                .join(User, User.id == actor_col)
                .filter(
                    ts_col >= cutoff,
                    User.institution_id.isnot(None),
                )
                .all()
            )
        except Exception:
            logger.exception("feature_usage_counts fail key=%s", spec["key"])
            continue
        total = len(rows)
        inst_ids = {int(r[1]) for r in rows if r[1] is not None}
        user_ids = {int(r[0]) for r in rows if r[0] is not None}
        out[spec["key"]] = {
            "label": spec["label"],
            "icon": spec["icon"],
            "total_events": total,
            "distinct_institutions": len(inst_ids),
            "distinct_users": len(user_ids),
            "institution_ids": inst_ids,
        }
    return out


def feature_popularity(db: Session, *, days: int = 30) -> list[dict]:
    """Son N gün'de feature popülerlik sıralaması."""
    counts = _feature_usage_counts(db, days=days)
    out = []
    for key, c in counts.items():
        out.append({
            "key": key,
            "label": c["label"],
            "icon": c["icon"],
            "total_events": c["total_events"],
            "distinct_institutions": c["distinct_institutions"],
            "distinct_users": c["distinct_users"],
        })
    out.sort(key=lambda r: -r["total_events"])
    return out


def feature_usage_matrix(db: Session, *, days: int = 30, top: int = 30) -> dict:
    """Kurum × Feature matrisi — son N gün.

    Hücre = bool (kullandı/kullanmadı) + opsiyonel sayı.
    En aktif top N kurumu göster.
    """
    cutoff = _now() - timedelta(days=days)
    counts = _feature_usage_counts(db, days=days)
    feature_keys = list(counts.keys())

    # En aktif kurumlar — toplam aktif login sayısı bazlı
    inst_active = (
        db.query(
            User.institution_id,
            func.count(func.distinct(User.id)).label("c"),
        )
        .join(AuditLog, AuditLog.actor_id == User.id)
        .filter(
            AuditLog.action == AuditAction.LOGIN_SUCCESS,
            AuditLog.created_at >= cutoff,
            User.institution_id.isnot(None),
        )
        .group_by(User.institution_id)
        .order_by(desc("c"))
        .limit(top)
        .all()
    )
    inst_ids = [int(r.institution_id) for r in inst_active]
    if not inst_ids:
        return {
            "features": [], "rows": [], "days_window": days,
        }

    inst_map = {
        i.id: i for i in
        db.query(Institution).filter(Institution.id.in_(inst_ids)).all()
    }

    rows: list[dict] = []
    for iid in inst_ids:
        inst = inst_map.get(iid)
        if inst is None:
            continue
        row = {
            "institution_id": iid,
            "institution_name": inst.name,
            "plan": inst.plan,
            "cells": [],
            "detail_url": f"/admin/revenue/institutions/{iid}",
        }
        adopted = 0
        for fkey in feature_keys:
            fc = counts[fkey]
            used = iid in fc["institution_ids"]
            row["cells"].append({"key": fkey, "used": used})
            if used:
                adopted += 1
        row["adopted_count"] = adopted
        row["adoption_pct"] = round(100 * adopted / len(feature_keys)) if feature_keys else 0
        rows.append(row)

    rows.sort(key=lambda r: -r["adopted_count"])

    features = [
        {"key": k, "label": counts[k]["label"], "icon": counts[k]["icon"]}
        for k in feature_keys
    ]
    return {
        "features": features,
        "rows": rows,
        "days_window": days,
    }


def onboarding_milestones(db: Session, *, days: int = 14) -> list[dict]:
    """Son N gün'de kayıt olmuş kurumların kritik milestone'larını tamamlama durumu.

    Milestone listesi:
      1. Yetkili ilk giriş yaptı (login_success)
      2. Öğretmen davet edildi (Invitation kullanılmış)
      3. Öğrenci eklendi (User role=student created)
      4. İlk plan/görev oluşturuldu (Task)
      5. Veli daveti gönderildi (ParentInvitation)
    """
    from app.models import Invitation, ParentInvitation, Task
    now = _now()
    cutoff = now - timedelta(days=days)
    insts = (
        db.query(Institution)
        .filter(
            Institution.is_active.is_(True),
            Institution.created_at >= cutoff,
        )
        .order_by(Institution.created_at)
        .all()
    )
    if not insts:
        return []

    inst_ids = [i.id for i in insts]

    # Milestone 1 — yetkili giriş
    admin_login = (
        db.query(User.institution_id)
        .join(AuditLog, AuditLog.actor_id == User.id)
        .filter(
            AuditLog.action == AuditAction.LOGIN_SUCCESS,
            User.institution_id.in_(inst_ids),
            User.role == UserRole.INSTITUTION_ADMIN,
        )
        .distinct()
        .all()
    )
    m1_done = {int(r.institution_id) for r in admin_login}

    # Milestone 2 — öğretmen davet edildi (Invitation kullanıldı)
    try:
        inv_rows = (
            db.query(Invitation.institution_id)
            .filter(
                Invitation.institution_id.in_(inst_ids),
                Invitation.role == UserRole.TEACHER,
            )
            .distinct()
            .all()
        )
        m2_done = {int(r.institution_id) for r in inv_rows}
    except Exception:
        m2_done = set()

    # Milestone 3 — öğrenci eklendi
    student_rows = (
        db.query(User.institution_id)
        .filter(
            User.institution_id.in_(inst_ids),
            User.role == UserRole.STUDENT,
        )
        .distinct()
        .all()
    )
    m3_done = {int(r.institution_id) for r in student_rows}

    # Milestone 4 — ilk task oluşturuldu (öğrenci'nin kurumu üzerinden)
    task_rows = (
        db.query(User.institution_id)
        .join(Task, Task.student_id == User.id)
        .filter(User.institution_id.in_(inst_ids))
        .distinct()
        .all()
    )
    m4_done = {int(r.institution_id) for r in task_rows}

    # Milestone 5 — veli davet edildi (davet eden kullanıcı üzerinden)
    try:
        parent_rows = (
            db.query(User.institution_id)
            .join(ParentInvitation, ParentInvitation.invited_by_id == User.id)
            .filter(User.institution_id.in_(inst_ids))
            .distinct()
            .all()
        )
        m5_done = {int(r.institution_id) for r in parent_rows}
    except Exception:
        m5_done = set()

    out: list[dict] = []
    for inst in insts:
        steps = [
            ("admin_login", "🔑 Yetkili giriş", inst.id in m1_done),
            ("teacher_invite", "🎓 Öğretmen davet", inst.id in m2_done),
            ("student_added", "🎒 Öğrenci eklendi", inst.id in m3_done),
            ("first_task", "📝 İlk görev", inst.id in m4_done),
            ("parent_invite", "👨‍👩 Veli davet", inst.id in m5_done),
        ]
        done_count = sum(1 for _, _, d in steps if d)
        age_days = (now - _aware(inst.created_at)).days if inst.created_at else 0
        out.append({
            "institution_id": inst.id,
            "institution_name": inst.name,
            "plan": inst.plan,
            "age_days": age_days,
            "milestones": [
                {"key": k, "label": lbl, "done": d} for k, lbl, d in steps
            ],
            "done_count": done_count,
            "total_count": len(steps),
            "completion_pct": round(100 * done_count / len(steps)),
            "detail_url": f"/admin/revenue/institutions/{inst.id}",
        })

    # Tamamlanmamış olanlar üstte (en az done önce)
    out.sort(key=lambda r: (r["done_count"], -r["age_days"]))
    return out


# ---------------------------- Faz H: Benchmark (Sprint 4) ----------------------------


def plan_benchmark_table(db: Session, *, active_days: int = 30) -> list[dict]:
    """Her plan kodu için ortalama metrikler.

    Yeni kurum için "hedef belirleme" referansı. Her plan satırı:
      • Kurum sayısı (aktif)
      • Ortalama aktif öğretmen (son N gün)
      • Ortalama aktif öğrenci
      • Ortalama feature adopsiyonu (5 feature'dan kaçı kullanılıyor)
      • Ortalama oturum süresi (dakika)
    """
    cutoff = _now() - timedelta(days=active_days)

    # Tüm aktif kurumlar
    insts = (
        db.query(Institution)
        .filter(Institution.is_active.is_(True))
        .all()
    )
    if not insts:
        return []

    inst_by_plan: dict[str, list[Institution]] = defaultdict(list)
    for i in insts:
        inst_by_plan[i.plan or "free"].append(i)

    inst_ids = [i.id for i in insts]

    # Per-inst aktif öğretmen + öğrenci sayıları
    active_rows = (
        db.query(User.institution_id, User.role)
        .join(AuditLog, AuditLog.actor_id == User.id)
        .filter(
            AuditLog.action == AuditAction.LOGIN_SUCCESS,
            AuditLog.created_at >= cutoff,
            User.institution_id.in_(inst_ids),
            User.role.in_([UserRole.TEACHER, UserRole.STUDENT]),
        )
        .distinct()
        .all()
    )
    per_inst: dict[int, dict] = defaultdict(lambda: {"teachers": 0, "students": 0})
    for iid, role in active_rows:
        if role == UserRole.TEACHER:
            per_inst[int(iid)]["teachers"] += 1
        else:
            per_inst[int(iid)]["students"] += 1

    # Feature adopsiyon — feature_usage_matrix sonucundan al
    fm = feature_usage_matrix(db, days=active_days, top=len(insts) + 100)
    inst_adoption = {r["institution_id"]: r["adopted_count"] for r in fm["rows"]}
    feature_total = len(fm["features"]) or 1

    # Oturum süresi per inst (ActiveSession üzerinden)
    sess_rows = (
        db.query(
            User.institution_id,
            ActiveSession.login_at,
            ActiveSession.last_seen_at,
        )
        .join(User, User.id == ActiveSession.user_id)
        .filter(
            ActiveSession.terminated_at.isnot(None),
            ActiveSession.terminated_at >= cutoff,
            User.institution_id.in_(inst_ids),
        )
        .all()
    )
    per_inst_sess: dict[int, list[float]] = defaultdict(list)
    for iid, la, ls in sess_rows:
        if la is None or ls is None:
            continue
        secs = (_aware(ls) - _aware(la)).total_seconds()
        if 0 <= secs <= 24 * 3600:
            per_inst_sess[int(iid)].append(secs / 60.0)

    out: list[dict] = []
    for plan_code, plan_insts in inst_by_plan.items():
        count = len(plan_insts)
        if count == 0:
            continue
        avg_t = sum(per_inst[i.id]["teachers"] for i in plan_insts) / count
        avg_s = sum(per_inst[i.id]["students"] for i in plan_insts) / count
        avg_adopt = sum(inst_adoption.get(i.id, 0) for i in plan_insts) / count
        # Oturum süresi: tüm kurumların tüm oturumları → ortalamasının ortalaması
        all_sess_avgs = []
        for i in plan_insts:
            durs = per_inst_sess.get(i.id, [])
            if durs:
                all_sess_avgs.append(sum(durs) / len(durs))
        avg_sess_min = round(sum(all_sess_avgs) / len(all_sess_avgs), 1) if all_sess_avgs else 0

        try:
            from app.services.plans import PLAN_CATALOG
            plan_info = PLAN_CATALOG.get(plan_code)
            plan_label = getattr(plan_info, "label", plan_code) if plan_info else plan_code
            plan_price = int(getattr(plan_info, "price_monthly_try", 0) or 0) if plan_info else 0
        except Exception:
            plan_label = plan_code
            plan_price = 0

        out.append({
            "plan": plan_code,
            "plan_label": plan_label,
            "monthly_price": plan_price,
            "institution_count": count,
            "avg_active_teachers": round(avg_t, 1),
            "avg_active_students": round(avg_s, 1),
            "avg_feature_adoption": round(avg_adopt, 1),
            "avg_feature_adoption_pct": round(100 * avg_adopt / feature_total),
            "feature_total": feature_total,
            "avg_session_min": avg_sess_min,
        })
    # Ücretli planlar üstte, fiyata göre azalan
    out.sort(key=lambda r: (-r["monthly_price"], -r["institution_count"]))
    return out


def champion_institutions(db: Session, *, top_pct: int = 10) -> list[dict]:
    """En üst %N kurum — birleşik skor.

    Skor = 40% recent_activity_density (son 7g aktif gün/kişi)
         + 30% feature_adoption (kullanılan feature %)
         + 20% paying_age_months (ödeyen + 6+ ay = yüksek)
         + 10% teacher_student_ratio (yüksek = iyi)

    En üst %top_pct (varsayılan 10) kurumlar "champion" sayılır;
    referans/case study/yıllık plan adayı.
    """
    insts = (
        db.query(Institution)
        .filter(Institution.is_active.is_(True))
        .all()
    )
    if not insts:
        return []

    now = _now()
    inst_ids = [i.id for i in insts]

    # Son 7g'de distinct aktif user başı login günü ortalaması
    cutoff_7d = now - timedelta(days=7)
    activity_rows = (
        db.query(User.institution_id, User.id, AuditLog.created_at)
        .join(AuditLog, AuditLog.actor_id == User.id)
        .filter(
            AuditLog.action == AuditAction.LOGIN_SUCCESS,
            AuditLog.created_at >= cutoff_7d,
            User.institution_id.in_(inst_ids),
        )
        .all()
    )
    inst_user_days: dict[int, dict[int, set[str]]] = defaultdict(lambda: defaultdict(set))
    for iid, uid, ca in activity_rows:
        ts = _aware(ca)
        if ts is None:
            continue
        inst_user_days[int(iid)][int(uid)].add(ts.date().isoformat())

    # Feature adoption
    fm = feature_usage_matrix(db, days=30, top=len(insts) + 100)
    feature_total = len(fm["features"]) or 1
    adopt_map = {r["institution_id"]: r["adopted_count"] for r in fm["rows"]}

    # Aktif öğretmen/öğrenci oranı
    ratios = teacher_student_ratios(db, active_days=14)
    ratio_map = {r["institution_id"]: (r["ratio"] or 0) for r in ratios}

    rows: list[dict] = []
    for inst in insts:
        user_days = inst_user_days.get(inst.id, {})
        active_user_count = len(user_days)
        total_login_days = sum(len(d) for d in user_days.values())
        # Density: ortalama gün sayısı kişi başı (0-7)
        density = (total_login_days / active_user_count) if active_user_count > 0 else 0
        density_norm = min(density / 7.0, 1.0)

        adopt = adopt_map.get(inst.id, 0)
        adopt_pct = adopt / feature_total

        is_paying = _is_paid_plan(inst.plan)
        age_months = ((now - _aware(inst.created_at)).days / 30.0) if inst.created_at else 0
        age_score = min(age_months / 6.0, 1.0) if is_paying else 0

        ratio = ratio_map.get(inst.id, 0)
        ratio_norm = min(ratio / 5.0, 1.0) if ratio else 0

        score = (
            0.40 * density_norm +
            0.30 * adopt_pct +
            0.20 * age_score +
            0.10 * ratio_norm
        ) * 100

        rows.append({
            "institution_id": inst.id,
            "institution_name": inst.name,
            "plan": inst.plan,
            "is_paying": is_paying,
            "score": round(score, 1),
            "density": round(density, 1),
            "active_user_count": active_user_count,
            "feature_adoption": adopt,
            "feature_total": feature_total,
            "age_months": round(age_months, 1),
            "student_teacher_ratio": ratio,
            "detail_url": f"/admin/revenue/institutions/{inst.id}",
        })

    rows.sort(key=lambda r: -r["score"])
    n_champ = max(1, len(rows) * top_pct // 100)
    champions = rows[:n_champ]
    for r in champions:
        r["is_champion"] = True
    return champions


# ====================================================================
# SPRINT 5 — Bağımsız öğretmen (Solo) paralel fonksiyonlar
# Owner-pattern: bağımsız öğretmen = 1 kişilik tenant. Aşağıdaki tüm
# fonksiyonlar `solo_*` veya `combined_*` prefix'i ile kurum sürümlerini
# tamamlar.
# ====================================================================


def _solo_actor_universe(db: Session, teacher_ids: list[int]) -> dict[int, list[int]]:
    """Her bağımsız öğretmen için 'aktör evreni' = öğretmen + öğrencileri.

    Heartbeat, decay rate gibi metriklerde 'kurum kullanıcıları' yerine
    bu evren kullanılır.
    """
    if not teacher_ids:
        return {}
    students = _solo_student_ids(db, teacher_ids)
    return {tid: [tid] + students.get(tid, []) for tid in teacher_ids}


def solo_decay_rates(db: Session, *, limit: int = 200) -> list[dict]:
    """Bağımsız öğretmenler için son 7g vs önceki 7g birleşik aktivite eğimi.

    Aktivite = öğretmen + öğrencilerinin distinct login günü (1g = 1 nokta).
    """
    now = _now()
    cut_recent = now - timedelta(days=7)
    cut_prev = now - timedelta(days=14)
    teachers = _solo_teachers(db, limit=limit)
    if not teachers:
        return []
    teacher_ids = [t.id for t in teachers]
    universe = _solo_actor_universe(db, teacher_ids)
    # actor_id → teacher_id eşlemesi
    actor_to_teacher: dict[int, int] = {}
    for tid, uids in universe.items():
        for uid in uids:
            actor_to_teacher[uid] = tid
    all_actors = list(actor_to_teacher.keys())
    if not all_actors:
        return []

    def _bucket(cut_from, cut_to):
        rows = (
            db.query(AuditLog.actor_id)
            .filter(
                AuditLog.action == AuditAction.LOGIN_SUCCESS,
                AuditLog.actor_id.in_(all_actors),
                AuditLog.created_at >= cut_from,
            )
        )
        if cut_to is not None:
            rows = rows.filter(AuditLog.created_at < cut_to)
        per_teacher: dict[int, set[int]] = defaultdict(set)
        for (uid,) in rows.all():
            tid = actor_to_teacher.get(int(uid))
            if tid is not None:
                per_teacher[tid].add(int(uid))
        return {tid: len(s) for tid, s in per_teacher.items()}

    recent = _bucket(cut_recent, None)
    prev = _bucket(cut_prev, cut_recent)

    out: list[dict] = []
    for t in teachers:
        r = recent.get(t.id, 0)
        p = prev.get(t.id, 0)
        if p == 0 and r == 0:
            change_pct = 0
            band = "no_activity"; color = "slate"; label = "iki haftadır aktivite yok"
        elif p == 0 and r > 0:
            change_pct = 100
            band = "growing"; color = "emerald"; label = "yeni aktivite başladı"
        elif r == 0:
            change_pct = -100
            band = "sharp_drop"; color = "rose"; label = "tamamen durdu"
        else:
            change_pct = round(100 * (r - p) / p)
            if change_pct <= -50:
                band = "sharp_drop"; color = "rose"; label = f"sert düşüş %{change_pct}"
            elif change_pct <= -20:
                band = "slow_drop"; color = "amber"; label = f"yavaş düşüş %{change_pct}"
            elif change_pct >= 20:
                band = "growing"; color = "emerald"; label = f"büyüme %+{change_pct}"
            else:
                band = "stable"; color = "slate"; label = f"sabit %{change_pct:+d}"
        out.append({
            "owner_type": "solo",
            "owner_id": t.id,
            "institution_id": None,
            "institution_name": _solo_owner_label(t),
            "plan": _solo_plan(t),
            "recent_7d": r,
            "previous_7d": p,
            "change_pct": change_pct,
            "band": band,
            "color": color,
            "label": label,
            "detail_url": f"/admin/revenue/users/{t.id}",
        })
    band_order = {"sharp_drop": 0, "slow_drop": 1, "no_activity": 2,
                  "stable": 3, "growing": 4}
    out.sort(key=lambda r: (band_order.get(r["band"], 9), r["change_pct"]))
    return out


def combined_decay_rates(db: Session, *, segment: str = "all",
                           limit: int = 200) -> list[dict]:
    if segment == "institution":
        out = institution_decay_rates(db, limit=limit)
        for r in out:
            r.setdefault("owner_type", "institution")
            r.setdefault("owner_id", r.get("institution_id"))
        return out
    if segment == "solo":
        return solo_decay_rates(db, limit=limit)
    insts = institution_decay_rates(db, limit=limit)
    for r in insts:
        r.setdefault("owner_type", "institution")
        r.setdefault("owner_id", r.get("institution_id"))
    solos = solo_decay_rates(db, limit=limit)
    merged = insts + solos
    band_order = {"sharp_drop": 0, "slow_drop": 1, "no_activity": 2,
                  "stable": 3, "growing": 4}
    merged.sort(key=lambda r: (band_order.get(r["band"], 9), r["change_pct"]))
    return merged


def solo_plan_activity_matrix(db: Session, *, active_days: int = 14) -> dict:
    """Bağımsız öğretmenler için 4-quadrant plan × aktivite tablosu.

    Aktiflik ölçütü: öğretmenin kendi son girişi `active_days` içindeyse aktif
    (öğrenci aktivitesi sayılmaz — burada amaç öğretmenin platformla
    ilişkisini ölçmek).
    """
    teachers = _solo_teachers(db)
    if not teachers:
        return {
            "paying_active": [], "paying_idle": [],
            "free_active": [], "free_idle": [],
            "totals": {"paying_active": 0, "paying_idle": 0,
                        "free_active": 0, "free_idle": 0, "total": 0},
            "active_days": active_days,
        }
    hbs = solo_heartbeats(db, limit=len(teachers) + 100)
    hb_by_id = {h["owner_id"]: h for h in hbs}

    quads = {"paying_active": [], "paying_idle": [],
              "free_active": [], "free_idle": []}
    for t in teachers:
        hb = hb_by_id.get(t.id, {})
        days_since = hb.get("days_since_login")
        is_active = (days_since is not None and days_since < active_days)
        is_paying = _is_paid_plan(t.plan)
        if is_paying and is_active:
            key = "paying_active"
        elif is_paying and not is_active:
            key = "paying_idle"
        elif not is_paying and is_active:
            key = "free_active"
        else:
            key = "free_idle"
        quads[key].append({
            "owner_type": "solo",
            "owner_id": t.id,
            "institution_id": None,
            "institution_name": _solo_owner_label(t),
            "plan": _solo_plan(t),
            "days_since_login": days_since,
            "label": hb.get("label", "—"),
            "band_color": hb.get("band_color", "slate"),
            "detail_url": f"/admin/revenue/users/{t.id}",
        })
    for k in quads:
        if "active" in k:
            quads[k].sort(key=lambda r: (r["days_since_login"] or 999))
        else:
            quads[k].sort(key=lambda r: -(r["days_since_login"] or 0))
    totals = {k: len(v) for k, v in quads.items()}
    totals["total"] = sum(totals.values())
    return {**quads, "totals": totals, "active_days": active_days}


def combined_plan_activity_matrix(db: Session, *, segment: str = "all",
                                     active_days: int = 14) -> dict:
    if segment == "institution":
        m = plan_activity_matrix(db, active_days=active_days)
        for k in ("paying_active", "paying_idle", "free_active", "free_idle"):
            for r in m.get(k, []):
                r.setdefault("owner_type", "institution")
                r.setdefault("owner_id", r.get("institution_id"))
        return m
    if segment == "solo":
        return solo_plan_activity_matrix(db, active_days=active_days)
    inst_m = plan_activity_matrix(db, active_days=active_days)
    solo_m = solo_plan_activity_matrix(db, active_days=active_days)
    out = {}
    for k in ("paying_active", "paying_idle", "free_active", "free_idle"):
        i_rows = inst_m.get(k, [])
        for r in i_rows:
            r.setdefault("owner_type", "institution")
            r.setdefault("owner_id", r.get("institution_id"))
        out[k] = i_rows + solo_m.get(k, [])
    totals = {k: len(v) for k, v in out.items()}
    totals["total"] = sum(totals.values())
    out["totals"] = totals
    out["active_days"] = active_days
    return out


def solo_silent_teachers(db: Session, *, days: int = 7) -> list[dict]:
    """Son N günde hiç giriş yapmamış (kendisi + öğrencileri) bağımsız öğretmenler."""
    hbs = solo_heartbeats(db)
    out = []
    for h in hbs:
        d = h.get("days_since_login")
        if d is None or d >= days:
            out.append({
                "owner_type": "solo",
                "owner_id": h["owner_id"],
                "tenant_id": h["owner_id"],
                "tenant_name": h["institution_name"],
                "plan": h["plan"],
                "days_since_login": d,
                "detail_url": h["detail_url"],
            })
    return out


def combined_silent(db: Session, *, segment: str = "all", days: int = 7) -> list[dict]:
    if segment == "institution":
        rows = silent_tenants(db, days=days)
        for r in rows:
            r.setdefault("owner_type", "institution")
            r.setdefault("owner_id", r.get("tenant_id"))
        return rows
    if segment == "solo":
        return solo_silent_teachers(db, days=days)
    insts = silent_tenants(db, days=days)
    for r in insts:
        r.setdefault("owner_type", "institution")
        r.setdefault("owner_id", r.get("tenant_id"))
    return insts + solo_silent_teachers(db, days=days)


def solo_teacher_student_ratios(db: Session, *, active_days: int = 14) -> list[dict]:
    """Bağımsız öğretmen için aktif öğrenci sayısı.

    Bağımsız öğretmende öğretmen sayısı sabit = 1, oran = aktif_öğrenci ÷ 1.
    Kurumdaki ratio gibi yorumlanmaz; salt aktif öğrenci sayısı baskındır.
    Bantlar: 0 öğrenci → 'no_students'; 1-2 → 'low'; 3-9 → 'medium'; 10+ → 'high'.
    """
    cutoff = _now() - timedelta(days=active_days)
    teachers = _solo_teachers(db)
    if not teachers:
        return []
    teacher_ids = [t.id for t in teachers]
    stu_map = _solo_student_ids(db, teacher_ids)
    all_stu_ids = [s for sids in stu_map.values() for s in sids]
    if all_stu_ids:
        active_rows = (
            db.query(AuditLog.actor_id)
            .filter(
                AuditLog.action == AuditAction.LOGIN_SUCCESS,
                AuditLog.actor_id.in_(all_stu_ids),
                AuditLog.created_at >= cutoff,
            )
            .distinct()
            .all()
        )
        active_stu = {int(r[0]) for r in active_rows}
    else:
        active_stu = set()

    out: list[dict] = []
    for t in teachers:
        sids = stu_map.get(t.id, [])
        active = sum(1 for s in sids if s in active_stu)
        ratio = float(active)  # öğretmen=1, ratio = aktif_öğrenci/1
        if active == 0:
            band = "no_students"; color = "slate"
            label = "aktif öğrenci yok" if not sids else f"{len(sids)} öğr. pasif"
        elif active >= 10:
            band = "high"; color = "emerald"; label = f"{active} aktif öğrenci"
        elif active >= 3:
            band = "medium"; color = "amber"; label = f"{active} aktif öğrenci"
        else:
            band = "low"; color = "rose"; label = f"sadece {active} aktif"
        out.append({
            "owner_type": "solo",
            "owner_id": t.id,
            "institution_id": None,
            "institution_name": _solo_owner_label(t),
            "plan": _solo_plan(t),
            "active_teachers": 1,  # bağımsız → her zaman 1 öğretmen
            "active_students": active,
            "total_students": len(sids),
            "ratio": ratio,
            "band": band,
            "color": color,
            "label": label,
            "detail_url": f"/admin/revenue/users/{t.id}",
        })
    band_order = {"low": 0, "no_students": 1, "medium": 2, "high": 3}
    out.sort(key=lambda r: (band_order.get(r["band"], 9), -(r["ratio"] or 0)))
    return out


def combined_teacher_student_ratios(db: Session, *, segment: str = "all",
                                       active_days: int = 14) -> list[dict]:
    if segment == "institution":
        rows = teacher_student_ratios(db, active_days=active_days)
        for r in rows:
            r.setdefault("owner_type", "institution")
            r.setdefault("owner_id", r.get("institution_id"))
        return rows
    if segment == "solo":
        return solo_teacher_student_ratios(db, active_days=active_days)
    insts = teacher_student_ratios(db, active_days=active_days)
    for r in insts:
        r.setdefault("owner_type", "institution")
        r.setdefault("owner_id", r.get("institution_id"))
    return insts + solo_teacher_student_ratios(db, active_days=active_days)


def solo_feature_usage_matrix(db: Session, *, days: int = 30, top: int = 30) -> dict:
    """Bağımsız öğretmen × Özellik matrisi.

    Her feature event'in actor_id'si üzerinden ilişkili öğretmen tespit edilir:
      - student_id sütunları → User.teacher_id (öğrenci'nin koçu)
      - invited_by_id → ParentInvitation'ı gönderen öğretmen
    Yalnız `institution_id IS NULL` öğrenciler dahil edilir.
    """
    from app.models import (
        ParentInvitation,
        PomodoroSession,
        ReviewLog,
        Task,
        WeekNote,
    )
    cutoff = _now() - timedelta(days=days)
    model_map = {
        "Task": Task, "WeekNote": WeekNote,
        "ParentInvitation": ParentInvitation,
        "PomodoroSession": PomodoroSession,
        "ReviewLog": ReviewLog,
    }
    teachers = _solo_teachers(db, limit=top + 200)
    teacher_ids = {t.id for t in teachers}
    if not teacher_ids:
        return {"features": [], "rows": [], "days_window": days}

    feature_use: dict[str, dict] = {}
    for spec in _feature_event_specs():
        Model = model_map.get(spec["model"])
        if Model is None:
            continue
        ts_col = getattr(Model, spec["ts"], None)
        actor_col = getattr(Model, spec["actor"], None)
        if ts_col is None or actor_col is None:
            continue
        try:
            if spec["actor"] == "invited_by_id":
                # actor doğrudan davet eden kullanıcı — onun bağımsız öğretmen olması yeter
                rows = (
                    db.query(actor_col)
                    .filter(
                        ts_col >= cutoff,
                        actor_col.in_(teacher_ids),
                    )
                    .all()
                )
                t_ids = {int(r[0]) for r in rows if r[0] is not None}
            else:
                # actor öğrenci — student.teacher_id üzerinden bağımsız öğretmen bul
                rows = (
                    db.query(User.teacher_id)
                    .join(Model, getattr(Model, spec["actor"]) == User.id)
                    .filter(
                        ts_col >= cutoff,
                        User.role == UserRole.STUDENT,
                        User.institution_id.is_(None),
                        User.teacher_id.in_(teacher_ids),
                    )
                    .all()
                )
                t_ids = {int(r[0]) for r in rows if r[0] is not None}
        except Exception:
            logger.exception("solo_feature_usage_matrix fail key=%s", spec["key"])
            continue
        feature_use[spec["key"]] = {
            "label": spec["label"],
            "icon": spec["icon"],
            "teacher_ids": t_ids,
        }
    feature_keys = list(feature_use.keys())

    # Top öğretmenler — son N gün öğrenci+kendi login sayısına göre
    universe = _solo_actor_universe(db, list(teacher_ids))
    actor_to_teacher = {uid: tid for tid, uids in universe.items() for uid in uids}
    all_actors = list(actor_to_teacher.keys())
    if all_actors:
        active_rows = (
            db.query(AuditLog.actor_id)
            .filter(
                AuditLog.action == AuditAction.LOGIN_SUCCESS,
                AuditLog.actor_id.in_(all_actors),
                AuditLog.created_at >= cutoff,
            )
            .all()
        )
        per_teacher: dict[int, int] = defaultdict(int)
        seen: set[tuple[int, int]] = set()
        for (uid,) in active_rows:
            tid = actor_to_teacher.get(int(uid))
            if tid is None:
                continue
            key = (tid, int(uid))
            if key in seen:
                continue
            seen.add(key)
            per_teacher[tid] += 1
        ordered = sorted(per_teacher.items(), key=lambda x: -x[1])[:top]
        top_ids = [tid for tid, _ in ordered]
    else:
        top_ids = [t.id for t in teachers[:top]]

    t_map = {t.id: t for t in teachers}
    rows: list[dict] = []
    for tid in top_ids:
        t = t_map.get(tid)
        if t is None:
            continue
        row = {
            "owner_type": "solo",
            "owner_id": tid,
            "institution_id": None,
            "institution_name": _solo_owner_label(t),
            "plan": _solo_plan(t),
            "cells": [],
            "detail_url": f"/admin/revenue/users/{tid}",
        }
        adopted = 0
        for fk in feature_keys:
            used = tid in feature_use[fk]["teacher_ids"]
            row["cells"].append({"key": fk, "used": used})
            if used:
                adopted += 1
        row["adopted_count"] = adopted
        row["adoption_pct"] = round(100 * adopted / len(feature_keys)) if feature_keys else 0
        rows.append(row)
    rows.sort(key=lambda r: -r["adopted_count"])
    features = [
        {"key": k, "label": feature_use[k]["label"], "icon": feature_use[k]["icon"]}
        for k in feature_keys
    ]
    return {"features": features, "rows": rows, "days_window": days}


def combined_feature_usage_matrix(db: Session, *, segment: str = "all",
                                     days: int = 30, top: int = 30) -> dict:
    if segment == "institution":
        m = feature_usage_matrix(db, days=days, top=top)
        for r in m.get("rows", []):
            r.setdefault("owner_type", "institution")
            r.setdefault("owner_id", r.get("institution_id"))
        return m
    if segment == "solo":
        return solo_feature_usage_matrix(db, days=days, top=top)
    inst_m = feature_usage_matrix(db, days=days, top=top)
    solo_m = solo_feature_usage_matrix(db, days=days, top=top)
    # Özellik listesi her ikisinde aynı (feature_specs sabit)
    features = inst_m.get("features") or solo_m.get("features", [])
    rows = []
    for r in inst_m.get("rows", []):
        r.setdefault("owner_type", "institution")
        r.setdefault("owner_id", r.get("institution_id"))
        rows.append(r)
    rows += solo_m.get("rows", [])
    rows.sort(key=lambda r: -r.get("adopted_count", 0))
    return {"features": features, "rows": rows, "days_window": days}


def solo_onboarding_milestones(db: Session, *, days: int = 14) -> list[dict]:
    """Son N günde kayıt olmuş bağımsız öğretmenlerin onboarding milestone'ları.

    4 milestone (kurumdaki 5'ten farklı — "öğretmen daveti" milestone'u yok):
      1. Yetkili (öğretmen) giriş yaptı
      2. İlk öğrenci eklendi
      3. İlk görev oluşturuldu
      4. Veli daveti gönderildi
    """
    from app.models import ParentInvitation, Task
    now = _now()
    cutoff = now - timedelta(days=days)
    teachers = (
        db.query(User)
        .filter(
            User.role == UserRole.TEACHER,
            User.institution_id.is_(None),
            User.is_active.is_(True),
            User.created_at >= cutoff,
        )
        .order_by(User.created_at)
        .all()
    )
    if not teachers:
        return []
    teacher_ids = [t.id for t in teachers]

    # Milestone 1 — öğretmenin kendi girişi
    self_login = (
        db.query(AuditLog.actor_id)
        .filter(
            AuditLog.action == AuditAction.LOGIN_SUCCESS,
            AuditLog.actor_id.in_(teacher_ids),
        )
        .distinct()
        .all()
    )
    m1_done = {int(r[0]) for r in self_login}

    # Milestone 2 — öğrenci eklendi
    stu_map = _solo_student_ids(db, teacher_ids)
    m2_done = {tid for tid, sids in stu_map.items() if sids}

    # Milestone 3 — ilk görev (öğrencinin koçu = bu öğretmen)
    if any(stu_map.values()):
        all_student_ids = [s for sids in stu_map.values() for s in sids]
        student_to_teacher = {s: tid for tid, sids in stu_map.items() for s in sids}
        task_rows = (
            db.query(Task.student_id)
            .filter(Task.student_id.in_(all_student_ids))
            .distinct()
            .all()
        )
        m3_done = {student_to_teacher[int(r[0])] for r in task_rows
                   if int(r[0]) in student_to_teacher}
    else:
        m3_done = set()

    # Milestone 4 — veli davet
    try:
        pi_rows = (
            db.query(ParentInvitation.invited_by_id)
            .filter(ParentInvitation.invited_by_id.in_(teacher_ids))
            .distinct()
            .all()
        )
        m4_done = {int(r[0]) for r in pi_rows}
    except Exception:
        m4_done = set()

    out: list[dict] = []
    for t in teachers:
        # 5 step — "Öğretmen davet" bağımsız öğretmen için anlamsız (done=None);
        # bu sayede kurum tablosuyla aynı header'a hizalanır.
        steps = [
            ("admin_login", "🔑 Yetkili giriş", t.id in m1_done),
            ("teacher_invite", "🎓 Öğretmen davet", None),
            ("student_added", "🎒 Öğrenci eklendi", t.id in m2_done),
            ("first_task", "📝 İlk görev", t.id in m3_done),
            ("parent_invite", "👨‍👩 Veli davet", t.id in m4_done),
        ]
        applicable = [d for _, _, d in steps if d is not None]
        done_count = sum(1 for d in applicable if d)
        total_count = len(applicable)
        age_days = (now - _aware(t.created_at)).days if t.created_at else 0
        out.append({
            "owner_type": "solo",
            "owner_id": t.id,
            "institution_id": None,
            "institution_name": _solo_owner_label(t),
            "plan": _solo_plan(t),
            "age_days": age_days,
            "milestones": [
                {"key": k, "label": lbl, "done": d} for k, lbl, d in steps
            ],
            "done_count": done_count,
            "total_count": total_count,
            "completion_pct": round(100 * done_count / total_count) if total_count else 0,
            "detail_url": f"/admin/revenue/users/{t.id}",
        })
    out.sort(key=lambda r: (r["done_count"], -r["age_days"]))
    return out


def combined_onboarding(db: Session, *, segment: str = "all",
                          days: int = 14) -> list[dict]:
    if segment == "institution":
        rows = onboarding_milestones(db, days=days)
        for r in rows:
            r.setdefault("owner_type", "institution")
            r.setdefault("owner_id", r.get("institution_id"))
        return rows
    if segment == "solo":
        return solo_onboarding_milestones(db, days=days)
    insts = onboarding_milestones(db, days=days)
    for r in insts:
        r.setdefault("owner_type", "institution")
        r.setdefault("owner_id", r.get("institution_id"))
    return insts + solo_onboarding_milestones(db, days=days)


def solo_plan_benchmark_table(db: Session, *, active_days: int = 30) -> list[dict]:
    """Bağımsız öğretmen planı (User.plan) bazlı ortalama metrikler."""
    cutoff = _now() - timedelta(days=active_days)
    teachers = _solo_teachers(db, limit=10000)
    if not teachers:
        return []

    by_plan: dict[str, list[User]] = defaultdict(list)
    for t in teachers:
        by_plan[_solo_plan(t)].append(t)

    teacher_ids = [t.id for t in teachers]
    stu_map = _solo_student_ids(db, teacher_ids)
    all_stu = [s for sids in stu_map.values() for s in sids]

    # Aktif öğrenci sayısı per teacher
    if all_stu:
        active_rows = (
            db.query(AuditLog.actor_id)
            .filter(
                AuditLog.action == AuditAction.LOGIN_SUCCESS,
                AuditLog.actor_id.in_(all_stu),
                AuditLog.created_at >= cutoff,
            )
            .distinct()
            .all()
        )
        active_stu = {int(r[0]) for r in active_rows}
    else:
        active_stu = set()
    per_teacher_active_stu = {
        tid: sum(1 for s in sids if s in active_stu)
        for tid, sids in stu_map.items()
    }

    # Aktif öğretmen sayısı (kendi girişi)
    if teacher_ids:
        t_active_rows = (
            db.query(AuditLog.actor_id)
            .filter(
                AuditLog.action == AuditAction.LOGIN_SUCCESS,
                AuditLog.actor_id.in_(teacher_ids),
                AuditLog.created_at >= cutoff,
            )
            .distinct()
            .all()
        )
        active_t = {int(r[0]) for r in t_active_rows}
    else:
        active_t = set()

    # Feature adopsiyon — solo_feature_usage_matrix
    fm = solo_feature_usage_matrix(db, days=active_days, top=len(teachers) + 100)
    adopt_map = {r["owner_id"]: r["adopted_count"] for r in fm["rows"]}
    feature_total = len(fm["features"]) or 1

    # Oturum süresi
    sess_rows = (
        db.query(
            ActiveSession.user_id,
            ActiveSession.login_at,
            ActiveSession.last_seen_at,
        )
        .filter(
            ActiveSession.terminated_at.isnot(None),
            ActiveSession.terminated_at >= cutoff,
            ActiveSession.user_id.in_(teacher_ids + all_stu),
        )
        .all()
    )
    # actor_id → teacher_id eşlemesi
    actor_to_teacher = {tid: tid for tid in teacher_ids}
    for tid, sids in stu_map.items():
        for s in sids:
            actor_to_teacher[s] = tid
    per_teacher_sess: dict[int, list[float]] = defaultdict(list)
    for uid, la, ls in sess_rows:
        if la is None or ls is None:
            continue
        tid = actor_to_teacher.get(int(uid))
        if tid is None:
            continue
        secs = (_aware(ls) - _aware(la)).total_seconds()
        if 0 <= secs <= 24 * 3600:
            per_teacher_sess[tid].append(secs / 60.0)

    try:
        from app.services.plans import PLAN_CATALOG
    except Exception:
        PLAN_CATALOG = {}

    out: list[dict] = []
    for plan_code, ts in by_plan.items():
        count = len(ts)
        if count == 0:
            continue
        avg_active_t = sum(1 for t in ts if t.id in active_t) / count
        avg_active_s = sum(per_teacher_active_stu.get(t.id, 0) for t in ts) / count
        avg_adopt = sum(adopt_map.get(t.id, 0) for t in ts) / count
        sess_avgs = []
        for t in ts:
            durs = per_teacher_sess.get(t.id, [])
            if durs:
                sess_avgs.append(sum(durs) / len(durs))
        avg_sess = round(sum(sess_avgs) / len(sess_avgs), 1) if sess_avgs else 0

        plan_info = PLAN_CATALOG.get(plan_code) if PLAN_CATALOG else None
        plan_label = (getattr(plan_info, "label", plan_code)
                      if plan_info else plan_code)
        plan_price = int(getattr(plan_info, "price_monthly_try", 0) or 0) if plan_info else 0

        out.append({
            "owner_type": "solo",
            "plan": plan_code,
            "plan_label": f"👤 {plan_label}",
            "monthly_price": plan_price,
            "institution_count": count,  # burada öğretmen sayısı
            "avg_active_teachers": round(avg_active_t, 2),
            "avg_active_students": round(avg_active_s, 1),
            "avg_feature_adoption": round(avg_adopt, 1),
            "avg_feature_adoption_pct": round(100 * avg_adopt / feature_total),
            "feature_total": feature_total,
            "avg_session_min": avg_sess,
        })
    out.sort(key=lambda r: (-r["monthly_price"], -r["institution_count"]))
    return out


def combined_plan_benchmark(db: Session, *, segment: str = "all",
                               active_days: int = 30) -> list[dict]:
    if segment == "institution":
        rows = plan_benchmark_table(db, active_days=active_days)
        for r in rows:
            r.setdefault("owner_type", "institution")
        return rows
    if segment == "solo":
        return solo_plan_benchmark_table(db, active_days=active_days)
    insts = plan_benchmark_table(db, active_days=active_days)
    for r in insts:
        r.setdefault("owner_type", "institution")
        r["plan_label"] = f"🏢 {r.get('plan_label', r['plan'])}"
    return insts + solo_plan_benchmark_table(db, active_days=active_days)


def champion_solo_teachers(db: Session, *, top_pct: int = 10) -> list[dict]:
    """Bağımsız öğretmenler için en üst %N — kurum champion ile aynı skor formülü."""
    teachers = _solo_teachers(db, limit=10000)
    if not teachers:
        return []
    now = _now()
    teacher_ids = [t.id for t in teachers]
    universe = _solo_actor_universe(db, teacher_ids)
    actor_to_teacher = {uid: tid for tid, uids in universe.items() for uid in uids}
    all_actors = list(actor_to_teacher.keys())

    # Density: son 7g'de kişi başı distinct login günü
    cutoff_7d = now - timedelta(days=7)
    if all_actors:
        activity_rows = (
            db.query(AuditLog.actor_id, AuditLog.created_at)
            .filter(
                AuditLog.action == AuditAction.LOGIN_SUCCESS,
                AuditLog.actor_id.in_(all_actors),
                AuditLog.created_at >= cutoff_7d,
            )
            .all()
        )
    else:
        activity_rows = []
    user_days: dict[int, dict[int, set[str]]] = defaultdict(lambda: defaultdict(set))
    for uid, ca in activity_rows:
        tid = actor_to_teacher.get(int(uid))
        ts = _aware(ca)
        if tid is None or ts is None:
            continue
        user_days[tid][int(uid)].add(ts.date().isoformat())

    # Feature adoption
    fm = solo_feature_usage_matrix(db, days=30, top=len(teachers) + 100)
    feature_total = len(fm["features"]) or 1
    adopt_map = {r["owner_id"]: r["adopted_count"] for r in fm["rows"]}

    # Aktif öğrenci sayısı (ratio yerine kullanılır)
    ratios = solo_teacher_student_ratios(db, active_days=14)
    ratio_map = {r["owner_id"]: r["active_students"] for r in ratios}

    rows: list[dict] = []
    for t in teachers:
        ud = user_days.get(t.id, {})
        active_user_count = len(ud)
        total_login_days = sum(len(d) for d in ud.values())
        density = (total_login_days / active_user_count) if active_user_count > 0 else 0
        density_norm = min(density / 7.0, 1.0)
        adopt = adopt_map.get(t.id, 0)
        adopt_pct = adopt / feature_total
        is_paying = _is_paid_plan(t.plan)
        age_months = ((now - _aware(t.created_at)).days / 30.0) if t.created_at else 0
        age_score = min(age_months / 6.0, 1.0) if is_paying else 0
        # Bağımsız öğretmen için ratio yerine "aktif öğrenci sayısı/10" normalize
        ratio_norm = min(ratio_map.get(t.id, 0) / 10.0, 1.0)
        score = (
            0.40 * density_norm + 0.30 * adopt_pct
            + 0.20 * age_score + 0.10 * ratio_norm
        ) * 100
        rows.append({
            "owner_type": "solo",
            "owner_id": t.id,
            "institution_id": None,
            "institution_name": _solo_owner_label(t),
            "plan": _solo_plan(t),
            "is_paying": is_paying,
            "score": round(score, 1),
            "density": round(density, 1),
            "active_user_count": active_user_count,
            "feature_adoption": adopt,
            "feature_total": feature_total,
            "age_months": round(age_months, 1),
            "student_teacher_ratio": ratio_map.get(t.id, 0),
            "detail_url": f"/admin/revenue/users/{t.id}",
        })
    rows.sort(key=lambda r: -r["score"])
    n_champ = max(1, len(rows) * top_pct // 100)
    champions = rows[:n_champ]
    for r in champions:
        r["is_champion"] = True
    return champions


def combined_champions(db: Session, *, segment: str = "all",
                          top_pct: int = 10) -> list[dict]:
    if segment == "institution":
        rows = champion_institutions(db, top_pct=top_pct)
        for r in rows:
            r.setdefault("owner_type", "institution")
            r.setdefault("owner_id", r.get("institution_id"))
        return rows
    if segment == "solo":
        return champion_solo_teachers(db, top_pct=top_pct)
    inst_rows = champion_institutions(db, top_pct=top_pct)
    for r in inst_rows:
        r.setdefault("owner_type", "institution")
        r.setdefault("owner_id", r.get("institution_id"))
    solo_rows = champion_solo_teachers(db, top_pct=top_pct)
    merged = inst_rows + solo_rows
    merged.sort(key=lambda r: -r.get("score", 0))
    return merged


# ====================================================================
# SPRINT 5 — Bağımsız öğretmene özel metrikler (sadece solo/all segmentlerinde)
# ====================================================================


def solo_parent_outreach_rate(db: Session) -> dict:
    """Veli daveti göndermiş aktif bağımsız öğretmenlerin oranı.

    Veli iletişimi — öğretmenin program dışı destek istemesinin ölçütü.
    """
    from app.models import ParentInvitation
    teachers = _solo_teachers(db, limit=10000)
    total = len(teachers)
    if total == 0:
        return {"sent_count": 0, "total": 0, "ratio_pct": 0, "label": "—"}
    teacher_ids = [t.id for t in teachers]
    try:
        sent_rows = (
            db.query(ParentInvitation.invited_by_id)
            .filter(ParentInvitation.invited_by_id.in_(teacher_ids))
            .distinct()
            .all()
        )
        sent = {int(r[0]) for r in sent_rows}
    except Exception:
        sent = set()
    cnt = len(sent)
    pct = round(100 * cnt / total) if total else 0
    if pct >= 50:
        label = "yüksek — veli destek kültürü güçlü"; color = "emerald"
    elif pct >= 25:
        label = "orta — geliştirilebilir"; color = "amber"
    else:
        label = "düşük — veli daveti özelliği tanıtılmamış"; color = "rose"
    return {
        "sent_count": cnt,
        "total": total,
        "ratio_pct": pct,
        "label": label,
        "color": color,
    }


def solo_discipline_metric(db: Session, *, weeks: int = 4) -> dict:
    """Öğrenci başına haftalık ortalama görev sayısı.

    "Öğretmen disiplini" — aktif öğretmen ne kadar yoğun program hazırlıyor?
    """
    from app.models import Task
    cutoff = _now() - timedelta(weeks=weeks)
    teachers = _solo_teachers(db, limit=10000)
    if not teachers:
        return {"avg_per_student_per_week": 0, "total_tasks": 0,
                "total_students": 0, "label": "—"}
    teacher_ids = [t.id for t in teachers]
    stu_map = _solo_student_ids(db, teacher_ids)
    all_stu = [s for sids in stu_map.values() for s in sids]
    if not all_stu:
        return {"avg_per_student_per_week": 0, "total_tasks": 0,
                "total_students": 0,
                "label": "henüz hiç öğrenci eklenmemiş", "color": "slate"}
    task_count = (
        db.query(func.count(Task.id))
        .filter(
            Task.student_id.in_(all_stu),
            Task.created_at >= cutoff,
        )
        .scalar() or 0
    )
    total_stu = len(all_stu)
    avg = round(task_count / total_stu / weeks, 1) if total_stu else 0
    if avg >= 5:
        label = "yoğun program"; color = "emerald"
    elif avg >= 2:
        label = "orta yoğunluk"; color = "amber"
    elif avg > 0:
        label = "düşük — öğrenci başına az görev"; color = "rose"
    else:
        label = "hiç görev oluşturulmamış"; color = "slate"
    return {
        "avg_per_student_per_week": avg,
        "total_tasks": int(task_count),
        "total_students": total_stu,
        "weeks": weeks,
        "label": label,
        "color": color,
    }


def solo_consistency_score(db: Session, *, weeks: int = 4) -> dict:
    """Bağımsız öğretmenlerin son N haftada giriş yapmadığı hafta sayısı.

    Tutarlılık göstergesi — sürekli giriş yapan öğretmen vs sporadik.
    Çıktı: aktif öğretmenlerin ortalama 'kayıp hafta' sayısı (0 = mükemmel).
    """
    now = _now()
    teachers = _solo_teachers(db, limit=10000)
    if not teachers:
        return {"avg_missing_weeks": 0, "weeks": weeks, "consistent_count": 0,
                "total": 0, "label": "—", "color": "slate"}
    teacher_ids = [t.id for t in teachers]
    cutoff = now - timedelta(weeks=weeks)
    rows = (
        db.query(AuditLog.actor_id, AuditLog.created_at)
        .filter(
            AuditLog.action == AuditAction.LOGIN_SUCCESS,
            AuditLog.actor_id.in_(teacher_ids),
            AuditLog.created_at >= cutoff,
        )
        .all()
    )
    by_teacher: dict[int, set[int]] = defaultdict(set)
    for uid, ca in rows:
        ts = _aware(ca)
        if ts is None:
            continue
        week_index = ((now - ts).days // 7)  # 0..weeks-1
        if 0 <= week_index < weeks:
            by_teacher[int(uid)].add(week_index)

    missing_per_teacher: list[int] = []
    consistent = 0
    for t in teachers:
        weeks_active = by_teacher.get(t.id, set())
        missing = weeks - len(weeks_active)
        missing_per_teacher.append(missing)
        if missing == 0:
            consistent += 1
    total = len(teachers)
    avg_missing = round(sum(missing_per_teacher) / total, 1) if total else 0
    if avg_missing <= 0.5:
        label = "yüksek tutarlılık"; color = "emerald"
    elif avg_missing <= 1.5:
        label = "orta tutarlılık"; color = "amber"
    else:
        label = "düşük tutarlılık — sporadik kullanım"; color = "rose"
    return {
        "avg_missing_weeks": avg_missing,
        "consistent_count": consistent,
        "total": total,
        "weeks": weeks,
        "label": label,
        "color": color,
    }


def solo_special_panel(db: Session) -> dict:
    """Bağımsız öğretmene özel metrik paketi (sadece solo/all segmentinde gösterilir)."""
    return {
        "parent_outreach": solo_parent_outreach_rate(db),
        "discipline": solo_discipline_metric(db, weeks=4),
        "consistency": solo_consistency_score(db, weeks=4),
    }


# ---------------------------- Faz J: Aksiyon önerileri (Sprint 4) ----------------------------


# Risk bant veya quadrant → önerilen aksiyon listesi
# Her öneri: {kind (CrmActionKind), label, hint}
RISK_ACTION_SUGGESTIONS: dict[str, list[dict]] = {
    # Heartbeat band'leri
    "no_login": [
        {"kind": "call", "label": "Yetkiliyi ara", "hint": "Hesabı oluşturulmuş ama hiç giriş yapılmamış"},
        {"kind": "email", "label": "Onboarding tekrar gönder", "hint": "Eksik adımları hatırlat"},
    ],
    "dead": [
        {"kind": "call", "label": "Yetkiliyi ara — durum sor", "hint": "30+ gün giriş yok, kayıp olabilir"},
        {"kind": "email", "label": "Geri kazanma teklifi", "hint": "İndirim/uzatma ile yeniden aktivasyon"},
    ],
    "critical": [
        {"kind": "call", "label": "Yetkiliyi ara", "hint": "14-30g sessizlik — kaybedebilirsin"},
        {"kind": "email", "label": "Memnuniyet anketi", "hint": "Neden kullanmıyorlar öğren"},
    ],
    "warning": [
        {"kind": "whatsapp", "label": "Hatırlatma mesajı", "hint": "1 haftadır giriş yok"},
        {"kind": "email", "label": "Yeni özellik tanıtımı", "hint": "İlgisini yeniden kazan"},
    ],
    "watch": [
        {"kind": "whatsapp", "label": "Yumuşak temas", "hint": "Henüz erken — sadece selam"},
    ],
    # Decay rate band'leri
    "sharp_drop": [
        {"kind": "call", "label": "Acil arama — sebep öğren", "hint": "Aktivite %50+ düştü, sebep ne?"},
        {"kind": "meeting", "label": "Yüz yüze görüşme öner", "hint": "Önemli müşteri kaybı sinyali"},
    ],
    "slow_drop": [
        {"kind": "email", "label": "Memnuniyet anketi", "hint": "Yavaş düşüş — sorun büyümeden öğren"},
    ],
    # Plan × Aktivite quadrant'ları
    "paying_idle": [
        {"kind": "call", "label": "Değer keşif görüşmesi", "hint": "Ödüyor ama kullanmıyor — niye sor"},
        {"kind": "onboarding", "label": "Yeniden eğitim öner", "hint": "Belki nasıl kullanılacağı net değil"},
    ],
    "paying_active": [
        {"kind": "email", "label": "Referans iste", "hint": "Champion — case study/testimonial adayı"},
        {"kind": "offer_sent", "label": "Yıllık plan teklif et", "hint": "Memnun + aktif → yıllık taahhüt"},
    ],
    "free_active": [
        {"kind": "offer_sent", "label": "Upgrade teklif et", "hint": "Aktif kullanıyor — ücretli plana geçiş şansı yüksek"},
        {"kind": "email", "label": "Premium özellik tanıtımı", "hint": "Ne kazanacağını göster"},
    ],
    "free_idle": [
        {"kind": "email", "label": "Yeniden aktivasyon kampanyası", "hint": "Düşük öncelik ama mass-email mantıklı"},
    ],
    # Champion özel rozeti
    "champion": [
        {"kind": "email", "label": "Memnuniyet referansı iste", "hint": "Champion seviyede — case study adayı"},
        {"kind": "offer_sent", "label": "Yıllık plan + indirim", "hint": "Uzun vadeli taahhüt için ideal an"},
        {"kind": "meeting", "label": "Stratejik partnership görüşmesi", "hint": "En değerli müşteriler"},
    ],
}


def suggest_actions_for(key: str) -> list[dict]:
    """Risk bant/quadrant/durum için önerilen aksiyon listesi."""
    return RISK_ACTION_SUGGESTIONS.get(key, [])


def critical_summary(panel_data: dict) -> dict:
    """Tüm panellerden kritik durumları tek özete kondansa eden helper.

    Yöneticinin tek bakışta "bugün acil ne var?" cevabını gösterir.
    Diğer panelleri zaten oluşturulmuş `panel_data` üzerinden kondansa eder
    (yeniden hesaplama yapmaz).
    """
    hb = panel_data.get("heartbeat_summary", {})
    decays = panel_data.get("decay_rates", []) or []
    plan_activity = panel_data.get("plan_activity", {}) or {}
    onboarding = panel_data.get("onboarding", []) or []
    champions = panel_data.get("champions", []) or []
    s = panel_data.get("stickiness", {}) or {}

    critical_inst = (hb.get("critical", 0) + hb.get("dead", 0)
                      + hb.get("no_login", 0))
    sharp_drop = sum(1 for d in decays if d.get("band") == "sharp_drop")
    paying_idle = (plan_activity.get("totals", {}) or {}).get("paying_idle", 0)
    onboarding_stuck = sum(1 for o in onboarding if o.get("completion_pct", 0) < 50)

    return {
        "stickiness_pct": s.get("ratio_pct", 0),
        "stickiness_color": s.get("color", "slate"),
        "stickiness_label": s.get("label", "—"),
        "critical_institutions": critical_inst,
        "sharp_drop_count": sharp_drop,
        "paying_idle_count": paying_idle,
        "onboarding_stuck_count": onboarding_stuck,
        "champion_count": len(champions),
    }


# ---------------------------- Aggregator ----------------------------


def get_activity_panel_data(db: Session, *, segment: str = "all") -> dict:
    """Aktivite paneli verisi.

    segment: 'all' (kurum + bağımsız öğretmen), 'institution', veya 'solo'.
    Kurum-merkezli bölümler (heartbeats/decay/plan_activity/silent/ratios/
    feature_matrix/onboarding/plan_benchmark/champions) seçilen segmente göre
    filtrelenir. Bütün-sistem metrikleri (DAU/MAU, heatmap, trend, stickiness,
    rol kırılımı vb.) segmentten bağımsız hesaplanır.
    """
    heartbeats = combined_heartbeats(db, segment=segment)
    data = {
        "generated_at": _now(),
        "segment": segment,
        "totals": aggregate_activity(db),
        "per_tenant": per_tenant_activity(db, top=20),
        "heatmap": hour_day_heatmap(db, days=7),
        "dau_trend_14d": daily_dau_trend(db, days=14),
        "silent_tenants_7d": combined_silent(db, segment=segment, days=7),
        "role_breakdown": role_breakdown_today(db),
        "heartbeats": heartbeats,
        "heartbeat_summary": heartbeat_summary(heartbeats),
        "wow": dau_week_over_week(db),
        # Sprint 2 — Faz C (segment'ten bağımsız — toplu)
        "stickiness": stickiness_metric(db),
        "stickiness_trend_30d": stickiness_trend(db, days=30),
        "week1": week1_retention(db),
        "day30": day30_survival(db),
        "resurrected": resurrected_users(db),
        # Sprint 2 — Faz G (owner-aware)
        "decay_rates": combined_decay_rates(db, segment=segment),
        "plan_activity": combined_plan_activity_matrix(db, segment=segment),
        # Sprint 3 — Faz D (owner-aware)
        "session_duration": session_duration_distribution(db, days=30),
        "teacher_student_ratios": combined_teacher_student_ratios(
            db, segment=segment),
        "power_users": power_users(db),
        # Sprint 3 — Faz E (owner-aware)
        "feature_popularity": feature_popularity(db, days=30),
        "feature_matrix": combined_feature_usage_matrix(
            db, segment=segment, days=30, top=30),
        "onboarding": combined_onboarding(db, segment=segment, days=14),
        # Sprint 4 — Faz H (owner-aware)
        "plan_benchmark": combined_plan_benchmark(db, segment=segment),
        "champions": combined_champions(db, segment=segment),
        # Sprint 4 — Faz J
        "action_suggestions": RISK_ACTION_SUGGESTIONS,
    }
    # Sprint 5 — Bağımsız öğretmene özel panel (sadece solo veya all'da)
    if segment in ("solo", "all"):
        data["solo_special"] = solo_special_panel(db)
    return data


def get_activity_panel_data_with_summary(db: Session, *, segment: str = "all") -> dict:
    """Tüm panel verisi + kritik özet kartı bağlı."""
    data = get_activity_panel_data(db, segment=segment)
    data["critical_summary"] = critical_summary(data)
    return data


__all__ = [
    "RISK_ACTION_SUGGESTIONS",
    "active_users_window",
    "aggregate_activity",
    "champion_institutions",
    "champion_solo_teachers",
    "combined_champions",
    "combined_decay_rates",
    "combined_feature_usage_matrix",
    "combined_heartbeats",
    "combined_onboarding",
    "combined_plan_activity_matrix",
    "combined_plan_benchmark",
    "combined_silent",
    "combined_teacher_student_ratios",
    "daily_dau_trend",
    "dau_week_over_week",
    "day30_survival",
    "feature_popularity",
    "feature_usage_matrix",
    "get_activity_panel_data",
    "get_activity_panel_data_with_summary",
    "heartbeat_summary",
    "hour_day_heatmap",
    "institution_decay_rates",
    "institution_heartbeats",
    "institution_hour_day_heatmap",
    "onboarding_milestones",
    "per_tenant_activity",
    "plan_activity_matrix",
    "plan_benchmark_table",
    "power_users",
    "resurrected_users",
    "role_breakdown_today",
    "session_duration_distribution",
    "silent_tenants",
    "solo_consistency_score",
    "solo_decay_rates",
    "solo_discipline_metric",
    "solo_feature_usage_matrix",
    "solo_heartbeats",
    "solo_onboarding_milestones",
    "solo_parent_outreach_rate",
    "solo_plan_activity_matrix",
    "solo_plan_benchmark_table",
    "solo_silent_teachers",
    "solo_special_panel",
    "solo_teacher_student_ratios",
    "stickiness_metric",
    "stickiness_trend",
    "suggest_actions_for",
    "teacher_student_ratios",
    "week1_retention",
]

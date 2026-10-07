"""Deneme analizi Faz 2 — gelişim raporu, hedef net, aksiyon planı, paylaşım.

TEK MERKEZ. Koç ekranı, öğrenci ekranı ve A4 gelişim raporu aynı hesabı kullanır.

Bileşenler:
  - build_progress_report : tek sınav türünde (TYT/AYT/LGS ayrı ölçek) gelişim
    özeti + ders gidişatı + hedef farkı + KURAL TABANLI yorum + aksiyon planı.
    AI YOK, kredi YOK; her cümle kayıtlı veriden türer (sayı uydurulmaz).
  - hedef net             : `exam_targets` (öğrenci × tür; öğrenci CASCADE).
  - seans gündem kuyruğu  : `session_agenda_items` (öğrenci CASCADE) — "seansa
    ekle" ile düşer, yeni seans formunda işaretli gelir, seans kaydedilince silinir.
  - öğrenciyle paylaşım   : koçun ÖĞRENCİYE notu (koça özel `note`tan AYRI),
    denemenin `analysis_meta["student_share"]` alanında — deneme silinince gider.

Öğrenci silinince bu kayıtların hiçbiri yetim kalmaz (2026-10-02; ilk sürüm
app_settings anahtarlarıydı, migration l3m6p9q0p44l taşıdı).
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.models import ExamResult, User
from app.models.exam_progress import ExamTarget, SessionAgendaItem
from app.models.curriculum import EXAM_SECTION_LABELS, ExamSection
from app.services import exam_scope
from app.models.exam_result import section_penalty

QUEUE_MAX = 40
SHARE_NOTE_MAX = 1000

# yorum/aksiyon eşikleri
SLOPE_WINDOW = 5          # eğim: son N deneme
SUBJECT_DROP_SLOPE = -1.0  # ders başına deneme başı net düşüşü
BLANK_HIGH_RATIO = 0.25    # son denemede boş / soru
WRONG_HIGH_RATIO = 0.30    # yanlış / (doğru + yanlış)
STALE_DAYS = 21            # son deneme bu kadar eskiyse ritim uyarısı


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


# ---------------------------------------------------------------- hedef net

class ProgressError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def _valid_section(section: str) -> ExamSection:
    try:
        return ExamSection(section)
    except ValueError:
        raise ProgressError(422, "invalid_section", "Geçersiz sınav türü.")


def _target_dict(t: ExamTarget, names: dict[int, str]) -> dict:
    try:
        subj = json.loads(t.subject_targets) if t.subject_targets else {}
    except ValueError:
        subj = {}
    return {
        "target_net": round(t.target_net, 2),
        "target_date": t.target_date.isoformat() if t.target_date else None,
        "subjects": subj if isinstance(subj, dict) else {},
        "note": t.note,
        "set_by_id": t.set_by_id,
        "set_by_name": names.get(t.set_by_id) if t.set_by_id else None,
        "updated_at": _iso(t.updated_at),
    }


def get_targets(db: Session, student_id: int) -> dict:
    rows = db.query(ExamTarget).filter(ExamTarget.student_id == student_id).all()
    ids = {r.set_by_id for r in rows if r.set_by_id}
    names = {u.id: u.full_name for u in db.query(User).filter(User.id.in_(ids)).all()} if ids else {}
    return {r.section: _target_dict(r, names) for r in rows}


def set_target(db: Session, student_id: int, *, section: str, target_net: float | None,
               target_date: str | None = None, subjects: dict | None = None,
               note: str | None = None, actor: User) -> dict:
    """Hedefi kaydet; target_net None → o türün hedefi silinir."""
    sec = _valid_section(section)
    row = (db.query(ExamTarget)
           .filter(ExamTarget.student_id == student_id, ExamTarget.section == sec.value).first())
    if target_net is None:
        if row is not None:
            db.delete(row)
        db.flush()
        return get_targets(db, student_id)
    if target_net < 0 or target_net > 200:
        raise ProgressError(422, "invalid_target", "Hedef net 0-200 arasında olmalı.")
    td = None
    if target_date:
        try:
            td = date.fromisoformat(target_date)
        except ValueError:
            raise ProgressError(422, "invalid_date", "Geçersiz tarih (YYYY-AA-GG).")
    clean_subj: dict[str, float] = {}
    for k, v in (subjects or {}).items():
        if v is None or str(k).strip() == "":
            continue
        fv = float(v)
        if fv < 0 or fv > 120:
            raise ProgressError(422, "invalid_target", "Ders hedefi 0-120 arasında olmalı.")
        clean_subj[str(k).strip()[:80]] = round(fv, 2)
    if row is None:
        row = ExamTarget(student_id=student_id, section=sec.value, target_net=0)
        db.add(row)
    row.target_net = round(float(target_net), 2)
    row.target_date = td
    row.subject_targets = json.dumps(clean_subj, ensure_ascii=False)
    row.note = (note or "").strip()[:300] or None
    row.set_by_id = actor.id
    row.updated_at = datetime.now(timezone.utc)
    db.flush()
    return get_targets(db, student_id)


# ---------------------------------------------------------------- seans gündem kuyruğu

def _item_dict(q: SessionAgendaItem) -> dict:
    return {"id": str(q.id), "key": q.item_key, "text": q.text, "source": q.source,
            "exam_id": q.exam_id, "created_at": _iso(q.created_at)}


def get_queue(db: Session, student_id: int) -> list[dict]:
    rows = (db.query(SessionAgendaItem).filter(SessionAgendaItem.student_id == student_id)
            .order_by(SessionAgendaItem.id).all())
    return [_item_dict(q) for q in rows]


def add_to_queue(db: Session, student_id: int, items: list[dict], *, actor: User) -> tuple[list[dict], int]:
    """Kuyruğa ekle; aynı `key` (ya da aynı metin) zaten varsa tekrar eklenmez."""
    existing = db.query(SessionAgendaItem).filter(SessionAgendaItem.student_id == student_id).all()
    keys = {q.item_key for q in existing if q.item_key}
    texts = {q.text for q in existing}
    count = len(existing)
    added = 0
    for it in items:
        text = (it.get("text") or "").strip()[:400]
        if not text:
            continue
        key = (it.get("key") or "").strip()[:80] or None
        if (key and key in keys) or text in texts:
            continue
        if count >= QUEUE_MAX:
            break
        exam_id = it.get("exam_id")
        if exam_id is not None:
            ok = db.query(ExamResult.id).filter(
                ExamResult.id == exam_id, ExamResult.student_id == student_id).first()
            exam_id = exam_id if ok else None
        db.add(SessionAgendaItem(student_id=student_id, created_by_id=actor.id, item_key=key,
                                 text=text, source=(it.get("source") or "exam")[:20], exam_id=exam_id))
        added += 1
        count += 1
        if key:
            keys.add(key)
        texts.add(text)
    db.flush()
    return get_queue(db, student_id), added


def remove_from_queue(db: Session, student_id: int, ids: list[str], *, actor: User) -> list[dict]:
    int_ids = [int(i) for i in ids if str(i).isdigit()]
    if int_ids:
        (db.query(SessionAgendaItem)
         .filter(SessionAgendaItem.student_id == student_id, SessionAgendaItem.id.in_(int_ids))
         .delete(synchronize_session=False))
    db.flush()
    return get_queue(db, student_id)


# ---------------------------------------------------------------- öğrenciyle paylaşım

def _meta(exam: ExamResult) -> dict:
    try:
        m = json.loads(exam.analysis_meta) if exam.analysis_meta else {}
    except ValueError:
        m = {}
    return m if isinstance(m, dict) else {}


def share_info(exam: ExamResult) -> dict | None:
    s = _meta(exam).get("student_share")
    return s if isinstance(s, dict) and s.get("shared_at") else None


def set_share(db: Session, exam: ExamResult, *, note: str | None, actor: User) -> dict:
    meta = _meta(exam)
    prev = meta.get("student_share") if isinstance(meta.get("student_share"), dict) else {}
    share = {
        "note": (note or "").strip()[:SHARE_NOTE_MAX] or None,
        "shared_at": _now_iso(),
        "first_shared_at": prev.get("first_shared_at") or prev.get("shared_at") or _now_iso(),
        "shared_by_name": actor.full_name,
    }
    meta["student_share"] = share
    exam.analysis_meta = json.dumps(meta, ensure_ascii=False)
    return share


def clear_share(exam: ExamResult) -> None:
    meta = _meta(exam)
    if meta.pop("student_share", None) is not None:
        exam.analysis_meta = json.dumps(meta, ensure_ascii=False)


# ---------------------------------------------------------------- gelişim raporu

def _slope(values: list[float]) -> float | None:
    """Doğrusal eğim (deneme başına net değişimi); <3 noktada None."""
    n = len(values)
    if n < 3:
        return None
    xs = list(range(n))
    mx, my = sum(xs) / n, sum(values) / n
    den = sum((x - mx) ** 2 for x in xs)
    if den == 0:
        return None
    return round(sum((x - mx) * (y - my) for x, y in zip(xs, values)) / den, 2)


def _fmt(n: float) -> str:
    return f"{n:.2f}".replace(".", ",")


def _signed(n: float) -> str:
    return ("+" if n > 0 else "−" if n < 0 else "") + _fmt(abs(n))


def _subject_rows(exam: ExamResult) -> list[dict]:
    try:
        data = json.loads(exam.subject_nets) if exam.subject_nets else []
    except ValueError:
        data = []
    return [d for d in data if isinstance(d, dict) and d.get("name")]


def _skey(name: str) -> str:
    return " ".join(str(name).lower().split())


def build_progress_report(db: Session, student: User, *, section: str | None = None,
                          period: str | None = None) -> dict:
    from app.services import grade_period_service
    from app.services.exam_topic_analysis import build_exam_topic_analysis

    win = grade_period_service.resolve_window(db, student.id, period)
    q = db.query(ExamResult).filter(ExamResult.student_id == student.id)
    if win.start is not None:
        q = q.filter(ExamResult.exam_date >= win.start)
    if win.end is not None:
        q = q.filter(ExamResult.exam_date <= win.end)
    all_exams = q.order_by(ExamResult.exam_date.asc(), ExamResult.id.asc()).all()

    # 2026-10-06: seçim TÜR değil SERİ (genel deneme / ders bazlı branş) — netler
    # yalnız aynı kapsamdaki denemeler arasında kıyaslanır (exam_scope).
    options = exam_scope.series_options(all_exams)
    skey = exam_scope.resolve_series(section, options)
    sec: ExamSection | None = ExamSection(exam_scope.section_of_key(skey)) if skey else None
    is_general = exam_scope.is_general_key(skey)

    exams = [e for e in all_exams if exam_scope.in_series(e, skey)]
    # hedef net tür anahtarıyla tutulur → yalnız GENEL seriye uygulanır
    target = get_targets(db, student.id).get(sec.value) if (sec and is_general) else None
    opt = next((o for o in options if o["value"] == skey), None)
    base = {
        "section": sec.value if sec else None,
        "section_label": (opt["label"] if opt else (EXAM_SECTION_LABELS[sec] if sec else None)),
        "section_options": options,
        "series": skey,
        "is_branch": bool(skey) and not is_general,
        "target_allowed": is_general,
        "student_name": student.full_name,
        "generated_at": _now_iso(),
        "exams": [], "stats": None, "subjects": [], "target": None,
        "commentary": [], "actions": [], "opportunities": [],
    }
    if not exams:
        if target:
            base["target"] = {**target, "gap": None, "progress_pct": None}
        return base

    penalty = section_penalty(sec)
    series = []
    for e in exams:
        qn = e.total_correct + e.total_wrong + e.total_blank
        series.append({
            "id": e.id, "title": e.title, "exam_date": e.exam_date.isoformat(),
            "net": round(e.net, 2), "correct": e.total_correct, "wrong": e.total_wrong,
            "blank": e.total_blank, "questions": qn,
        })
    nets = [s["net"] for s in series]
    last, first = series[-1], series[0]
    last3 = nets[-3:]
    stats = {
        "count": len(nets),
        "first_net": first["net"], "last_net": last["net"],
        "best_net": max(nets), "avg_net": round(sum(nets) / len(nets), 2),
        "avg_last3": round(sum(last3) / len(last3), 2),
        "change": round(last["net"] - first["net"], 2),
        "slope": _slope(nets[-SLOPE_WINDOW:]),
        "last_date": last["exam_date"],
        "days_since_last": (date.today() - exams[-1].exam_date).days,
    }

    # ders gidişatı (subject_nets; ad bazında birleşir)
    subj_order: list[str] = []
    subj_names: dict[str, str] = {}
    per_exam: list[dict[str, dict]] = []
    for e in exams:
        m: dict[str, dict] = {}
        for d in _subject_rows(e):
            k = _skey(d["name"])
            if k not in subj_names:
                subj_names[k] = d["name"]
                subj_order.append(k)
            m[k] = d
        per_exam.append(m)
    subj_targets = {(_skey(k)): v for k, v in ((target or {}).get("subjects") or {}).items()}
    subjects = []
    for k in subj_order:
        vals = [m[k]["net"] for m in per_exam if k in m]
        lastd = per_exam[-1].get(k)
        tnet = subj_targets.get(k)
        subjects.append({
            "name": subj_names[k],
            "nets": [m[k]["net"] if k in m else None for m in per_exam],
            "first": vals[0] if vals else None,
            "last": lastd["net"] if lastd else None,
            "avg": round(sum(vals) / len(vals), 2) if vals else None,
            "change": round(vals[-1] - vals[0], 2) if len(vals) >= 2 else None,
            "slope": _slope(vals[-SLOPE_WINDOW:]),
            "last_correct": lastd.get("correct") if lastd else None,
            "last_wrong": lastd.get("wrong") if lastd else None,
            "last_blank": lastd.get("blank") if lastd else None,
            "target": tnet,
            "gap": round(tnet - lastd["net"], 2) if (tnet is not None and lastd) else None,
        })

    # hedef
    tinfo = None
    if target:
        gap = round(target["target_net"] - stats["avg_last3"], 2)
        weeks_left = None
        if target.get("target_date"):
            try:
                weeks_left = max(0, (date.fromisoformat(target["target_date"]) - date.today()).days // 7)
            except ValueError:
                weeks_left = None
        exams_needed = None
        if gap > 0 and stats["slope"] and stats["slope"] > 0:
            exams_needed = int(-(-gap // stats["slope"]))
        tinfo = {
            **target,
            "basis": "son 3 denemenin ortalaması" if len(last3) > 1 else "son deneme",
            "basis_net": stats["avg_last3"],
            "gap": gap,
            "progress_pct": round(min(100.0, max(0.0, stats["avg_last3"] / target["target_net"] * 100)), 1)
            if target["target_net"] else None,
            "weeks_left": weeks_left,
            "exams_needed_at_pace": exams_needed,
            "per_week_needed": round(gap / weeks_left, 2) if (weeks_left and gap > 0) else None,
        }

    # konu fırsatları (soru-satırlı denemelerden)
    try:
        ta = build_exam_topic_analysis(db, student, section=skey, period=period)
    except Exception:  # noqa: BLE001 — rapor konu analizi olmadan da üretilir
        ta = {"opportunities": [], "forgotten": [], "improved": []}
    opps = ta.get("opportunities", [])[:6]

    commentary = _commentary(stats, series, subjects, tinfo, penalty)
    actions = _actions(stats, series, subjects, tinfo, opps, ta.get("forgotten", []), exams[-1].id)

    base.update({
        "exams": series, "stats": stats, "subjects": subjects, "target": tinfo,
        "commentary": commentary, "actions": actions,
        "opportunities": [
            {"topic_id": o["topic_id"], "topic_name": o["topic_name"],
             "subject_name": o["subject_name"], "wrong": o["wrong"], "blank": o["blank"],
             "total": o["total"], "net_gain_per_exam": o["net_gain_per_exam"]}
            for o in opps
        ],
    })
    return base


def _commentary(stats, series, subjects, tinfo, penalty) -> list[dict]:
    out: list[dict] = []
    n = stats["count"]
    last = series[-1]
    if n == 1:
        out.append({"tone": "info", "text": f"Bu türde ilk deneme: {_fmt(last['net'])} net. "
                    "Gidişatı görmek için aynı türden en az üç deneme gerekir."})
    else:
        ch = stats["change"]
        tone = "good" if ch >= 1 else "warn" if ch <= -1 else "info"
        out.append({"tone": tone, "text": f"{n} denemede net {_fmt(stats['first_net'])} → "
                    f"{_fmt(stats['last_net'])} ({_signed(ch)}). En iyi net {_fmt(stats['best_net'])}."})
        sl = stats["slope"]
        if sl is not None:
            if sl >= 0.5:
                out.append({"tone": "good", "text": f"Son {min(n, SLOPE_WINDOW)} denemede düzenli yükseliş var: "
                            f"deneme başına ortalama {_signed(sl)} net."})
            elif sl <= -0.5:
                out.append({"tone": "warn", "text": f"Son {min(n, SLOPE_WINDOW)} denemede düşüş eğilimi var: "
                            f"deneme başına ortalama {_signed(sl)} net."})
            else:
                out.append({"tone": "info", "text": "Son denemelerde net yatay seyrediyor — "
                            "yeni bir sıçrama için çalışma biçiminde değişiklik gerekebilir."})
    ups = [s for s in subjects if s["change"] is not None and s["change"] >= 2]
    downs = [s for s in subjects if s["change"] is not None and s["change"] <= -2]
    if ups:
        best = max(ups, key=lambda s: s["change"])
        out.append({"tone": "good", "text": f"En çok gelişen ders {best['name']} "
                    f"({_fmt(best['first'])} → {_fmt(best['last'])} net)."})
    if downs:
        worst = min(downs, key=lambda s: s["change"])
        out.append({"tone": "warn", "text": f"En çok gerileyen ders {worst['name']} "
                    f"({_fmt(worst['first'])} → {_fmt(worst['last'])} net)."})
    if last["questions"]:
        br = last["blank"] / last["questions"]
        answered = last["correct"] + last["wrong"]
        wr = last["wrong"] / answered if answered else 0
        if br >= BLANK_HIGH_RATIO:
            out.append({"tone": "warn", "text": f"Son denemede {last['blank']} soru boş kaldı "
                        f"(soruların %{round(br * 100)}'i) — süre ya da konu eksiği konuşulmalı."})
        if wr >= WRONG_HIGH_RATIO and last["wrong"] >= 5:
            lost = round(last["wrong"] / penalty, 2)
            out.append({"tone": "warn", "text": f"Cevaplanan soruların %{round(wr * 100)}'i yanlış; "
                        f"yanlışlar {_fmt(lost)} net götürdü — emin olunmayan soruda eleme önemli."})
    if tinfo:
        gap = tinfo["gap"]
        if gap <= 0:
            out.append({"tone": "good", "text": f"Hedef {_fmt(tinfo['target_net'])} net tuttu "
                        f"({tinfo['basis']}: {_fmt(tinfo['basis_net'])})."})
        else:
            txt = f"Hedef {_fmt(tinfo['target_net'])} nete {_fmt(gap)} net kaldı ({tinfo['basis']}: {_fmt(tinfo['basis_net'])})."
            if tinfo.get("exams_needed_at_pace"):
                txt += f" Bu tempoyla yaklaşık {tinfo['exams_needed_at_pace']} deneme sonra ulaşılır."
            elif stats["slope"] is not None and stats["slope"] <= 0:
                txt += " Mevcut tempo hedefe götürmüyor."
            if tinfo.get("per_week_needed"):
                txt += f" Hedef tarihe kadar haftada {_fmt(tinfo['per_week_needed'])} net artış gerekiyor."
            out.append({"tone": "info" if (stats["slope"] or 0) > 0 else "warn", "text": txt})
    if stats["days_since_last"] >= STALE_DAYS:
        out.append({"tone": "warn", "text": f"Son deneme {stats['days_since_last']} gün önce — "
                    "deneme ritmi düştü."})
    return out


def _actions(stats, series, subjects, tinfo, opps, forgotten, last_exam_id) -> list[dict]:
    acts: list[dict] = []

    def add(key, kind, priority, title, detail, subject=None, topic_id=None):
        acts.append({"key": key, "kind": kind, "priority": priority, "title": title,
                     "detail": detail, "subject": subject, "topic_id": topic_id,
                     "exam_id": last_exam_id})

    for o in opps[:4]:
        parts = []
        if o["wrong"]:
            parts.append(f"{o['wrong']} yanlış")
        if o["blank"]:
            parts.append(f"{o['blank']} boş")
        add(f"topic:{o['topic_id']}", "topic", 1 if o["net_gain_per_exam"] >= 1 else 2,
            f"{o['topic_name']} konusunu kapat",
            f"{o['subject_name']} · {o['total']} soruda {' ve '.join(parts)}; kapanırsa deneme başına "
            f"yaklaşık {_signed(o['net_gain_per_exam'])} net.",
            o["subject_name"], o["topic_id"])
    for f in forgotten[:2]:
        add(f"forgot:{f['topic_id']}", "review", 2, f"{f['topic_name']} tekrar edilmeli",
            f"{f['subject_name']} · doğruluk %{round(f['first_accuracy'] * 100)} → "
            f"%{round(f['last_accuracy'] * 100)} düştü (ilk denemelerde "
            f"{f.get('first_correct', 0)}/{f.get('first_total', 0)}, son denemelerde "
            f"{f.get('last_correct', 0)}/{f.get('last_total', 0)} doğru — unutulma işareti).",
            f["subject_name"], f["topic_id"])
    for s in subjects:
        if s["slope"] is not None and s["slope"] <= SUBJECT_DROP_SLOPE:
            add(f"subjdrop:{_skey(s['name'])}", "subject", 1, f"{s['name']} dersindeki düşüşü konuş",
                f"Son denemelerde deneme başına {_signed(s['slope'])} net; son net {_fmt(s['last'])}.",
                s["name"])
    gaps = [s for s in subjects if s["gap"] is not None and s["gap"] > 0]
    for s in sorted(gaps, key=lambda x: -x["gap"])[:2]:
        add(f"subjgap:{_skey(s['name'])}", "target", 2, f"{s['name']} hedefine {_fmt(s['gap'])} net var",
            f"Hedef {_fmt(s['target'])} · son deneme {_fmt(s['last'])} net.", s["name"])
    last = series[-1]
    if last["questions"] and last["blank"] / last["questions"] >= BLANK_HIGH_RATIO:
        add("behavior:blank", "behavior", 2, "Boş bırakılan soruları azalt",
            f"Son denemede {last['blank']} boş — turlama (önce bildiklerini çöz, sonra dön) "
            "ve süre planı üzerine çalışılmalı.")
    answered = last["correct"] + last["wrong"]
    if answered and last["wrong"] >= 5 and last["wrong"] / answered >= WRONG_HIGH_RATIO:
        add("behavior:wrong", "behavior", 2, "Yanlış oranını düşür",
            f"Son denemede {last['wrong']} yanlış — emin olunmayan soruda eleme yapıp "
            "gerekirse boş bırakma stratejisi konuşulmalı.")
    if stats["days_since_last"] >= STALE_DAYS:
        add("rhythm", "rhythm", 3, "Deneme ritmini yeniden kur",
            f"Son deneme {stats['days_since_last']} gün önce; düzenli (1-2 haftada bir) deneme önerilir.")
    if tinfo and tinfo["gap"] > 0 and (stats["slope"] is None or stats["slope"] <= 0):
        add("target:pace", "target", 1, "Hedefe göre çalışma planını güncelle",
            f"Hedef {_fmt(tinfo['target_net'])} net; {_fmt(tinfo['gap'])} net açık var ve mevcut tempo yetmiyor.")
    acts.sort(key=lambda a: a["priority"])
    return acts[:10]


def action_agenda_text(a: dict) -> str:
    """Aksiyonu seans gündemi satırına çevir."""
    return f"{a['title']} — {a['detail']}"

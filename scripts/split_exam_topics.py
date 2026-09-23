"""Alt konulara bölünen sınav konuları + "Ünite / Konu" etiketleri — geriye dönük onarım.

2026-09-23 (Emir #113 karne analizi): (1) Paragraf / Üçgenler / Çokgenler ve
Dörtgenler alt konulara bölündü, eski geniş başlıklar "(Karma)" adını aldı
(seed EXAM_TOPIC_RENAMES); (2) TYT Tarih + Din'e eksik üniteler eklendi;
(3) normalizasyon "Ünite / Konu" etiketinde önce KUYRUĞU arar.

Bu betik mevcut veriyi yeni yapıya taşır:
  - kitap bölümleri + katalog şablon bölümleri: "(Karma)" konuya bağlı olup adı
    bir alt konuyu açıkça söyleyenler alt konuya,
  - öğrenilmiş sözlük (exam_topic_aliases, yalnız AI kayıtları — koç kaydına
    dokunulmaz) + deneme soruları (yalnız elle düzeltilmemiş satırlar):
    yeni deterministik kural (kuyruk → bütün → alt konu anahtar sözcüğü →
    ünite başı) farklı bir konu veriyorsa o konuya.

Belirsizde DOKUNMAZ (tahmin yok). Dry-run varsayılan; --apply yazar.
İdempotent: ikinci koşu 0 değişiklik.

    python -m scripts.split_exam_topics            # rapor
    python -m scripts.split_exam_topics --apply    # uygula
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter

from app.database import SessionLocal
from app.models import BookSection, BookTemplateSection, Subject, Topic, User
from app.models.exam_result import (
    ALIAS_SOURCE_COACH,
    ExamResult,
    ExamResultQuestion,
    ExamTopicAlias,
)
from app.services.curriculum_mapping import _label_key, _topic_key
from app.services.exam_import_service import (
    _deterministic_match,
    _label_parts,
    rebuild_subject_nets,
)

KARMA = {
    "Paragraf (Karma)": [
        ("Paragrafta Ana Düşünce", ("ana dusunce", "konu baslik", "paragrafin konusu",
                                    "paragrafta konu", "baslik")),
        ("Paragrafta Yardımcı Düşünce", ("yardimci", "kesin yargi", "cikarilabil",
                                         "soruya cevap", "diyalog", "roportaj",
                                         "iki metni", "iki paragrafi", "karsilastir",
                                         "coklu soru", "yorum")),
        ("Paragrafta Yapı", ("yapi", "siralama", "akisi bozan", "akisini bozan",
                             "ikiye bol", "iki parcaya", "tamamlama", "bosluk",
                             "cumle ekleme", "olusturma")),
    ],
    "Üçgenler (Karma)": [
        ("Üçgende Açıortay ve Kenarortay", ("aciortay", "kenarortay", "merkez",
                                            "yardimci")),
        ("Dik Üçgen ve Pisagor", ("dik ucgen", "dik ozel", "ozel ucgen", "pisagor",
                                  "trigonom")),
        ("İkizkenar ve Eşkenar Üçgen", ("ikizkenar", "eskenar ucgen")),
        ("Üçgende Açılar", ("ucgende aci", "ucgende acilar", "ucgende aci ")),
    ],
    "Çokgenler ve Dörtgenler (Karma)": [
        ("Paralelkenar", ("paralelkenar",)),
        ("Eşkenar Dörtgen ve Deltoid", ("eskenar dortgen", "deltoid")),
        ("Dikdörtgen", ("dikdortgen",)),
        ("Kare", ("kare",)),
        ("Yamuk", ("yamuk",)),
        ("Çokgenler", ("cokgen",)),
    ],
}


# 2026-09-23'te eklenen konular (alt konular + Tarih/Din eksikleri).
NEW_TOPICS = {name for rules in KARMA.values() for name, _ in rules} | {
    "Uluslararası İlişkilerde Denge Stratejisi (1774-1914)",
    "Din ve İslam", "Gönül Coğrafyamız", "Ahlaki Tutum ve Davranışlar",
    "Kur'an'da Bazı Kavramlar", "İslam ve Bilim",
}


def _split_target(label: str | None, karma_name: str, by_name: dict[str, Topic]) -> Topic | None:
    """(Karma) konuya bağlı etiketi alt konuya çevir — ilk uyan kural."""
    rules = KARMA.get(karma_name)
    if not rules:
        return None
    _, tail = _label_parts(label)
    key = f" {tail or _label_key(label)} "
    if karma_name.startswith("Çokgenler") and "cokgen" in key and "dortgen" in key:
        return None  # "Çokgenler ve Dörtgenler" genel başlığı
    for name, words in rules:
        if any(f" {w}" in key for w in words):
            return by_name.get(name)
    return None


class Pool:
    """Bir sınav ailesinin (TYT / AYT) konu havuzu."""

    def __init__(self, subjects: list[Subject], topics: list[Topic]):
        self.subj = {s.id: s for s in subjects}
        self.topics = {t.id: t for t in topics}
        self.home: dict[int, dict[str, Topic]] = {}
        self.uni: dict[str, list[Topic]] = {}
        self.by_name: dict[tuple[int, str], Topic] = {}
        for t in topics:
            k = _topic_key(t.name)
            self.by_name[(t.subject_id, t.name)] = t
            if not k:
                continue
            self.home.setdefault(t.subject_id, {}).setdefault(k, t)
            b = self.uni.setdefault(k, [])
            if all(x.subject_id != t.subject_id for x in b):
                b.append(t)

    def names_in(self, subject_id: int) -> dict[str, Topic]:
        return {n: t for (sid, n), t in self.by_name.items() if sid == subject_id}

    def resolve(self, label: str | None, home_sid: int | None, current: Topic | None) -> Topic | None:
        """Yeni kurala göre hedef; belirsizse None."""
        home_map = self.home.get(home_sid, {}) if home_sid else {}
        head, tail = _label_parts(label)
        full = _label_key(label)
        hit = None
        if tail and tail != full:
            hit = _deterministic_match(tail, home_map, self.uni)
        if hit is None and not tail:
            hit = _deterministic_match(full, home_map, self.uni)
        if hit is None and current is not None and current.name.endswith("(Karma)"):
            hit = _split_target(label, current.name, self.names_in(current.subject_id))
        if hit is None and head:
            # Ünite adı BİREBİR bir resmi konuysa ("Uluslararası İlişkilerde Denge
            # Stratejisi (1774-1914) / Osmanlı Dağılma Dönemi") asıl konu odur;
            # AI'ın seçtiği komşu ünite yanlıştır. (Karma) başlık hariç — orada
            # AI'ın daha özel seçimi ("Doğruda Açılar") korunur.
            cand = home_map.get(head) or (
                self.uni[head][0] if len(self.uni.get(head) or []) == 1 else None)
            # Mevcut eşleme varsa ünite başı onu YALNIZ bugün eklenen bir konuya
            # çevirebilir (AI o konuyu daha önce seçemezdi); aksi hâlde AI'ın
            # daha özel seçimi korunur ("Sayma ve Olasılık / Sıralama ve Seçme"
            # → Permütasyon kalır, Olasılık'a çekilmez).
            if cand is not None and (current is None or cand.name in NEW_TOPICS):
                hit = cand
        return hit


def _family(section_value: str | None) -> str | None:
    v = (section_value or "").upper()
    if v.startswith("TYT"):
        return "TYT"
    if v.startswith("AYT"):
        return "AYT"
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    db = SessionLocal()

    exam_subjects = (
        db.query(Subject)
        .filter(Subject.is_builtin.is_(True), Subject.teacher_id.is_(None),
                Subject.curriculum_model.is_(None))
        .all()
    )
    pools: dict[str, Pool] = {}
    for fam in ("TYT", "AYT"):
        subs = [s for s in exam_subjects if s.name.startswith(fam + " ")]
        tops = db.query(Topic).filter(Topic.subject_id.in_([s.id for s in subs]),
                                      Topic.is_builtin.is_(True)).all()
        pools[fam] = Pool(subs, tops)
    all_topics = {**pools["TYT"].topics, **pools["AYT"].topics}
    karma_ids = {t.id for t in all_topics.values() if t.name in KARMA}
    if not karma_ids:
        print("(Karma) konular yok — önce seed çalışmalı (scripts.seed).")
        return 1

    def fam_of_topic(tid: int | None) -> str | None:
        t = all_topics.get(tid) if tid else None
        if t is None:
            return None
        return "TYT" if t.subject_id in pools["TYT"].subj else "AYT"

    changes: Counter[str] = Counter()
    report: Counter[tuple[str, str, str, str]] = Counter()

    # 1) kitap + şablon bölümleri (yalnız Karma'ya bağlı olanlar)
    for model, kind in ((BookSection, "bolum"), (BookTemplateSection, "sablon")):
        for sec in db.query(model).filter(model.topic_id.in_(karma_ids)).all():
            cur = all_topics[sec.topic_id]
            tgt = _split_target(sec.label, cur.name,
                                pools[fam_of_topic(cur.id)].names_in(cur.subject_id))
            if tgt is not None and tgt.id != cur.id:
                report[(kind, sec.label or "", cur.name, tgt.name)] += 1
                changes[kind] += 1
                if args.apply:
                    sec.topic_id = tgt.id

    # 2) öğrenilmiş sözlük (AI kayıtları)
    for a in db.query(ExamTopicAlias).filter(ExamTopicAlias.source != ALIAS_SOURCE_COACH).all():
        fam = fam_of_topic(a.topic_id) or ("AYT" if (a.scope or "").startswith("ayt") else "TYT")
        pool = pools.get(fam)
        cur = all_topics.get(a.topic_id)
        if pool is None or cur is None:
            continue
        tgt = pool.resolve(a.label_raw or a.label_key, a.subject_id, cur)
        if tgt is not None and tgt.id != cur.id:
            report[("sozluk", a.label_raw or a.label_key, cur.name, tgt.name)] += 1
            changes["sozluk"] += 1
            if args.apply:
                a.topic_id = tgt.id

    # 3) deneme soruları (elle düzeltilmemiş)
    qs = (
        db.query(ExamResultQuestion, ExamResult.section)
        .join(ExamResult, ExamResult.id == ExamResultQuestion.exam_result_id)
        .filter(ExamResultQuestion.manually_edited.is_(False),
                ExamResultQuestion.topic_label_raw.isnot(None))
        .all()
    )
    touched_exams: set[int] = set()
    for q, section in qs:
        fam = _family(section.value if hasattr(section, "value") else section)
        pool = pools.get(fam) if fam else None
        if pool is None:
            continue
        cur = all_topics.get(q.topic_id) if q.topic_id else None
        if q.topic_id and cur is None:
            continue  # okul/Maarif konusu (karma havuz) — dokunma
        home_sid = cur.subject_id if cur is not None else q.subject_id
        tgt = pool.resolve(q.topic_label_raw, home_sid, cur)
        if tgt is not None and cur is not None and tgt.subject_id != cur.subject_id:
            report[("soru-ATLANDI(ders farklı)", q.topic_label_raw, cur.name, tgt.name)] += 1
            continue
        if tgt is not None and (cur is None or tgt.id != cur.id):
            report[("soru", q.topic_label_raw, cur.name if cur else "—", tgt.name)] += 1
            changes["soru"] += 1
            touched_exams.add(q.exam_result_id)
            if args.apply:
                q.topic_id = tgt.id
                q.subject_id = tgt.subject_id

    for (kind, label, old, new), n in sorted(report.items()):
        print(f"[{kind}] {label[:80]}  |  {old}  ->  {new}  (x{n})")
    print("\nÖZET:", dict(changes), "| etkilenen deneme:", len(touched_exams))
    if args.apply:
        db.flush()
        for ex in db.query(ExamResult).filter(ExamResult.id.in_(touched_exams)).all():
            st = db.get(User, ex.student_id)
            if st is not None:
                rebuild_subject_nets(db, ex, st)
        db.commit()
        print("UYGULANDI.")
    else:
        db.rollback()
        print("(dry-run — yazmak için --apply)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

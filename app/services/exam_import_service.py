"""Deneme PDF içe aktarma — orkestrasyon (TEK MERKEZ).

Akış: PDF → Gemini ÇİFT okuma (ai_exam_import) → satır birleştirme (uyuşmayan
hücre = şüpheli) → deterministik iç tutarlılık kontrolleri → sınav evreni
tespiti (tyt|ayt|lgs|okul) → ders çözümü → KONU NORMALİZASYONU (4 katman) →
önizleme taslağı. Koç/öğrenci taslağı düzeltir → confirm → ExamResult +
soru satırları + öğrenen sözlük güncellenir.

KONU NORMALİZASYONU (sistemin kalbi — yayınevi etiketi ≠ müfredat konusu):
  0. Öğrenen sözlük (ExamTopicAlias): (evren+ders+etiket) daha önce çözüldüyse
     deterministik aynı sonuç — birikim tutarlı kalır, AI maliyeti düşer.
  1. Deterministik: curriculum_mapping normalize/alias + ÖN-EK eşleşmesi
     (PDF'ler uzun konu adını kısaltır: "Paragrafta Yardımcı Düşü…").
     Belirsiz (birden çok aday) ASLA otomatik bağlanmaz.
  2. Kapalı-küme Gemini: yalnız evrenin GERÇEK konu listesinden id seçebilir;
     liste dışı id düşürülür (uydurma konu giremez). Konu adları kişisel veri
     değil → ücretsiz anahtar kullanılabilir (personal_data=False).
  3. Eşleşmeyen: ham etiketiyle saklanır; konu-bazlı birikime GİRMEZ
     (kirletmez), koç önizlemede/sonradan bağlar → sözlüğe yazılır.

Ders çözümü konudan ÜSTÜN değildir: "TYT-MATEMATİK" bölümündeki geometri
sorusu ("Üçgende Alan") konu eşleşmesiyle TYT Geometri dersine atanır —
PDF'in bölüm başlığı değil bizim taksonomi kazanır.
"""
from __future__ import annotations

import base64
import json
import logging
import re
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import (
    ALIAS_SOURCE_AI,
    ALIAS_SOURCE_COACH,
    EQ_RESULT_BOS,
    EQ_RESULT_DOGRU,
    EQ_RESULT_YANLIS,
    EQ_RESULTS,
    EXAM_SECTION_LABELS,
    EXAM_UNIVERSE_AYT,
    EXAM_UNIVERSE_LGS,
    EXAM_UNIVERSE_OKUL,
    EXAM_UNIVERSE_TYT,
    EXAM_UNIVERSES,
    CurriculumModel,
    ExamResult,
    ExamResultQuestion,
    ExamSection,
    ExamTopicAlias,
    Subject,
    Topic,
    Track,
    User,
    compute_net,
    section_penalty,
)
from app.services import ai_exam_import, gemini
from app.services.curriculum_mapping import _label_key, _topic_key, normalize

logger = logging.getLogger(__name__)

MAX_PDF_BYTES = 10 * 1024 * 1024  # 10 MB (Gemini inline sınırına base64 payıyla uyar)

_TRACK_TO_AYT_SECTION: dict[Track, ExamSection] = {
    Track.SAYISAL: ExamSection.AYT_SAY,
    Track.EA: ExamSection.AYT_EA,
    Track.SOZEL: ExamSection.AYT_SOZ,
    Track.DIL: ExamSection.AYT_DIL,
}

# Ham ders adı çözümünde ek eşanlamlar — KANONİK anahtara indirger (idempotent;
# hem sistem ders adı hem belge ham adı aynı fonksiyondan geçer → simetrik).
# NOT: anahtar/değerler normalize+bağlaç-atma SONRASI hallerdir.
_SUBJECT_ALIASES: dict[str, str] = {
    "din kulturu ahlak bilgisi": "din kulturu",
    "din k a b": "din kulturu",          # K12 kısaltması "Din K.ve A.B."
    "turk dili edebiyati": "edebiyat",
    "sosyal bilgiler": "sosyal bilimler",
    "yabanci dil": "ingilizce",
    "matematik geometri": "matematik",
    "fen": "fen bilimleri",
    # LGS belgeleri "Tarih" der; sistem dersi "T.C. İnkılap Tarihi ve Atatürkçülük".
    # TYT evreninde de güvenli: "TYT Tarih" adı da bu kanona iner (simetrik).
    "tarih": "t c inkilap tarihi ataturkculuk",
}


class ExamImportError(Exception):
    """Servis hatası — router HTTP koduna çevirir."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


# ============================================================================
# Evren → aday ders/konu kümeleri
# ============================================================================


def universe_subjects(db: Session, universe: str, student: User) -> list[Subject]:
    """Evrenin normalize hedefi olan builtin dersler.

    TYT/AYT için ek ayraç `curriculum_model IS NULL` ŞART: sınav taksonomisi
    model-bağımsızdır; eski okul dersleri de (Klasik/Maarif "Matematik")
    exam_section taşıyabilir — onlar TYT evreninin hedefi DEĞİL (karışırsa
    ders çözümü okul dersine gider, konu eşleşmesi çöker).
    """
    q = db.query(Subject).filter(Subject.is_builtin.is_(True))
    if universe == EXAM_UNIVERSE_TYT:
        return q.filter(
            Subject.exam_section == ExamSection.TYT,
            Subject.curriculum_model.is_(None),
        ).all()
    if universe == EXAM_UNIVERSE_AYT:
        return q.filter(
            Subject.exam_section.in_([
                ExamSection.AYT_SAY, ExamSection.AYT_EA,
                ExamSection.AYT_SOZ, ExamSection.AYT_DIL,
            ]),
            Subject.curriculum_model.is_(None),
        ).all()
    if universe == EXAM_UNIVERSE_LGS:
        return q.filter(Subject.curriculum_model == CurriculumModel.LGS).all()
    # OKUL — öğrencinin okul müfredatı (Maarif/Klasik), sınıfını kapsayan dersler
    model = student.effective_curriculum_model
    subs = q.filter(Subject.curriculum_model == model).all()
    return [s for s in subs
            if s.covers_grade(student.grade_level, is_graduate=student.is_graduate)]


def universe_topics(
    db: Session, subjects: list[Subject], *, universe: str, grade_cap: int | None,
) -> list[Topic]:
    """Evrenin LEAF konuları (tema/parent başlıkları aday DEĞİL).

    grade_cap (okul/lgs kazanım testleri): konunun grade_level'ı verilmişse
    öğrencinin sınıfını aşan konular aday olmaz. TYT/AYT'de cap uygulanmaz
    (sınav taksonomisi kümülatiftir).
    """
    if not subjects:
        return []
    sids = [s.id for s in subjects]
    topics = db.query(Topic).filter(Topic.subject_id.in_(sids)).all()
    parent_ids = {t.parent_id for t in topics if t.parent_id is not None}
    leafs = [t for t in topics if t.id not in parent_ids]
    if universe in (EXAM_UNIVERSE_OKUL, EXAM_UNIVERSE_LGS) and grade_cap:
        leafs = [t for t in leafs
                 if t.grade_level is None or t.grade_level <= grade_cap]
    return sorted(leafs, key=lambda t: (t.subject_id, t.order, t.id))


# ============================================================================
# Ders çözümü (ham ders adı → sistem dersi)
# ============================================================================


def _subject_key(name: str | None) -> str:
    """Ders adı → eşleştirme anahtarı (TYT-/AYT- önekleri + bağlaç atılır)."""
    key = _label_key(name)
    return _SUBJECT_ALIASES.get(key, key)


def _subjects_by_key(subjects: list[Subject]) -> dict[str, Subject]:
    out: dict[str, Subject] = {}
    for s in sorted(subjects, key=lambda x: x.id):
        k = _subject_key(s.name)
        if k and k not in out:
            out[k] = s
        # alias iki yönlü çalışsın: sistem adının alias karşılığı da anahtar olsun
        ak = _SUBJECT_ALIASES.get(k)
        if ak and ak not in out:
            out[ak] = s
    return out


def resolve_subject(raw_name: str | None, by_key: dict[str, Subject]) -> Subject | None:
    if not raw_name:
        return None
    return by_key.get(_subject_key(raw_name))


# ============================================================================
# Konu normalizasyonu — 4 katman
# ============================================================================


def _alias_lookup(
    db: Session, universe: str, subject_id: int | None, label_key: str,
) -> ExamTopicAlias | None:
    if not label_key:
        return None
    return (
        db.query(ExamTopicAlias)
        .filter(
            ExamTopicAlias.scope == universe,
            ExamTopicAlias.subject_id == subject_id,
            ExamTopicAlias.label_key == label_key,
        )
        .first()
    )


def _deterministic_match(
    label_key: str,
    home_map: dict[str, Topic],
    universe_map: dict[str, list[Topic]],
) -> Topic | None:
    """Katman 1 — birebir + ÖN-EK (kesik etiket). Belirsizlik → None (asla tahmin)."""
    if not label_key:
        return None
    hit = home_map.get(label_key)
    if hit is not None:
        return hit
    # Kesik etiket ("paragrafta yardimci dusu"): home dersinde TEK ön-ek adayı
    if len(label_key) >= 6:
        pref = [t for k, t in home_map.items() if k.startswith(label_key)]
        if len(pref) == 1:
            return pref[0]
    # Evren genelinde TEKİL birebir eşleşme (ders başlığı yanlış/eksikse —
    # örn. geometri konusu "Matematik" bölümünde): yalnız tek derste varsa güvenli.
    uni = universe_map.get(label_key)
    if uni and len(uni) == 1:
        return uni[0]
    return None


_AI_LABEL_BATCH = 25


def _ai_match_labels(
    labels: list[dict], candidates: list[Topic], subj_names: dict[int, str],
) -> dict[int, int]:
    """Katman 2 — kapalı-küme Gemini. labels: [{key(int idx), subject, label}].

    Dönen {idx: topic_id} — yalnız aday listesindeki id'ler (uydurma düşürülür).
    Best-effort: hata → boş (satırlar 'eşleşmedi' kalır, akış ölmez).
    """
    if not labels or not candidates:
        return {}
    topic_lines = "\n".join(
        f"{t.id}: {t.name} [{subj_names.get(t.subject_id, '?')}]" for t in candidates
    )
    out: dict[int, int] = {}
    valid_ids = {t.id for t in candidates}
    for i in range(0, len(labels), _AI_LABEL_BATCH):
        batch = labels[i:i + _AI_LABEL_BATCH]
        lab_lines = "\n".join(
            f"{r['key']}: {r['label']} (dersi: {r['subject'] or '?'})" for r in batch
        )
        prompt = (
            "Deneme sınavındaki YAYINEVİ konu etiketlerini resmi müfredat "
            "konularına eşle. Etiketler kısaltılmış/farklı adlandırılmış olabilir "
            "(örn. 'İşlem Yeteneği' → 'Temel Kavramlar'); ANLAM olarak eşleştir. "
            "Konu, etiketin dersinden farklı bir derse ait olabilir (örn. geometri "
            "konusu Matematik bölümünde). Emin değilsen topic_id=null bırak — "
            "ASLA zorlama eşleştirme yapma. Yalnız listedeki topic_id'leri kullan.\n\n"
            f"RESMİ KONULAR (topic_id: ad [ders]):\n{topic_lines}\n\n"
            f"ETİKETLER (key: etiket):\n{lab_lines}\n\n"
            'Yalnız JSON dön: {"mappings":[{"key":N,"topic_id":N|null}]}'
        )
        try:
            raw = gemini.generate(
                [gemini.text_part(prompt)],
                personal_data=False, json_mode=True, max_output_tokens=16384,
            )
            try:
                mappings = gemini.extract_json(raw).get("mappings") or []
            except Exception:  # noqa: BLE001 — Gemini bazen düz dizi döndürür
                parsed = json.loads(raw.strip().strip("`").removeprefix("json"))
                mappings = parsed if isinstance(parsed, list) else []
            keys = {r["key"] for r in batch}
            for m in mappings:
                if not isinstance(m, dict):
                    continue
                k, tid = m.get("key"), m.get("topic_id")
                if k in keys and tid in valid_ids:
                    out[int(k)] = int(tid)
        except Exception as e:  # noqa: BLE001 — best-effort katman
            logger.warning("exam_import AI konu eşleme parti hatası: %s", e)
    return out


def normalize_topics(
    db: Session,
    rows: list[dict],
    *,
    universe: str,
    subjects: list[Subject],
    topics: list[Topic],
    use_ai: bool = True,
) -> dict[str, int]:
    """Satırların konularını normalize et (yerinde). Dönen: katman istatistikleri.

    Her satıra yazılır: subject_id/subject_name (konudan türetilmiş nihai ders),
    topic_id/topic_name, topic_source (alias|auto|ai|none).
    """
    by_key = _subjects_by_key(subjects)
    subj_by_id = {s.id: s for s in subjects}
    subj_names = {s.id: s.name for s in subjects}

    # ders bazlı + evren geneli konu anahtar haritaları
    home_maps: dict[int, dict[str, Topic]] = {}
    universe_map: dict[str, list[Topic]] = {}
    for t in topics:
        k = _topic_key(t.name)
        if not k:
            continue
        home_maps.setdefault(t.subject_id, {}).setdefault(k, t)
        bucket = universe_map.setdefault(k, [])
        if all(x.subject_id != t.subject_id for x in bucket):
            bucket.append(t)

    stats = {"alias": 0, "auto": 0, "ai": 0, "none": 0}
    ai_pending: dict[tuple[int | None, str], list[int]] = {}  # (home_sid, lkey) → satır idx'leri

    for idx, row in enumerate(rows):
        home = resolve_subject(row.get("subject_raw"), by_key)
        home_sid = home.id if home else None
        row["subject_id"] = home_sid
        row["subject_name"] = home.name if home else None
        lkey = _label_key(row.get("topic_raw"))
        row["_label_key"] = lkey
        row["_home_subject_id"] = home_sid
        if not lkey:
            row["topic_id"] = None
            row["topic_name"] = None
            row["topic_source"] = "none"
            stats["none"] += 1
            continue

        # Katman 0 — öğrenen sözlük
        alias = _alias_lookup(db, universe, home_sid, lkey)
        if alias is not None and alias.topic_id in {t.id for t in topics}:
            tp = next(t for t in topics if t.id == alias.topic_id)
            _assign_topic(row, tp, subj_by_id, source="alias")
            alias.hit_count = (alias.hit_count or 0) + 1
            stats["alias"] += 1
            continue

        # Katman 1 — deterministik (birebir + ön-ek + evren-tekil)
        home_map = home_maps.get(home_sid, {}) if home_sid else {}
        det = _deterministic_match(lkey, home_map, universe_map)
        if det is not None:
            _assign_topic(row, det, subj_by_id, source="auto")
            stats["auto"] += 1
            continue

        # Katman 2'ye aday (etiket düzeyinde tekilleştirilir)
        ai_pending.setdefault((home_sid, lkey), []).append(idx)

    if use_ai and ai_pending:
        label_items = [
            {"key": i, "subject": (subj_names.get(sid) if sid else rows[idxs[0]].get("subject_raw")),
             "label": rows[idxs[0]].get("topic_raw") or ""}
            for i, ((sid, _lk), idxs) in enumerate(ai_pending.items())
        ]
        ai_hits = _ai_match_labels(label_items, topics, subj_names)
        topic_by_id = {t.id: t for t in topics}
        for i, ((_sid, _lk), idxs) in enumerate(ai_pending.items()):
            tid = ai_hits.get(i)
            tp = topic_by_id.get(tid) if tid else None
            for ridx in idxs:
                if tp is not None:
                    _assign_topic(rows[ridx], tp, subj_by_id, source="ai")
                    stats["ai"] += 1
                else:
                    rows[ridx]["topic_id"] = None
                    rows[ridx]["topic_name"] = None
                    rows[ridx]["topic_source"] = "none"
                    stats["none"] += 1
    else:
        for (_sid, _lk), idxs in ai_pending.items():
            for ridx in idxs:
                rows[ridx]["topic_id"] = None
                rows[ridx]["topic_name"] = None
                rows[ridx]["topic_source"] = "none"
                stats["none"] += 1
    return stats


def _assign_topic(row: dict, tp: Topic, subj_by_id: dict[int, Subject], *, source: str) -> None:
    row["topic_id"] = tp.id
    row["topic_name"] = tp.name
    row["topic_source"] = source
    # Nihai ders = konunun dersi (geometri sorusu Matematik bölümünde olsa da)
    row["subject_id"] = tp.subject_id
    s = subj_by_id.get(tp.subject_id)
    if s is not None:
        row["subject_name"] = s.name


# ============================================================================
# Çift okuma birleştirme + deterministik kontroller
# ============================================================================


def merge_reads(r1: dict, r2: dict) -> tuple[dict, int]:
    """İki bağımsız okumayı birleştir; uyuşmayan hücre → satır 'şüpheli'.

    Hizalama ders bazında: soru numaraları iki okumada BÜYÜK ölçüde kesişiyorsa
    numarayla; kesişmiyorsa (örn. Fen bölümü 1-20 sürekli numaralı — bir okuma
    Kimya'yı 8-14, diğeri 1-7 numaralandırmış; GERÇEK Apotemi PDF'inde görüldü)
    DERS İÇİ SIRA ile eşlenir — aksi halde aynı sorular iki kez sayılır.
    Dönen: (birleşik okuma, şüpheli satır sayısı).
    """
    def _buckets(read: dict) -> dict[str, list[dict]]:
        out: dict[str, list[dict]] = {}
        for q in read["questions"]:
            out.setdefault(normalize(q["subject"]), []).append(q)
        return out

    b1, b2 = _buckets(r1), _buckets(r2)
    order = list(b1)
    order += [s for s in b2 if s not in b1]

    merged_rows: list[dict] = []
    suspects = 0
    for sk in order:
        l1, l2 = b1.get(sk, []), b2.get(sk, [])
        nos1 = [q["no"] for q in l1 if q.get("no") is not None]
        nos2 = [q["no"] for q in l2 if q.get("no") is not None]
        inter = set(nos1) & set(nos2)
        by_no = (
            len(nos1) == len(set(nos1)) and len(nos2) == len(set(nos2))
            and bool(inter)
            and len(inter) >= max(1, min(len(nos1), len(nos2)) // 2)
        )
        if by_no:
            i1 = {int(q["no"]): q for q in l1 if q.get("no") is not None}
            i2 = {int(q["no"]): q for q in l2 if q.get("no") is not None}
            keys: list[tuple[dict | None, dict | None]] = [
                (i1.get(n), i2.get(n)) for n in sorted(set(i1) | set(i2))
            ]
        else:
            # sıra-bazlı hizalama (numaralar güvenilmez/kesişmiyor)
            n = max(len(l1), len(l2))
            keys = [(l1[i] if i < len(l1) else None,
                     l2[i] if i < len(l2) else None) for i in range(n)]

        for q1, q2 in keys:
            base = dict(q1 or q2)  # type: ignore[arg-type]
            suspect = False
            if q1 is None or q2 is None:
                suspect = True  # yalnız bir okumada var
            else:
                if normalize(q1["topic"]) != normalize(q2["topic"]):
                    suspect = True
                for f in ("correct_answer", "student_answer", "result"):
                    if q1.get(f) != q2.get(f):
                        suspect = True
                        # boş-olmayan değeri tercih et
                        base[f] = q1.get(f) if q1.get(f) is not None else q2.get(f)
            base["_suspect"] = suspect
            if suspect:
                suspects += 1
            merged_rows.append(base)

    merged = dict(r1)
    merged["questions"] = merged_rows
    # özet tablo: uyuşmuyorsa r1 esas + kontrol katmanı yakalar
    return merged, suspects


def _derive_result(row: dict) -> tuple[str | None, bool]:
    """DC/ÖC'den sonucu türet — sembol okumasından DAHA güvenilir.

    Dönen: (nihai sonuç, sembol-türetme çelişkisi var mı).
    """
    dc, oc, res = row.get("correct_answer"), row.get("student_answer"), row.get("result")
    if dc is not None:
        derived = EQ_RESULT_BOS if oc is None else (
            EQ_RESULT_DOGRU if oc == dc else EQ_RESULT_YANLIS
        )
        return derived, (res is not None and res != derived)
    if oc is None and res is None:
        return EQ_RESULT_BOS, False
    return res, False


def run_checks(read: dict, rows: list[dict]) -> list[dict]:
    """Deterministik iç tutarlılık — format-bağımsız, KOŞULLU katmanlar.

    Belge özet tablosu içeriyorsa satır sayımlarıyla çapraz sağlanır (bonus);
    içermiyorsa yalnız satır-içi kontroller çalışır. Başarısız kontrol akışı
    DURDURMAZ — önizlemede uyarı bandı olur.
    """
    checks: list[dict] = []

    # satır bazlı ders sayımları
    tallies: dict[str, dict[str, int]] = {}
    for r in rows:
        sk = normalize(r.get("subject_raw"))
        t = tallies.setdefault(sk, {"n": 0, "d": 0, "y": 0, "b": 0})
        t["n"] += 1
        res = r.get("result")
        if res == EQ_RESULT_DOGRU:
            t["d"] += 1
        elif res == EQ_RESULT_YANLIS:
            t["y"] += 1
        elif res == EQ_RESULT_BOS:
            t["b"] += 1

    for s in read.get("subjects") or []:
        sk = normalize(s["name"])
        t = tallies.get(sk)
        if t is None:
            continue  # özetteki üst bölüm başlığı (örn. "TYT-SOSYAL") — satırlar alt derste
        parts = []
        ok = True
        if s.get("questions") is not None and t["n"] != s["questions"]:
            ok = False
            parts.append(f"satır {t['n']} ≠ özet soru {s['questions']}")
        for k, dk, label in (("correct", "d", "doğru"), ("wrong", "y", "yanlış"),
                             ("blank", "b", "boş")):
            if s.get(k) is not None and t[dk] != s[k]:
                ok = False
                parts.append(f"{label}: satır {t[dk]} ≠ özet {s[k]}")
        checks.append({
            "code": f"subject_counts:{sk}",
            "label": f"{s['name']} — özet ↔ soru satırları",
            "ok": ok,
            "detail": "; ".join(parts) if parts else
                      f"{t['n']} soru · {t['d']}D {t['y']}Y {t['b']}B",
        })
    return checks


# ============================================================================
# Evren / tür tespiti
# ============================================================================


def detect_universe(read: dict, student: User) -> dict:
    """Üç kaynak (başlık anahtar kelimeleri + yapı + öğrenci bağlamı) oylar.

    Dönen: {universe, section, scope, confidence}. Emin olunamazsa en olası
    seçilir + confidence düşük — önizlemede tür seçici gösterilir, koç düzeltir.
    """
    hints = " ".join(read.get("type_hints") or []) + " " + (read.get("exam_title") or "")
    h = normalize(hints)
    n_q = len(read["questions"])
    subj_keys = {normalize(q["subject"]) for q in read["questions"]}
    n_subj = len(subj_keys)
    grade = read.get("grade_hint") or student.grade_level

    votes: dict[str, int] = {u: 0 for u in EXAM_UNIVERSES}
    # 1) anahtar kelime
    if re.search(r"\btyt\b|\bmsu\b", h):
        votes[EXAM_UNIVERSE_TYT] += 2
    if re.search(r"\bayt\b", h):
        votes[EXAM_UNIVERSE_AYT] += 2
    if re.search(r"\blgs\b", h):
        votes[EXAM_UNIVERSE_LGS] += 2
    if re.search(r"\bkazanim\b|\byazili\b|\bokul\b", h):
        votes[EXAM_UNIVERSE_OKUL] += 2
    # 2) yapı
    if 100 <= n_q <= 130 and n_subj >= 6:
        votes[EXAM_UNIVERSE_TYT] += 1
    elif 70 <= n_q <= 95 and n_subj >= 5 and grade is not None and grade <= 8:
        votes[EXAM_UNIVERSE_LGS] += 1
    elif 60 <= n_q <= 90 and n_subj >= 2:
        votes[EXAM_UNIVERSE_AYT] += 1
    # 3) öğrenci bağlamı
    if student.is_graduate or (student.grade_level or 0) >= 9:
        votes[EXAM_UNIVERSE_TYT] += 1
        votes[EXAM_UNIVERSE_AYT] += 0  # nötr — TYT daha yaygın
    elif student.grade_level is not None and student.grade_level <= 8:
        votes[EXAM_UNIVERSE_LGS] += 1

    universe = max(votes, key=lambda u: votes[u])
    top = votes[universe]
    confidence = "high" if top >= 3 else ("medium" if top == 2 else "low")
    scope = "brans" if n_subj <= 2 else "full"

    section = _section_for(universe, read, student)
    return {"universe": universe, "section": section.value,
            "scope": scope, "confidence": confidence}


def _section_for(universe: str, read: dict, student: User) -> ExamSection:
    if universe == EXAM_UNIVERSE_TYT:
        return ExamSection.TYT
    if universe == EXAM_UNIVERSE_LGS:
        return ExamSection.LGS
    if universe == EXAM_UNIVERSE_OKUL:
        return ExamSection.OKUL
    # AYT — ders listesinden alan çıkarımı; olmadı öğrencinin alanı; olmadı SAY
    subj = " ".join(normalize(q["subject"]) for q in read["questions"])
    has_edb = "edebiyat" in subj or "turk dili" in subj
    has_fen = any(x in subj for x in ("fizik", "kimya", "biyoloji"))
    has_sos2 = any(x in subj for x in ("felsefe", "din"))
    if has_edb and has_sos2:
        return ExamSection.AYT_SOZ
    if has_edb:
        return ExamSection.AYT_EA
    if has_fen:
        return ExamSection.AYT_SAY
    if student.track is not None:
        return _TRACK_TO_AYT_SECTION.get(student.track, ExamSection.AYT_SAY)
    return ExamSection.AYT_SAY


_SECTION_TO_UNIVERSE = {
    ExamSection.TYT: EXAM_UNIVERSE_TYT,
    ExamSection.AYT_SAY: EXAM_UNIVERSE_AYT,
    ExamSection.AYT_EA: EXAM_UNIVERSE_AYT,
    ExamSection.AYT_SOZ: EXAM_UNIVERSE_AYT,
    ExamSection.AYT_DIL: EXAM_UNIVERSE_AYT,
    ExamSection.LGS: EXAM_UNIVERSE_LGS,
    ExamSection.OKUL: EXAM_UNIVERSE_OKUL,
}


def universe_for_section(section: ExamSection) -> str:
    return _SECTION_TO_UNIVERSE[section]


# ============================================================================
# ANALYZE — PDF → önizleme taslağı
# ============================================================================


def analyze(
    db: Session,
    student: User,
    pdf_bytes: bytes,
    *,
    force_section: str | None = None,
) -> dict:
    """Çift Gemini okuma + birleştirme + kontroller + tespit + normalizasyon.

    Kredi tüketimi ROUTER'dadır (consume_credits bu çağrıyı sarar).
    force_section: koç önizlemede türü değiştirdiyse yeniden normalize etmek
    için (yeni Gemini OKUMASI yapılmaz — okunanlar yeni evrenle eşlenir) —
    Faz 1'de yalnız ilk analiz kullanılır.
    """
    b64 = base64.b64encode(pdf_bytes).decode("ascii")
    r1, r2 = ai_exam_import.read_exam_pdf_double(b64)
    merged, _ = merge_reads(r1, r2)

    det = detect_universe(merged, student)
    if force_section:
        try:
            sec = ExamSection(force_section)
        except ValueError:
            raise ExamImportError(422, "invalid_section", "Geçersiz sınav türü.")
        det["universe"] = universe_for_section(sec)
        det["section"] = sec.value
        det["confidence"] = "high"

    universe = det["universe"]
    subjects = universe_subjects(db, universe, student)
    grade_cap = merged.get("grade_hint") or student.grade_level
    topics = universe_topics(db, subjects, universe=universe, grade_cap=grade_cap)

    # okuma satırları → çalışma satırları
    rows: list[dict] = []
    for q in merged["questions"]:
        res, res_conflict = _derive_result(q)
        rows.append({
            "subject_raw": q["subject"],
            "question_no": q.get("no"),
            "topic_raw": q["topic"],
            "correct_answer": q.get("correct_answer"),
            "student_answer": q.get("student_answer"),
            "result": res,
            "is_suspect": bool(q.get("_suspect")) or res_conflict or res is None,
        })

    stats = normalize_topics(db, rows, universe=universe, subjects=subjects, topics=topics)
    checks = run_checks(merged, rows)

    # tür-evren çapraz kontrolü: konuların çoğu eşleşmediyse tür yanlış olabilir
    matched = stats["alias"] + stats["auto"] + stats["ai"]
    if rows:
        checks.append({
            "code": "universe_match",
            "label": "Tür ↔ müfredat uyumu",
            "ok": matched >= max(1, len(rows) // 3),
            "detail": f"{matched}/{len(rows)} soru müfredat konusuna eşlendi"
                      + ("" if matched >= max(1, len(rows) // 3)
                         else " — sınav türü yanlış seçilmiş olabilir, üstten değiştirip yeniden deneyin"),
        })

    # ders özet grupları (satırlardan; belge özeti varsa net'i yanına)
    doc_net_by_key = {normalize(s["name"]): s.get("net")
                      for s in merged.get("subjects") or []}
    groups: dict[str, dict] = {}
    for r in rows:
        gname = r.get("subject_name") or r.get("subject_raw") or "Diğer"
        g = groups.setdefault(gname, {"name": gname, "questions": 0, "correct": 0,
                                      "wrong": 0, "blank": 0})
        g["questions"] += 1
        if r["result"] == EQ_RESULT_DOGRU:
            g["correct"] += 1
        elif r["result"] == EQ_RESULT_YANLIS:
            g["wrong"] += 1
        elif r["result"] == EQ_RESULT_BOS:
            g["blank"] += 1
    section = ExamSection(det["section"])
    penalty = section_penalty(section)
    subjects_out = []
    for g in groups.values():
        g["net"] = round(max(g["correct"] - g["wrong"] / penalty, 0.0), 2)
        g["doc_net"] = doc_net_by_key.get(normalize(g["name"]))
        subjects_out.append(g)

    # mükerrer uyarısı (ad+tarih)
    dup_id = None
    exam_date = _parse_date(merged.get("exam_date"))
    if merged.get("exam_title") and exam_date:
        dup = (
            db.query(ExamResult.id)
            .filter(
                ExamResult.student_id == student.id,
                ExamResult.title == merged["exam_title"][:200],
                ExamResult.exam_date == exam_date,
            )
            .first()
        )
        dup_id = dup[0] if dup else None

    # NOT: burada commit YOK — router, kredi bağlamıyla (consume_credits)
    # birlikte commit eder (alias hit_count artışları da onunla kalıcılaşır).
    suspect_count = sum(1 for r in rows if r["is_suspect"])

    # Önizlemede koçun konu SEÇEBİLMESİ için evrenin aday konuları
    subj_names_all = {s.id: s.name for s in subjects}
    topic_choices = [
        {"id": t.id, "name": t.name,
         "subject_name": subj_names_all.get(t.subject_id, "?")}
        for t in topics
    ]

    return {
        "title": merged.get("exam_title"),
        "exam_date": exam_date.isoformat() if exam_date else None,
        "grade_hint": merged.get("grade_hint"),
        "universe": universe,
        "section": det["section"],
        "section_label": EXAM_SECTION_LABELS[section],
        "scope": det["scope"],
        "confidence": det["confidence"],
        "subjects": subjects_out,
        "rows": [
            {k: v for k, v in r.items() if not k.startswith("_")}
            for r in rows
        ],
        "checks": checks,
        "suspect_count": suspect_count,
        "match_stats": stats,
        "duplicate_exam_id": dup_id,
        "score_info": merged.get("score_info"),
        "topic_choices": topic_choices,
    }


def _parse_date(v: str | None) -> date | None:
    if not v:
        return None
    try:
        return date.fromisoformat(v.strip()[:10])
    except ValueError:
        return None


# ============================================================================
# CONFIRM — düzeltilmiş taslak → ExamResult + soru satırları + sözlük
# ============================================================================


def confirm(
    db: Session,
    student: User,
    payload: dict,
    *,
    pdf_bytes: bytes | None,
    content_type: str | None,
    actor: User,
) -> ExamResult:
    """Önizlemede onaylanan taslağı kaydet.

    - Toplamlar + net, DÜZELTİLMİŞ satırlardan yeniden hesaplanır (satırlar esas).
    - topic_id'ler evren aday kümesine karşı yeniden doğrulanır (dışarıdan
      rastgele id enjekte edilemez).
    - Öğrenen sözlük güncellenir: koç düzeltmesi AI eşleşmesini ezer; tersi ezemez.
    """
    title = (payload.get("title") or "").strip()[:200]
    if not title:
        raise ExamImportError(422, "title_required", "Deneme adı zorunlu.")
    exam_date = _parse_date(payload.get("exam_date"))
    if exam_date is None:
        raise ExamImportError(422, "invalid_date", "Geçersiz tarih (YYYY-AA-GG).")
    try:
        section = ExamSection(str(payload.get("section") or ""))
    except ValueError:
        raise ExamImportError(422, "invalid_section", "Geçersiz sınav türü.")
    universe = universe_for_section(section)

    rows_in = payload.get("rows") or []
    if not rows_in:
        raise ExamImportError(422, "no_rows", "En az bir soru satırı gerekir.")
    if len(rows_in) > 400:
        raise ExamImportError(422, "too_many_rows", "Soru sayısı sınırı aşıldı (400).")

    # mükerrer koruması
    if not payload.get("force"):
        dup = (
            db.query(ExamResult.id)
            .filter(
                ExamResult.student_id == student.id,
                ExamResult.title == title,
                ExamResult.exam_date == exam_date,
            )
            .first()
        )
        if dup:
            raise ExamImportError(
                409, "duplicate_exam",
                "Bu deneme zaten kayıtlı görünüyor (aynı ad + tarih). "
                "Yine de kaydetmek için onayla.",
            )

    subjects = universe_subjects(db, universe, student)
    grade_cap = payload.get("grade_hint") or student.grade_level
    topics = universe_topics(db, subjects, universe=universe, grade_cap=grade_cap)
    topic_by_id = {t.id: t for t in topics}
    subj_by_id = {s.id: s for s in subjects}
    by_key = _subjects_by_key(subjects)

    penalty = section_penalty(section)
    totals = {"correct": 0, "wrong": 0, "blank": 0}
    groups: dict[str, dict] = {}
    q_rows: list[ExamResultQuestion] = []

    for r in rows_in:
        res = str(r.get("result") or "").strip().lower()
        if res not in EQ_RESULTS:
            raise ExamImportError(422, "invalid_result",
                                  "Soru sonucu dogru/yanlis/bos olmalı.")
        tid = r.get("topic_id")
        tp = topic_by_id.get(int(tid)) if tid is not None else None
        # nihai ders: konu varsa konunun dersi; yoksa ham addan çözülen
        home = resolve_subject(r.get("subject_raw"), by_key)
        sid = tp.subject_id if tp is not None else (home.id if home else None)

        raw_label = (str(r.get("topic_raw") or "").strip()[:200]) or None
        q_rows.append(ExamResultQuestion(
            question_no=r.get("question_no"),
            subject_name_raw=(str(r.get("subject_raw") or "").strip()[:120]) or None,
            subject_id=sid,
            topic_label_raw=raw_label,
            topic_id=tp.id if tp is not None else None,
            correct_answer=(str(r.get("correct_answer") or "").strip()[:8].upper()) or None,
            student_answer=(str(r.get("student_answer") or "").strip()[:8].upper()) or None,
            result=res,
            is_suspect=bool(r.get("is_suspect")),
            manually_edited=bool(r.get("manually_edited")),
        ))

        key = ("dogru", "yanlis", "bos").index(res)
        totals[("correct", "wrong", "blank")[key]] += 1
        gname = (subj_by_id[sid].name if sid in subj_by_id else None) \
            or (str(r.get("subject_raw") or "").strip() or "Diğer")
        g = groups.setdefault(gname, {"name": gname, "correct": 0, "wrong": 0, "blank": 0})
        g[("correct", "wrong", "blank")[key]] += 1

        # sözlük öğrenmesi için izler
        r["_final_topic"] = tp
        r["_home_subject_id"] = home.id if home else None

    subject_payload = []
    for g in groups.values():
        g["net"] = round(max(g["correct"] - g["wrong"] / penalty, 0.0), 2)
        subject_payload.append(g)

    net = compute_net(totals["correct"], totals["wrong"], section)

    meta = {
        "universe": universe,
        "scope": payload.get("scope") or "full",
        "grade_hint": payload.get("grade_hint"),
        "score_info": payload.get("score_info"),
        "suspect_count": sum(1 for r in rows_in if r.get("is_suspect")),
        "edited_count": sum(1 for r in rows_in if r.get("manually_edited")),
        "imported_at": datetime.now(timezone.utc).isoformat(),
    }

    exam = ExamResult(
        student_id=student.id,
        created_by_id=actor.id,
        title=title,
        exam_date=exam_date,
        section=section,
        total_correct=totals["correct"],
        total_wrong=totals["wrong"],
        total_blank=totals["blank"],
        net=net,
        subject_nets=json.dumps(subject_payload, ensure_ascii=False),
        note=(str(payload.get("note") or "").strip()[:500]) or None,
        import_source="pdf_import",
        import_pdf_content_type=content_type if pdf_bytes else None,
        import_pdf_size=len(pdf_bytes) if pdf_bytes else None,
        import_pdf_data=pdf_bytes,
        analysis_meta=json.dumps(meta, ensure_ascii=False),
    )
    db.add(exam)
    db.flush()
    for q in q_rows:
        q.exam_result_id = exam.id
        db.add(q)

    _learn_aliases(db, universe, rows_in, actor=actor)
    db.commit()
    db.refresh(exam)
    return exam


def _learn_aliases(db: Session, universe: str, rows_in: list[dict], *, actor: User) -> None:
    """Onaylanan eşlemeleri sözlüğe yaz — koç düzeltmesi AI'ı ezer, tersi ezemez."""
    seen: set[tuple[int | None, str]] = set()
    for r in rows_in:
        tp: Topic | None = r.get("_final_topic")
        if tp is None:
            continue
        lkey = _label_key(r.get("topic_raw"))
        if not lkey:
            continue
        home_sid = r.get("_home_subject_id")
        k = (home_sid, lkey)
        if k in seen:
            continue
        seen.add(k)
        source = ALIAS_SOURCE_COACH if r.get("manually_edited") else ALIAS_SOURCE_AI
        alias = _alias_lookup(db, universe, home_sid, lkey)
        if alias is None:
            db.add(ExamTopicAlias(
                scope=universe, subject_id=home_sid, label_key=lkey,
                label_raw=(str(r.get("topic_raw") or "").strip()[:200]) or None,
                topic_id=tp.id, source=source, hit_count=1,
                created_by_id=actor.id,
            ))
        elif alias.topic_id != tp.id:
            # farklı hedef: yalnız koç düzeltmesi mevcut kaydı değiştirebilir;
            # koç kaydını AI değiştiremez.
            if source == ALIAS_SOURCE_COACH or alias.source != ALIAS_SOURCE_COACH:
                alias.topic_id = tp.id
                alias.source = source
                alias.created_by_id = actor.id
        else:
            alias.hit_count = (alias.hit_count or 0) + 1

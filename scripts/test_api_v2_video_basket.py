# -*- coding: utf-8 -*-
"""Video Sepeti smoke testi (YouTube taklit — ağ yok).

Kapsam: URL çözümleme · ISO süre · segmentasyon (checkpoint önceki konuya,
tanıtım ayrı, alias) · içe aktarma + mükerrer atlama · anahtar yok → 503 ·
bozuk link → 422 · programa koy (aynı gün+konu → tek görev, çok video) ·
60 dk uyarısı · görev.videos serileştirme · taşı · geri al (son video → görev
silinir) · görev silinince video sepete döner · izlenen videoyu geri alma 409 ·
grup düzenleme (konu/etiket → başlık yenilenir) · kopyala · sahiplik 404.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import Subject, Task, TaskStatus, User, UserRole
from app.models.video_basket import VideoBasketItem, VideoSource
from app.services import gemini, system_secrets, youtube_service as yt
from app.services.jwt_auth import issue_access_token
from app.services.security import hash_password
from app.services.video_segmentation import SegVideo, segment

PASS = FAIL = 0


def check(n, c, e=""):
    global PASS, FAIL
    if c:
        PASS += 1
        print(f"  [PASS] {n}")
    else:
        FAIL += 1
        print(f"  [FAIL] {n} {e}")


# --- birim: URL + süre ---
print("URL / süre")
check("playlist URL", yt.parse_youtube_url("https://www.youtube.com/playlist?list=PLabcdefghij12")[:2] == ("playlist", "PLabcdefghij12"))
check("listeli video → liste", yt.parse_youtube_url("https://youtube.com/watch?v=abcdefghijk&list=PLabcdefghij12")[0] == "playlist")
check("youtu.be", yt.parse_youtube_url("youtu.be/abcdefghijk") == ("video", "abcdefghijk", None))
check("shorts", yt.parse_youtube_url("https://m.youtube.com/shorts/abcdefghijk")[1] == "abcdefghijk")
check("mix RD listesi → video", yt.parse_youtube_url("https://www.youtube.com/watch?v=abcdefghijk&list=RDabcdefghijk")[0] == "video")
try:
    yt.parse_youtube_url("https://vimeo.com/123"); check("yabancı site reddi", False)
except yt.YouTubeError as e:
    check("yabancı site reddi", e.code == "bad_url")
check("PT1H2M3S", yt.parse_iso_duration("PT1H2M3S") == 3723)
check("P0D canlı → None", yt.parse_iso_duration("P0D") is None)

# --- taklit YouTube ---
TITLES = [
    ("v0000000000", "TYT Matematik Kampı Tanıtım", 120),
    ("v0000000001", "Temel Kavramlar 1 | TYT Matematik Kampı 1. Gün", 1500),
    ("v0000000002", "Temel Kavramlar 2 | 2. Gün", 1500),
    ("v0000000003", "Checkpoint 1", 900),
    ("v0000000004", "Üslü İfadeler 1", 1200),
    ("v0000000005", "Üslü İfadeler 2 | Kamp", 1200),
    ("v0000000006", "Yaş Problemleri", 1300),
    ("v0000000007", "Yaş Problemleri Soru Çözümü", 800),
]
TITLES2 = [
    ("v0000000001", "Temel Kavramlar 1 | TYT Matematik Kampı 1. Gün", 1500),  # öteki listede de var
    ("w0000000001", "Mantık 1", 1100),
    ("w0000000002", "Mantık Soru Çözümü", 700),
]
PL2_ID = "PLsecondlist99"
FAKE_KEY = {"v": "test-key"}


def fake_get(path, params):
    if not FAKE_KEY["v"]:
        raise yt.YouTubeError("not_configured", "yok")
    second = params.get("playlistId") == PL2_ID or params.get("id") == PL2_ID
    if path == "playlists":
        return {"items": [{"snippet": {"title": "Mantık Kampı" if second else "TYT Mat Kampı",
                                       "channelTitle": "Hoca"}}]}
    if path == "playlistItems" and second:
        return {"items": [{"contentDetails": {"videoId": v}} for v, _, _ in TITLES2]}
    if path == "playlistItems":
        tok = params.get("pageToken")
        chunk = TITLES[:5] if not tok else TITLES[5:]
        out = {"items": [{"contentDetails": {"videoId": v}} for v, _, _ in chunk]}
        if not tok:
            out["nextPageToken"] = "p2"
        return out
    if path == "videos":
        ids = params["id"].split(",")
        return {"items": [{"id": v, "snippet": {"title": t, "channelTitle": "Hoca"},
                           "contentDetails": {"duration": f"PT{s}S"}}
                          for v, t, s in TITLES + TITLES2[1:] if v in ids]}
    raise AssertionError(path)


yt._get = fake_get
yt.is_configured = lambda: bool(FAKE_KEY["v"])
gemini.generate = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("AI kapalı"))

db = SessionLocal()
SUF = "_vbasket_tmp"


def clean():
    uids = [u.id for u in db.query(User).filter(User.email.like(f"%{SUF}@x.com"))]
    if uids:
        db.query(VideoSource).filter(VideoSource.coach_id.in_(uids)).delete(synchronize_session=False)
        db.query(VideoBasketItem).filter(VideoBasketItem.student_id.in_(uids)).delete(synchronize_session=False)
        db.query(Task).filter(Task.student_id.in_(uids)).delete(synchronize_session=False)
        db.query(User).filter(User.id.in_(uids)).delete(synchronize_session=False)
    db.commit()


clean()
try:
    coach = User(email=f"c{SUF}@x.com", full_name="Koç", role=UserRole.TEACHER,
                 password_hash=hash_password("x"), is_active=True)
    other = User(email=f"o{SUF}@x.com", full_name="Öteki", role=UserRole.TEACHER,
                 password_hash=hash_password("x"), is_active=True)
    db.add_all([coach, other]); db.flush()
    st = User(email=f"s{SUF}@x.com", full_name="Öğr A", role=UserRole.STUDENT, teacher_id=coach.id,
              password_hash=hash_password("x"), is_active=True, is_graduate=True)
    st2 = User(email=f"s2{SUF}@x.com", full_name="Öğr B", role=UserRole.STUDENT, teacher_id=coach.id,
               password_hash=hash_password("x"), is_active=True, is_graduate=True)
    db.add_all([st, st2]); db.commit()
    subj = db.query(Subject).filter(Subject.name == "TYT Matematik", Subject.teacher_id.is_(None)).first()
    assert subj, "TYT Matematik seed yok"

    # segmentasyon birim
    from app.services.curriculum_progress import leaf_topics_for_student
    tops = leaf_topics_for_student(db, st, coach.id, [subj.id]).by_subject.get(subj.id, [])
    sg = segment([SegVideo(v, t) for v, t, _ in TITLES], tops, batch_token="b", use_ai=False)
    print("Segmentasyon")
    check("tanıtım = diğer", sg[0].role == "diger")
    check("Temel Kavramlar 1-2 aynı grup", sg[1].group_key == sg[2].group_key and sg[1].topic_id)
    check("checkpoint önceki konuya", sg[3].group_key == sg[1].group_key and sg[3].role == "soru")
    check("Üslü İfadeler → Üslü Sayılar", sg[4].topic_id and "Üslü" in sg[4].group_label and sg[4].group_key == sg[5].group_key)
    check("soru çözümü aynı konu", sg[7].group_key == sg[6].group_key and sg[7].role == "soru")

    c = TestClient(app)
    H = {"Authorization": f"Bearer {issue_access_token(coach)}"}
    HO = {"Authorization": f"Bearer {issue_access_token(other)}"}
    base = f"/api/v2/teacher/students/{st.id}/video-basket"
    PL = "https://www.youtube.com/playlist?list=PLabcdefghij12"

    print("İçe aktarma")
    FAKE_KEY["v"] = ""
    r = c.post(base + "/import", json={"url": PL, "subject_id": subj.id}, headers=H)
    check("anahtar yok → 503", r.status_code == 503 and r.json()["detail"]["code"] == "youtube_not_configured", r.text)
    FAKE_KEY["v"] = "k"
    r = c.post(base + "/import", json={"url": "https://vimeo.com/1", "subject_id": subj.id}, headers=H)
    check("bozuk link → 422", r.status_code == 422, r.text)
    r = c.post(base + "/import", json={"url": PL, "subject_id": subj.id}, headers=H)
    check("içe aktar 200 + 8 video (2 sayfa)", r.status_code == 200 and r.json()["data"]["added"] == 8, r.text)
    r = c.post(base + "/import", json={"url": PL, "subject_id": subj.id}, headers=H)
    check("tekrar içe aktarım mükerrer atlar", r.json()["data"]["added"] == 0 and r.json()["data"]["skipped_existing"] == 8)
    r = c.get(base, headers=H)
    b = r.json()
    check("sepet 200 + gruplar", r.status_code == 200 and len(b["groups"]) >= 4 and b["waiting_count"] == 8, r.text[:300])
    check("yabancı koç 404", c.get(base, headers=HO).status_code == 404)
    g_temel = next(g for g in b["groups"] if "Temel" in g["label"])
    g_uslu = next(g for g in b["groups"] if "Üslü" in g["label"])
    g_yas = next(g for g in b["groups"] if "Yaş" in g["label"])
    check("grup dakikası", g_temel["total_min"] == 25 + 25 + 15, g_temel["total_min"])

    print("Programa koyma")
    d = (date.today() + timedelta(days=2)).isoformat()
    ids_temel = [i["id"] for i in g_temel["items"]]
    r = c.post(base + "/place", json={"item_ids": ids_temel[:2], "date": d}, headers=H)
    check("koy 200", r.status_code == 200, r.text)
    t1 = r.json()["data"]["task_ids"][0]
    r = c.post(base + "/place", json={"item_ids": ids_temel[2:], "date": d}, headers=H)
    check("aynı gün + konu → aynı görev", r.json()["data"]["task_ids"] == [t1], r.text)
    task = db.get(Task, t1); db.refresh(task)
    check("başlık ders·konu + 3 video", task.title.startswith("TYT Matematik · Temel Kavramlar") and "3 video (65 dk)" in task.title, task.title)
    check("görev video tipi + taslak (gelecek)", task.type.value == "video" and task.is_draft)
    check("link_url ilk video", task.link_url and task.link_url.endswith("v0000000001"))
    check("65 dk > 60 → uyarı", r.json()["warnings"] and "65 dk" in r.json()["warnings"][0], r.json()["warnings"])
    wk = c.get(f"/api/v2/teacher/students/{st.id}/day?date={d}", headers=H)
    vids = []
    for tt in (wk.json().get("tasks") or []):
        if tt["id"] == t1:
            vids = tt.get("videos") or []
    check("görev.videos 3 video", len(vids) == 3 and vids[0]["duration_min"] == 25, wk.text[:200])

    d2 = (date.today() + timedelta(days=3)).isoformat()
    r = c.post(base + "/place", json={"item_ids": [ids_temel[0]], "date": d2}, headers=H)
    check("taşı → yeni görev", r.status_code == 200 and r.json()["data"]["task_ids"][0] != t1)
    db.expire_all()
    check("eski görevde 2 video kaldı", db.query(VideoBasketItem).filter(VideoBasketItem.task_id == t1).count() == 2)
    check("küçük gün uyarısız", not r.json()["warnings"])

    print("Geri alma / silme")
    t2 = r.json()["data"]["task_ids"][0]
    r = c.post(f"/api/v2/teacher/video-basket/items/{ids_temel[0]}/unplace", headers=H)
    db.expire_all()
    check("son video geri → görev silinir", r.status_code == 200 and db.get(Task, t2) is None)
    r = c.delete(f"/api/v2/teacher/tasks/{t1}", headers=H)
    check("görev sil ucu 200", r.status_code == 200, r.text[:200])
    db.expire_all()
    check("görev silinince videolar sepete döner",
          db.query(VideoBasketItem).filter(VideoBasketItem.id.in_(ids_temel), VideoBasketItem.task_id.isnot(None)).count() == 0)

    ids_yas = [i["id"] for i in g_yas["items"]]
    r = c.post(base + "/place", json={"item_ids": ids_yas, "date": d}, headers=H)
    ty = db.get(Task, r.json()["data"]["task_ids"][0]); ty.status = TaskStatus.COMPLETED; db.commit()
    r = c.post(f"/api/v2/teacher/video-basket/items/{ids_yas[0]}/unplace", headers=H)
    check("izlenen video geri alınamaz 409", r.status_code == 409, r.text)
    b = c.get(base, headers=H).json()
    gy = next(g for g in b["groups"] if g["group_key"] == g_yas["group_key"])
    check("izlendi durumu", all(i["status"] == "watched" for i in gy["items"]))

    print("Düzenleme / kopyala")
    ids_uslu = [i["id"] for i in g_uslu["items"]]
    r = c.post(base + "/place", json={"item_ids": ids_uslu, "date": d2}, headers=H)
    tu = r.json()["data"]["task_ids"][0]
    r = c.post(base + "/groups", json={"group_key": g_uslu["group_key"], "label": "Üslü Sayılar (Kamp)"}, headers=H)
    db.expire_all()
    check("grup etiketi → görev başlığı yenilenir", r.status_code == 200 and "Üslü Sayılar (Kamp)" in db.get(Task, tu).title, db.get(Task, tu).title)
    r = c.post(f"/api/v2/teacher/video-basket/items/{ids_uslu[1]}", json={"role": "soru"}, headers=H)
    check("rol değiştir", r.status_code == 200 and db.get(VideoBasketItem, ids_uslu[1]).role == "soru")
    r = c.post(f"/api/v2/teacher/video-basket/items/{ids_uslu[1]}", json={"role": "xx"}, headers=H)
    check("geçersiz rol 422", r.status_code == 422)
    r = c.post(base + "/copy", json={"target_student_id": st2.id}, headers=H)
    check("kopyala 8 video", r.status_code == 200 and r.json()["data"]["added"] == 8, r.text)
    r = c.post(base + "/copy", json={"target_student_id": st2.id}, headers=H)
    check("tekrar kopya mükerrer atlar", r.json()["data"]["added"] == 0)
    b2 = c.get(f"/api/v2/teacher/students/{st2.id}/video-basket", headers=H).json()
    check("kopya sepette bekliyor", b2["waiting_count"] == 8)
    r = c.post(base + "/copy", json={"target_student_id": st.id}, headers=H)
    check("aynı öğrenciye kopya 422", r.status_code == 422)
    r = c.post(f"/api/v2/teacher/video-basket/items/{ids_uslu[0]}", json={"role": "soru"}, headers=HO)
    check("yabancı koç öğe 404", r.status_code == 404)
    r = c.post(base + "/groups/delete", json={"group_key": g_uslu["group_key"]}, headers=H)
    check("grup sil programdakileri korur", r.json()["data"]["deleted"] == 0)

    # ---- kayıtlı listeler (liste liste sepet)
    b = c.get(base, headers=H).json()
    s1 = next((x for x in b["sources"] if x["title"] == "TYT Mat Kampı"), None)
    check("ilk liste kayıtlı (8 video, sepette 8)", s1 and s1["in_basket"] == 8 and s1["video_count"] == 8, b["sources"])
    check("tüm gruplar kaynağa bağlı", all(g["source_id"] == s1["id"] for g in b["groups"]))
    check("kayıt kanonik liste linki", s1["url"].endswith("list=PLabcdefghij12"), s1["url"])
    r = c.post(base + "/import", json={"url": f"https://www.youtube.com/playlist?list={PL2_ID}", "subject_id": subj.id}, headers=H)
    d2 = r.json()["data"]
    check("ikinci liste: ortak video da gelir (3)", r.status_code == 200 and d2["added"] == 3 and d2["source_id"] != s1["id"], r.text)
    b = c.get(base, headers=H).json()
    g2 = [g for g in b["groups"] if g["source_id"] == d2["source_id"]]
    check("ikinci listenin grupları ayrı (3 video)", sum(len(g["items"]) for g in g2) == 3)
    check("ilk listeyle karışmadı", sum(len(g["items"]) for g in b["groups"] if g["source_id"] == s1["id"]) == 8)
    check("son kullanılan liste başta", b["sources"][0]["id"] == d2["source_id"] and b["sources"][0]["subject_id"] == subj.id)
    r = c.post(base + "/import", json={"source_id": d2["source_id"]}, headers=H)
    check("kayıtlı listeden yeniden getir (link yok) → mükerrer atlar",
          r.status_code == 200 and r.json()["data"]["added"] == 0 and r.json()["data"]["skipped_existing"] == 3, r.text)
    r = c.post(base + "/import", json={}, headers=H)
    check("link + liste yok → 422 url_required", r.status_code == 422 and r.json()["detail"]["code"] == "url_required", r.text)
    r = c.post(base + "/import", json={"source_id": d2["source_id"]}, headers=HO)
    check("başka koçun listesi → 404", r.status_code == 404)
    src_url = f"/api/v2/teacher/video-sources/{d2['source_id']}"
    r = c.post(src_url, json={"label": "Mantık — hocam", "subject_id": 0}, headers=H)
    lst = c.get(f"/api/v2/teacher/video-sources?student_id={st.id}", headers=H).json()
    e2 = next(x for x in lst if x["id"] == d2["source_id"])
    check("liste adı + ders düzenlenir", r.status_code == 200 and e2["name"] == "Mantık — hocam"
          and e2["title"] == "Mantık Kampı" and e2["subject_id"] is None, e2)
    check("başka koç düzenleyemez 404", c.post(src_url, json={"label": "x"}, headers=HO).status_code == 404)
    check("başka koçun kayıtlı listesi boş", c.get("/api/v2/teacher/video-sources", headers=HO).json() == [])
    r = c.post(base + "/copy", json={"target_student_id": st2.id}, headers=H)
    b2 = c.get(f"/api/v2/teacher/students/{st2.id}/video-basket", headers=H).json()
    check("kopya liste bağını taşır", r.json()["data"]["added"] == 3
          and any(g["source_id"] == d2["source_id"] for g in b2["groups"]), r.text)
    r = c.post(src_url + "/delete", json={"student_id": st.id, "remove_waiting": True}, headers=H)
    check("liste sil + bekleyenleri kaldır", r.status_code == 200 and r.json()["data"]["removed_videos"] == 3, r.text)
    check("liste kayıtlardan gitti", db.get(VideoSource, d2["source_id"]) is None)
    db.expire_all()
    check("öteki öğrencinin videoları kalır (listesiz)",
          db.query(VideoBasketItem).filter(VideoBasketItem.student_id == st2.id, VideoBasketItem.youtube_id == "w0000000001",
                                           VideoBasketItem.source_id.is_(None)).count() == 1)
    r = c.post(f"/api/v2/teacher/video-sources/{s1['id']}/delete", json={}, headers=H)
    check("ilk liste silinince sepet videoları kalır",
          r.status_code == 200 and db.query(VideoBasketItem).filter(VideoBasketItem.student_id == st.id).count() == 8)
finally:
    clean()
    db.close()

print(f"\n{PASS}/{PASS + FAIL} passed")
sys.exit(1 if FAIL else 0)

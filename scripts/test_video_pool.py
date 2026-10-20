"""Video Sepeti → Haftalık Havuz (2026-10-20).

Havuz modundaki öğrencide video grubu güne değil havuza kalem olarak eklenir; öğrenci kaba alınca
videolar o güne açılan VIDEO görevine bağlanır.

  V1 sepet yanıtı program_mode=havuz + açık dönem
  V2 to-pool: 2 grup (3+1 video) → 2 etkinlik kalemi, videolar "pooled"
  V3 dersi seçilmemiş grup → 422 subject_required (hiçbir şey yazılmaz)
  V4 aynı videoyu ikinci kez → 409 nothing_to_pool
  V5 öğrenci kaba alır → VIDEO görevi, 3 video bağlı, link ilk video, öğrenci görevde 3 video görür
  V6 kaptan geri al → videolar yeniden "pooled" (görev bağı boş)
  V7 tekrar kaba al + tamamla → kalem tamam (1/1), videolar "watched"
  V8 rehber diğer kalemi kaldırır → video sepete döner ("waiting")
  V9 gün-gün öğrencide to-pool → 409 not_havuz · başka koç 404

Çalıştır: PYTHONPATH=. python scripts/test_video_pool.py
"""
from __future__ import annotations

import sys

from sqlalchemy import delete as sa_delete

from scripts import test_api_v2_pool_student as base
from app.database import SessionLocal
from app.models import PoolItem, Task
from app.models.video_basket import VideoBasketItem
from app.services.rate_limit import get_login_limiter

passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  ({str(detail)[:300]})")


def seed_videos(d: dict) -> dict:
    with SessionLocal() as db:
        rows = []
        for i in range(3):
            rows.append(VideoBasketItem(student_id=d["st"], coach_id=d["coach"], youtube_id=f"vp{i}abcdefg",
                                        title=f"Biyoloji ders {i + 1}", duration_sec=600, subject_id=d["bio"],
                                        group_key="g-bio", group_label="Hücre", role="anlatim", order=i + 1))
        rows.append(VideoBasketItem(student_id=d["st"], coach_id=d["coach"], youtube_id="vpsoru00000",
                                    title="TYT soru çözümü", duration_sec=900, subject_id=d["tyt"],
                                    group_key="g-tyt", group_label="Problemler", role="soru", order=4))
        rows.append(VideoBasketItem(student_id=d["st"], coach_id=d["coach"], youtube_id="vpnosubj000",
                                    title="Dersiz video", duration_sec=300, subject_id=None,
                                    group_key="g-none", group_label="Genel", role="diger", order=5))
        # gün-gün öğrencisinin videosu
        rows.append(VideoBasketItem(student_id=d["gg"], coach_id=d["coach"], youtube_id="vpgg0000000",
                                    title="GG video", duration_sec=300, subject_id=d["bio"],
                                    group_key="g-gg", group_label="Hücre", role="anlatim", order=1))
        db.add_all(rows)
        db.commit()
        return {"bio": [r.id for r in rows[:3]], "tyt": rows[3].id, "none": rows[4].id, "gg": rows[5].id}


def status_map(c, sid) -> dict[int, dict]:
    r = c.get(f"/api/v2/teacher/students/{sid}/video-basket")
    return {it["id"]: it for g in r.json()["groups"] for it in g["items"]}, r.json()


def main() -> int:
    get_login_limiter().reset()
    d = base.seed()
    v = seed_videos(d)
    sid = d["st"]
    print(f"\n=== video sepeti → havuz — {base.PFX} ===\n")
    try:
        t = base.login(f"{base.PFX}_t@test.invalid")
        s = base.login(f"{base.PFX}_s@test.invalid")
        _, body = status_map(t, sid)
        check("V1 sepet: program_mode=havuz + açık dönem", body.get("program_mode") == "havuz"
              and body.get("pool_period_open") is True, str({k: body.get(k) for k in ("program_mode", "pool_period_open")}))

        url = f"/api/v2/teacher/students/{sid}/video-basket/to-pool"
        r = t.post(url, json={"item_ids": [v["none"]]})
        check("V3 dersi seçilmemiş grup → 422 subject_required",
              r.status_code == 422 and r.json()["detail"]["code"] == "subject_required", r.text[:200])

        r = t.post(url, json={"item_ids": v["bio"] + [v["tyt"]]})
        check("V2a to-pool 200", r.status_code == 200, r.text[:300])
        pids = r.json()["data"]["pool_item_ids"] if r.status_code == 200 else []
        check("V2b 2 grup → 2 kalem, 4 video", len(pids) == 2 and r.json()["data"]["videos"] == 4, r.text[:200])
        inv = r.json().get("invalidate", []) if r.status_code == 200 else []
        check("V2c invalidate sepet + havuz + öğrenci havuzu",
              any(k.endswith(":video-basket") for k in inv) and any(k.endswith(":pool") for k in inv)
              and f"student:{sid}:pool" in inv, str(inv))
        with SessionLocal() as db:
            items = {p.id: p for p in db.query(PoolItem).filter(PoolItem.id.in_(pids))}
            bio_item = next((p for p in items.values() if p.subject_id == d["bio"]), None)
            tyt_item = next((p for p in items.values() if p.subject_id == d["tyt"]), None)
            check("V2d kalem etkinlik · 1 birim · etiket '— 3 video (30 dk)'",
                  bio_item is not None and bio_item.unit == "etkinlik" and bio_item.quantity == 1
                  and "3 video (30 dk)" in (bio_item.label or ""), bio_item and bio_item.label)
        st, _ = status_map(t, sid)
        check("V2e videolar 'pooled' + pool_item_id", all(st[i]["status"] == "pooled"
              and st[i]["pool_item_id"] == bio_item.id for i in v["bio"]), [st[i]["status"] for i in v["bio"]])

        r = t.post(url, json={"item_ids": v["bio"]})
        check("V4 ikinci kez → 409 nothing_to_pool",
              r.status_code == 409 and r.json()["detail"]["code"] == "nothing_to_pool", r.text[:150])

        # V5 öğrenci kaba alır
        r = s.post("/api/v2/student/pool/cup", json={"item_id": bio_item.id})
        check("V5a kaba al 200", r.status_code == 200, r.text[:200])
        tid = next((c["task_id"] for c in r.json()["data"]["cup"] if c["item_id"] == bio_item.id), None) \
            if r.status_code == 200 else None
        with SessionLocal() as db:
            task = db.get(Task, tid) if tid else None
            linked = db.query(VideoBasketItem).filter(VideoBasketItem.task_id == tid).count() if tid else 0
            check("V5b VIDEO görevi + 3 video bağlı + link ilk video",
                  task is not None and task.type.value == "video" and linked == 3
                  and (task.link_url or "").endswith("vp0abcdefg"), (task and task.type, linked, task and task.link_url))
            check("V5c görev başlığı sepet başlığı", task is not None and "Hücre — 3 video (30 dk)" in task.title,
                  task and task.title)
        r = s.get("/api/v2/student/day")
        found = None
        if r.status_code == 200:
            for tk in r.json().get("tasks", []):
                if tk.get("id") == tid:
                    found = tk
        check("V5d öğrenci Bugün'de görevde 3 video görür", found is not None and len(found.get("videos") or []) == 3,
              (r.status_code, found and found.get("videos")))
        st, _ = status_map(t, sid)
        check("V5e koç sepetinde 'planned' (kapta)", all(st[i]["status"] == "planned" for i in v["bio"]),
              [st[i]["status"] for i in v["bio"]])

        # V6 geri al
        r = s.post(f"/api/v2/student/pool/cup/{tid}/return")
        check("V6a kaptan geri al 200", r.status_code == 200, r.text[:200])
        st, _ = status_map(t, sid)
        check("V6b videolar yeniden 'pooled'", all(st[i]["status"] == "pooled" for i in v["bio"]),
              [st[i]["status"] for i in v["bio"]])

        # V7 tekrar al + tamamla
        r = s.post("/api/v2/student/pool/cup", json={"item_id": bio_item.id})
        tid = next(c["task_id"] for c in r.json()["data"]["cup"] if c["item_id"] == bio_item.id)
        r = s.post(f"/api/v2/student/tasks/{tid}/complete", json={})
        check("V7a görevi tamamla 200", r.status_code == 200, r.text[:200])
        with SessionLocal() as db:
            from app.services import pool_mode as pm
            it = db.get(PoolItem, bio_item.id)
            pm.sync_item_progress(db, it)
            check("V7b kalem tamam (1/1)", it.completed == 1 and it.remaining == 0, (it.completed, it.quantity))
            db.rollback()
        st, _ = status_map(t, sid)
        check("V7c videolar 'watched'", all(st[i]["status"] == "watched" for i in v["bio"]),
              [st[i]["status"] for i in v["bio"]])

        # V8 rehber TYT kalemini kaldırır
        r = t.post(f"/api/v2/teacher/students/{sid}/pool/items/{tyt_item.id}/delete", json={})
        check("V8a kalem kaldır 200", r.status_code == 200, r.text[:150])
        st, _ = status_map(t, sid)
        check("V8b video sepete döner ('waiting')", st[v["tyt"]]["status"] == "waiting", st[v["tyt"]]["status"])

        r = t.post(f"/api/v2/teacher/students/{d['gg']}/video-basket/to-pool", json={"item_ids": [v["gg"]]})
        check("V9a gün-gün öğrenci → 409 not_havuz",
              r.status_code == 409 and r.json()["detail"]["code"] == "not_havuz", r.text[:150])
        g = base.login(f"{base.PFX}_g@test.invalid")
        r = g.post(url, json={"item_ids": [v["tyt"]]})
        check("V9b başka kullanıcı erişemez (403/404)", r.status_code in (403, 404), r.text[:120])
    finally:
        with SessionLocal() as db:
            db.execute(sa_delete(VideoBasketItem).where(VideoBasketItem.student_id.in_([d["st"], d["gg"]])))
            db.commit()
        base.cleanup()
    print(f"\n{passed} passed · {len(failed)} failed")
    for f in failed:
        print("  -", f)
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())

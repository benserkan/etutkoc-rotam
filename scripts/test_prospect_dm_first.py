# -*- coding: utf-8 -*-
"""DM-oncelikli akis dogrulama: telefonsuz aday + instagram dedup."""
import sys, secrets
sys.path.insert(0, r"D:\LGS-Program")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from sqlalchemy import delete as sa_delete
from app.database import SessionLocal
from app.models import SalesProspect
from app.services import prospect_service as ps

PFX = "dmtest" + secrets.token_hex(2)
db = SessionLocal()
db.execute(sa_delete(SalesProspect).where(SalesProspect.instagram.like("dmtest%")))
db.commit()
ok, fail = 0, []
def chk(l, c, d=""):
    global ok
    if c: ok += 1; print("  [PASS]", l)
    else: fail.append(l); print("  [FAIL]", l, d)

# 1) telefonsuz + instagram'li aday
p1 = ps.create_prospect(db, actor_user_id=None, name="DM Koç Bir",
                        instagram="@" + PFX + "bir")
db.commit()
chk("telefonsuz aday olusturuldu", p1.phone is None and p1.instagram == PFX + "bir",
    f"{p1.phone}/{p1.instagram}")

# 2) URL formatindaki handle temizlenir
p2 = ps.create_prospect(db, actor_user_id=None, name="DM Koç İki",
                        instagram="https://instagram.com/" + PFX + "iki/?hl=tr")
db.commit()
chk("URL -> handle normalize", p2.instagram == PFX + "iki", str(p2.instagram))

# 3) ayni instagram ikinci kez -> dedup
try:
    ps.create_prospect(db, actor_user_id=None, name="Kopya", instagram=PFX + "bir")
    db.rollback(); chk("instagram dedup", False, "hata firlatmadi")
except ps.ProspectError as e:
    db.rollback()
    chk("instagram dedup (duplicate_instagram)", e.code == "duplicate_instagram", e.code)

# 4) kimliksiz kayit reddedilir
try:
    ps.create_prospect(db, actor_user_id=None, name="Kimliksiz")
    db.rollback(); chk("kimliksiz red", False, "hata firlatmadi")
except ps.ProspectError as e:
    db.rollback()
    chk("kimliksiz red (identity_required)", e.code == "identity_required", e.code)

# 5) CSV: yalniz instagram sutunuyla
rep = ps.import_prospects_csv(db, actor_user_id=None, csv_text=(
    "ad,instagram\nCSV Koç," + PFX + "uc\nCSV Koç 2,@" + PFX + "dort\n"), dry_run=False)
db.commit()
chk("CSV telefonsuz 2 kayit", rep["created"] == 2, str(rep))
rep2 = ps.import_prospects_csv(db, actor_user_id=None, csv_text=(
    "ad,instagram\nCSV Koç," + PFX + "uc\n"), dry_run=True)
db.rollback()
chk("CSV tekrar -> zaten var", rep2["skipped_existing"] == 1, str(rep2))

db.execute(sa_delete(SalesProspect).where(SalesProspect.instagram.like(PFX + "%")))
db.commit(); db.close()
print(f"\n=== {ok} passed, {len(fail)} failed ===")
sys.exit(1 if fail else 0)

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import math
B = "D:/LGS-Program/mobile/store"; FD = B + "/fonts"
PF = FD + "/playfair-var.ttf"; PJ = FD + "/pjs-var.ttf"
W, H = 1080, 1920
PETROL = (18, 98, 118); TERRA = (199, 104, 72); SLATE = (28, 40, 47)
CREAM = (245, 242, 234); INK = (33, 44, 49); SUB = (120, 132, 138)
CYAN = (14, 116, 137); GOLD = (241, 180, 34); WHITE = (247, 249, 250)
RED = (214, 69, 69); GREEN = (34, 150, 90); AMBER = (224, 150, 40); VIOLET = (150, 110, 210)


def F(s, w, serif=False):
    f = ImageFont.truetype(PF if serif else PJ, s); f.set_variation_by_axes([w]); return f


HEAD = F(74, 720, True)
CT, CB, X0, X1 = 470, 2020, 92, 988
IX0, IX1 = X0 + 34, X1 - 34


def base(bg_color, lines, head_fill, accent):
    bg = Image.new("RGB", (W, H), bg_color); d = ImageDraw.Draw(bg)
    for i, ln in enumerate(lines):
        w = d.textlength(ln, font=HEAD); d.text(((W - w) / 2, 86 + i * 84), ln, font=HEAD, fill=head_fill)
    y = 86 + len(lines) * 84 + 26
    pts = [(150 + t / 120 * 240, y + math.sin(t / 120 * math.pi * 2) * 15) for t in range(120)]
    for i in range(len(pts) - 1):
        d.line([pts[i], pts[i + 1]], fill=accent, width=9)
    return bg


def card(bg, bottom=CB, rad=40, fill=CREAM):
    box = [X0, CT, X1, bottom]
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([box[0], box[1] + 16, box[2], box[3] + 16], radius=rad, fill=(0, 22, 30, 95))
    bg = Image.alpha_composite(bg.convert("RGBA"), sh.filter(ImageFilter.GaussianBlur(30))).convert("RGB")
    ImageDraw.Draw(bg).rounded_rectangle(box, radius=rad, fill=fill)
    return bg


def lift(bg, box, rad=26, fill=WHITE, blur=46, dy=32, alpha=140):
    """Bir öğeyi ön plana taşı — güçlü gölge + üstte kart (Claude float deseni)."""
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([box[0] + 8, box[1] + dy, box[2] + 8, box[3] + dy], radius=rad, fill=(0, 14, 22, alpha))
    bg = Image.alpha_composite(bg.convert("RGBA"), sh.filter(ImageFilter.GaussianBlur(blur))).convert("RGB")
    ImageDraw.Draw(bg).rounded_rectangle(box, radius=rad, fill=fill)
    return bg


def spark(d, cx, cy, r, col, wd):
    for ang in range(0, 360, 60):
        a = math.radians(ang); rr = r if ang % 120 == 0 else int(r * 0.62)
        d.line([cx - math.cos(a) * rr, cy - math.sin(a) * rr, cx + math.cos(a) * rr, cy + math.sin(a) * rr], fill=col, width=wd)


def statstrip(d, y, stats):
    sw = (X1 - X0 - 68 - 40) / 3; sx = IX0
    for lbl, val, col in stats:
        d.rounded_rectangle([sx, y, sx + sw, y + 116], radius=16, fill=WHITE)
        d.text((sx + 20, y + 16), lbl, font=F(24, 600), fill=SUB)
        d.text((sx + 20, y + 48), val, font=F(48, 800), fill=col)
        sx += sw + 20


# 1) ERKEN UYARI
bg = base(TERRA, ["Geride kalmadan", "önce uyar"], INK, CYAN); bg = card(bg, 1740); d = ImageDraw.Draw(bg)
d.text((IX0 + 6, CT + 30), "Öğrencilerim", font=F(36, 700), fill=INK)
d.rounded_rectangle([X1 - 200, CT + 32, IX1, CT + 72], radius=20, fill=(238, 226, 214)); d.text((X1 - 186, CT + 38), "9 aktif", font=F(26, 700), fill=(150, 92, 60))
statstrip(d, CT + 92, [("Yolunda", "5", GREEN), ("Dikkat", "3", AMBER), ("Kritik", "1", RED)])
rows = [("Berra Demirbaş", "Bugün 6/7 görev · %65", GREEN, None),
        ("Efe Yılmazoğlu", "Dün hiç ilerleme yok", RED, "Bugün 7/8 · Hafta %63"),
        ("Yiğit Eren Aydın", "Sınava yetişmiyor", AMBER, "Hafta %42"),
        ("Elif Demirci", "Bugün hiç tik yapmadı", RED, "Bugün 0/8 · Hafta %74"),
        ("Elvin Türkmen", "2 gündür program boş", AMBER, "Hafta %19"),
        ("Ada Yılmaz", "Bugün 8/8 görev · %91", GREEN, None)]
ry = CT + 232
for name, note, bar, sub in rows:
    d.rounded_rectangle([IX0, ry, IX1, ry + 150], radius=22, fill=WHITE)
    d.rounded_rectangle([IX0, ry, IX0 + 12, ry + 150], radius=6, fill=bar)
    d.text((IX0 + 34, ry + 22), name, font=F(34, 700), fill=INK)
    d.text((IX0 + 34, ry + 66), note, font=F(28, 600), fill=(bar if bar != GREEN else SUB))
    if sub:
        d.text((IX0 + 34, ry + 102), sub, font=F(26, 500), fill=SUB)
    d.text((IX1 - 44, ry + 56), "›", font=F(48, 700), fill=(205, 205, 205))
    ry += 170
bg.save(B + "/play/_c1.png", "PNG")

# 2) AI SEANS
bg = base(PETROL, ["Yapay zekâ,", "seansa hazırlar"], WHITE, GOLD); bg = card(bg, 1690); d = ImageDraw.Draw(bg)
d.ellipse([IX0, CT + 30, IX0 + 56, CT + 86], fill=CYAN); spark(d, IX0 + 28, CT + 58, 16, WHITE, 4)
d.text((IX0 + 74, CT + 42), "Koçluk içgörüsü", font=F(32, 700), fill=INK)
d.rounded_rectangle([X1 - 150, CT + 40, IX1, CT + 76], radius=18, fill=(214, 240, 222)); d.ellipse([X1 - 138, CT + 52, X1 - 128, CT + 62], fill=GREEN); d.text((X1 - 120, CT + 44), "hazır", font=F(26, 600), fill=(28, 120, 72))
by = CT + 112
d.rounded_rectangle([IX0, by, IX1, by + 96], radius=22, fill=(224, 238, 241))
d.text((IX0 + 24, by + 22), "Yarın Elif ile seans.", font=F(32, 700), fill=CYAN); d.text((IX0 + 24, by + 56), "Neye odaklanmalıyım?", font=F(32, 700), fill=CYAN)
ay = by + 124
for i, ln in enumerate(["Elif son 2 haftada matematik netinde düştü", "(78 → 71). Üçgenler ve olasılık eksik kalıyor.", "Motivasyonu deneme trendiyle desteklenmeli."]):
    d.text((IX0 + 6, ay + i * 46), ln, font=F(31, 500), fill=INK)
hy = ay + 3 * 46 + 22
bg = lift(bg, [X0 + 18, hy, X1 - 18, hy + 286], rad=24, fill=WHITE); d = ImageDraw.Draw(bg)
d.rounded_rectangle([X0 + 18, hy, X0 + 32, hy + 286], radius=7, fill=GOLD)
d.text((IX0 + 40, hy + 22), "Seans gündemi hazır", font=F(40, 700), fill=INK)
for i, b in enumerate(["Üçgenler — 20 soru tekrar", "Olasılık — eksik konu önceliği", "Motivasyon: net trendini göster"]):
    yy = hy + 96 + i * 56; d.ellipse([IX0 + 40, yy + 12, IX0 + 54, yy + 26], fill=CYAN); d.text((IX0 + 74, yy), b, font=F(29, 600), fill=(70, 84, 90))
ry = hy + 312
d.rounded_rectangle([IX0, ry, IX1, ry + 130], radius=22, fill=(236, 244, 240))
d.text((IX0 + 30, ry + 22), "✓ Programa eklendi", font=F(32, 700), fill=(28, 120, 72)); d.text((IX0 + 30, ry + 66), "Cuma · Matematik · Üçgenler 20 test", font=F(27, 500), fill=INK)
ly = ry + 160
d.text((IX0 + 6, ly), "Diğer hazır içgörüler", font=F(28, 700), fill=SUB); ly += 48
for nm, note, col in [("Yusuf", "Türkçe — paragraf hızı düştü", AMBER), ("Zeynep", "Fen — tekrar zamanı geldi", CYAN)]:
    d.rounded_rectangle([IX0, ly, IX1, ly + 116], radius=22, fill=WHITE); d.rounded_rectangle([IX0, ly, IX0 + 12, ly + 116], radius=6, fill=col)
    d.text((IX0 + 32, ly + 22), nm, font=F(32, 700), fill=INK); d.text((IX0 + 32, ly + 64), note, font=F(28, 500), fill=SUB); ly += 134
bg.save(B + "/play/_c2.png", "PNG")

# 3) PROGRAM — AI önerisi ön planda
bg = base(SLATE, ["Programı", "dakikada kur"], WHITE, GOLD); bg = card(bg, 1770); d = ImageDraw.Draw(bg)
days = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]; dw = (X1 - X0 - 68) / 7; dx = IX0
for i, dn in enumerate(days):
    act = i == 4
    d.rounded_rectangle([dx, CT + 26, dx + dw - 10, CT + 90], radius=16, fill=(CYAN if act else (236, 233, 224)))
    d.text((dx + dw / 2 - 22, CT + 44), dn, font=F(24, 700), fill=(WHITE if act else SUB)); dx += dw
d.text((IX0 + 6, CT + 116), "Cuma · Haftalık plan", font=F(34, 700), fill=INK)
# --- ÖN PLANA TAŞINAN AI ÖNERİSİ (lifted, geniş, güçlü gölge) ---
fb = [X0 + 18, CT + 172, X1 - 18, CT + 172 + 214]
bg = lift(bg, fb, rad=28, fill=(224, 240, 244)); d = ImageDraw.Draw(bg)
d.rounded_rectangle([fb[0], fb[1], fb[0] + 12, fb[3]], radius=6, fill=CYAN)
d.ellipse([fb[0] + 32, fb[1] + 28, fb[0] + 32 + 58, fb[1] + 28 + 58], fill=CYAN); spark(d, fb[0] + 61, fb[1] + 57, 17, WHITE, 4)
d.text((fb[0] + 108, fb[1] + 30), "Yapay zekâ önerisi", font=F(34, 700), fill=CYAN)
d.text((fb[0] + 108, fb[1] + 74), "bu haftaya hazırladı", font=F(27, 500), fill=SUB)
d.text((fb[0] + 32, fb[1] + 118), "Üçgenler eksik kalıyor — programa", font=F(31, 600), fill=INK)
d.text((fb[0] + 32, fb[1] + 156), "20 test ekledim · ✓ uygulandı", font=F(31, 600), fill=INK)
# --- görev listesi (AI eklediği işaretli) ---
tasks = [("Matematik", "Üçgenler · 20 test", CYAN, True), ("Türkçe", "Paragraf · 15 test", GOLD, False),
         ("Fen Bilimleri", "Basınç · 10 test", GREEN, False), ("TYT Deneme", "120 soru", (210, 120, 90), False)]
ry = fb[3] + 28
for t, s, tn, ai in tasks:
    d.rounded_rectangle([IX0, ry, IX1, ry + 118], radius=20, fill=WHITE); d.rounded_rectangle([IX0, ry, IX0 + 12, ry + 118], radius=6, fill=tn)
    d.text((IX0 + 32, ry + 18), t, font=F(33, 700), fill=INK); d.text((IX0 + 32, ry + 60), s, font=F(27, 500), fill=SUB)
    if ai:
        d.rounded_rectangle([X1 - 156, ry + 38, IX1 - 6, ry + 78], radius=20, fill=(224, 238, 241)); spark(d, X1 - 138, ry + 58, 9, CYAN, 3); d.text((X1 - 120, ry + 44), "AI ekledi", font=F(24, 700), fill=CYAN)
    else:
        d.ellipse([IX1 - 72, ry + 42, IX1 - 40, ry + 74], outline=tn, width=4)
    ry += 134
d.rounded_rectangle([IX0, ry, IX1, ry + 124], radius=22, fill=(58, 72, 80))
d.text((IX0 + 30, ry + 20), "Kaynak durumu", font=F(30, 700), fill=WHITE); d.text((IX0 + 30, ry + 62), "Matematik · 240/400 test kaldı", font=F(27, 500), fill=(200, 214, 220))
ry += 154
d.text((IX0 + 6, ry), "Bu hafta planlanan", font=F(28, 700), fill=SUB)
statstrip(d, ry + 44, [("Test", "540", CYAN), ("Deneme", "4", GOLD), ("Etkinlik", "6", GREEN)])
bg.save(B + "/play/_c3.png", "PNG")

# 4) DENEME NETLERİ
bg = base(TERRA, ["Deneme netleri,", "otomatik trend"], INK, CYAN); bg = card(bg, 1770); d = ImageDraw.Draw(bg)
d.text((IX0 + 6, CT + 30), "Net Gelişimi · TYT", font=F(34, 700), fill=INK)
d.text((IX0 + 6, CT + 84), "92", font=F(104, 800, True), fill=CYAN); d.text((IX0 + 160, CT + 144), "net", font=F(34, 600), fill=SUB)
d.rounded_rectangle([IX0 + 280, CT + 108, IX0 + 440, CT + 160], radius=26, fill=(214, 240, 222)); d.text((IX0 + 300, CT + 118), "▲ +11", font=F(32, 700), fill=(28, 120, 72))
base_y = CT + 500; heights = [0.42, 0.5, 0.4, 0.6, 0.74, 0.92]; bw = (IX1 - IX0) / len(heights)
for i, h in enumerate(heights):
    bxx = IX0 + i * bw + 16; top = base_y - int(h * 240); col = CYAN if i == len(heights) - 1 else (212, 168, 146)
    d.rounded_rectangle([bxx, top, bxx + bw - 32, base_y], radius=12, fill=col)
d.line([IX0, base_y + 2, IX1, base_y + 2], fill=(220, 208, 198), width=3)
for i, lbl in enumerate(["D1", "D2", "D3", "D4", "D5", "D6"]):
    d.text((IX0 + i * bw + bw / 2 - 18, base_y + 12), lbl, font=F(24, 600), fill=SUB)
d.text((IX0 + 6, base_y + 76), "Ders bazlı net", font=F(32, 700), fill=INK)
subs = [("Türkçe", "34 / 40", 0.85), ("Matematik", "28 / 40", 0.70), ("Fen", "18 / 20", 0.90), ("Sosyal", "12 / 20", 0.60)]
sy = base_y + 128
for name, val, p in subs:
    d.text((IX0 + 6, sy), name, font=F(30, 600), fill=INK); d.text((IX1 - 130, sy), val, font=F(30, 700), fill=CYAN)
    d.rounded_rectangle([IX0 + 6, sy + 42, IX1 - 6, sy + 58], radius=8, fill=(228, 216, 206))
    d.rounded_rectangle([IX0 + 6, sy + 42, IX0 + 6 + int((IX1 - 12) * p), sy + 58], radius=8, fill=CYAN); sy += 86
d.text((IX0 + 6, sy + 6), "Son denemeler", font=F(32, 700), fill=INK)
ry4 = sy + 56
for date, name, net in [("31 May", "TYT Genel Deneme", "92"), ("24 May", "TYT Genel Deneme", "81"), ("17 May", "AYT Matematik", "68")]:
    d.rounded_rectangle([IX0, ry4, IX1, ry4 + 80], radius=16, fill=WHITE)
    d.text((IX0 + 24, ry4 + 26), date, font=F(26, 600), fill=SUB)
    d.text((IX0 + 168, ry4 + 22), name, font=F(30, 600), fill=INK)
    nt = net + " net"; nw = d.textlength(nt, font=F(30, 700))
    d.text((IX1 - nw - 24, ry4 + 22), nt, font=F(30, 700), fill=CYAN)
    ry4 += 96
bg.save(B + "/play/_c4.png", "PNG")

# 5) VELİ ŞEFFAFLIĞI
bg = base(PETROL, ["Veli", "her şeyi görür"], WHITE, GOLD); bg = card(bg, 1620); d = ImageDraw.Draw(bg)
d.text((IX0 + 6, CT + 30), "Haftalık rapor", font=F(36, 700), fill=INK); d.text((IX0 + 6, CT + 80), "25 May – 31 May", font=F(28, 500), fill=SUB)
cxr, cyr, rr = X1 - 134, CT + 118, 78
d.arc([cxr - rr, cyr - rr, cxr + rr, cyr + rr], -90, 270, fill=(226, 222, 212), width=22)
d.arc([cxr - rr, cyr - rr, cxr + rr, cyr + rr], -90, -90 + int(360 * 0.89), fill=GREEN, width=22)
d.text((cxr - 50, cyr - 28), "%89", font=F(48, 800), fill=INK)
d.text((IX0 + 6, CT + 200), "Geçen haftaya göre", font=F(30, 500), fill=INK); d.text((IX0 + 330, CT + 200), "▲ +3 puan", font=F(30, 700), fill=GREEN)
subs = [("Matematik", 0.85), ("Türkçe", 0.92), ("Fen Bilimleri", 0.78), ("Sosyal", 0.95)]; sy = CT + 268
for name, p in subs:
    d.text((IX0 + 6, sy), name, font=F(30, 600), fill=INK)
    d.rounded_rectangle([IX0 + 300, sy + 6, IX1 - 6, sy + 30], radius=12, fill=(228, 224, 214))
    d.rounded_rectangle([IX0 + 300, sy + 6, IX0 + 300 + int((IX1 - 6 - (IX0 + 300)) * p), sy + 30], radius=12, fill=CYAN); sy += 70
ey = sy + 14
bg = lift(bg, [X0 + 18, ey, X1 - 18, ey + 196], rad=24, fill=WHITE); d = ImageDraw.Draw(bg)
d.text((IX0 + 30, ey + 22), "Son deneme", font=F(28, 600), fill=SUB)
d.rounded_rectangle([X1 - 160, ey + 20, IX1 - 6, ey + 58], radius=18, fill=(224, 238, 241)); d.text((X1 - 146, ey + 26), "LGS", font=F(26, 700), fill=CYAN)
d.text((IX0 + 30, ey + 60), "86", font=F(60, 800, True), fill=CYAN); d.text((IX0 + 150, ey + 94), "net", font=F(30, 600), fill=SUB)
d.text((IX0 + 30, ey + 144), "Doğru 68 · Yanlış 12 · Boş 10", font=F(28, 500), fill=INK)
ny = ey + 220
d.rounded_rectangle([IX0, ny, IX1, ny + 130], radius=22, fill=(236, 244, 240)); spark(d, IX0 + 44, ny + 64, 16, GREEN, 4)
d.text((IX0 + 84, ny + 26), "Bildirim gönderildi", font=F(30, 700), fill=(28, 120, 72)); d.text((IX0 + 84, ny + 68), "Rapor + net · WhatsApp & e-posta", font=F(27, 500), fill=INK)
wy = ny + 158
d.text((IX0 + 6, wy), "Bu hafta günlük tamamlama", font=F(28, 700), fill=SUB)
dvals = [("Pzt", 1.0), ("Sal", 1.0), ("Çar", 0.6), ("Per", 1.0), ("Cum", 0.4), ("Cmt", 0.0), ("Paz", 0.0)]
dwid = (IX1 - IX0) / 7
for i, (dn, v) in enumerate(dvals):
    cxc = IX0 + dwid * i + dwid / 2
    col = GREEN if v >= 0.9 else (AMBER if v > 0 else (214, 210, 200))
    d.ellipse([cxc - 24, wy + 48, cxc + 24, wy + 96], fill=col)
    d.text((cxc - d.textlength(dn, font=F(22, 600)) / 2, wy + 104), dn, font=F(22, 600), fill=SUB)
bg.save(B + "/play/_c5.png", "PNG")

# 6) KURUM RİSKİ
bg = base(SLATE, ["Riski gör,", "müdahale et"], WHITE, GOLD); bg = card(bg, 1700); d = ImageDraw.Draw(bg)
d.text((IX0 + 6, CT + 30), "Risk Paneli · Kurum", font=F(36, 700), fill=INK)
statstrip(d, CT + 90, [("Kritik", "1", RED), ("Yüksek", "2", AMBER), ("İzlemede", "6", CYAN)])
risks = [("Mert Kaya", "Ayşe Demir · 12. sınıf", "5 gündür giriş yok", "Kritik · 78", RED),
         ("Elvin Türkmen", "Serkan Aydın · 11. sınıf", "Düşük tamamlama · %81 düşüş", "Dikkat · 45", AMBER),
         ("Selin Kaya", "Mehmet Yıldız · 11. sınıf", "Haftalık tamamlama %38", "Dikkat · 52", AMBER)]
ry = CT + 232
for idx, (name, coach, note, badge, col) in enumerate(risks):
    if idx == 0:  # en kritik satır ön plana
        bg = lift(bg, [X0 + 18, ry, X1 - 18, ry + 250], rad=24, fill=WHITE); d = ImageDraw.Draw(bg)
        lx0, lx1 = X0 + 18, X1 - 18
    else:
        d.rounded_rectangle([IX0, ry, IX1, ry + 250], radius=24, fill=WHITE); lx0, lx1 = IX0, IX1
    d.rounded_rectangle([lx0, ry, lx0 + 14, ry + 250], radius=7, fill=col)
    d.text((lx0 + 38, ry + 24), name, font=F(36, 700), fill=INK)
    bw2 = d.textlength(badge, font=F(26, 700))
    d.rounded_rectangle([lx1 - bw2 - 64, ry + 26, lx1 - 24, ry + 66], radius=20, fill=(250, 232, 210) if col == AMBER else (250, 222, 222))
    d.text((lx1 - bw2 - 44, ry + 32), badge, font=F(26, 700), fill=(150, 96, 20) if col == AMBER else (170, 50, 50))
    d.text((lx0 + 38, ry + 76), coach, font=F(28, 500), fill=SUB)
    d.text((lx0 + 38, ry + 116), note, font=F(28, 600), fill=col)
    d.rounded_rectangle([lx0 + 38, ry + 162, lx1 - 38, ry + 218], radius=16, fill=CYAN)
    t = "Sorumlu koça ilet"; tw = d.textlength(t, font=F(30, 700)); d.text(((W - tw) / 2, ry + 174), t, font=F(30, 700), fill=WHITE)
    ry += 274
d.rounded_rectangle([IX0, ry, IX1, ry + 130], radius=22, fill=(58, 72, 80))
d.text((IX0 + 30, ry + 22), "Program uyumu · kurum", font=F(30, 700), fill=WHITE); d.text((IX0 + 30, ry + 66), "Bu hafta %72 · geçen hafta %68 ▲", font=F(28, 500), fill=(200, 214, 220))
bg.save(B + "/play/_c6.png", "PNG")
print("6 dolu slayt: _c1..._c6")

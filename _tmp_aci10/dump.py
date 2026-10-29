import sys, fitz, re
doc = fitz.open(sys.argv[1])
out = open(sys.argv[2], "w", encoding="utf-8")
for i in range(4, 252):
    p = doc[i]
    txt = p.get_text("text")
    txt = re.sub(r"[-]", "?", txt)
    txt = re.sub(r"\s+", " ", txt)
    out.write(f"=== PAGE {i+1} ===\n{txt[:900]}\n")
out.close()

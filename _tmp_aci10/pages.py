import sys, fitz, re
doc = fitz.open(sys.argv[1])
out=open("p.txt","w",encoding="utf-8")
for a in sys.argv[2:]:
    i = int(a) - 1
    txt = doc[i].get_text("text")
    txt = re.sub(r"[-]", "?", txt)
    txt = re.sub(r"\s+", " ", txt)
    out.write(f"=== PAGE {i+1} ===\n{txt[:3500]}\n")

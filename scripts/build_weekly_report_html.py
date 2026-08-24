# -*- coding: utf-8 -*-
"""Haftalık koç raporu HTML'i — dump JSON'undan (tek kaynak: app/services/weekly_coach_report).

    python -m scripts.build_weekly_report_html <dump.json> <out.html>

Kural motoru gündemi otomatik üretilir; format sistemdeki "Haftalık rapor" butonuyla birebir.
"""
from __future__ import annotations
import argparse, json

from app.services import weekly_coach_report as w


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dump"); ap.add_argument("out")
    a = ap.parse_args()
    d = json.load(open(a.dump, encoding="utf-8"))
    agenda = w.build_agenda(d)
    html_out = w.render_html(d, agenda)
    open(a.out, "w", encoding="utf-8").write(html_out)
    print("written", a.out, len(html_out), "agenda items:", len(agenda))


if __name__ == "__main__":
    main()

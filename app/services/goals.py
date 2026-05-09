"""Stage 11 — Goal tree (hedef ağacı) servis katmanı.

Üç ana akış:
1. **Tree builder** — bir öğrencinin tüm hedeflerini hierarchical tree olarak
   yeniden yapılandır (parent_id'lere göre); UI'da render için ready dict.
2. **Progress aggregation** — leaf hedeflerin yüzde ilerlemelerini ağırlıklı
   ortalamayla yukarı doğru taşır; tree node'una `aggregated_pct` ekler.
3. **Achievement detection** — current_value >= target_value veya manuel
   olarak ACHIEVED'a alındığında achieved_at set + audit + (ileride) veli
   bildirimi tetiklenir.

Tasarım kararları:
- Cache yok — küçük tree'ler (öğrenci başına 20-50 düğüm) için on-demand
  hesap yeterli. Performans gerekirse `aggregated_pct` denormalize edilebilir.
- Auto-generation Faz 3'te eklenecek; bu modül CRUD + tree + aggregate ile sınırlı.
- Soft-delete yok — abandoned status manage eder.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy.orm import Session, joinedload

from app.models import (
    GoalKind,
    GoalStatus,
    StudentGoal,
    User,
    UserRole,
)


logger = logging.getLogger(__name__)


# ============================ Tree builder ============================


@dataclass
class GoalNode:
    """UI'ya hazır tree node — hesaplanmış aggregated_pct dahil."""
    goal: StudentGoal
    children: list["GoalNode"] = field(default_factory=list)
    aggregated_pct: int | None = None       # 0..100 — alt hedeflerden derive
    achieved_count: int = 0                 # bu node + alt hedeflerde achieved sayım
    total_count: int = 0                    # bu node + alt hedeflerde toplam (active+achieved)


def list_student_goals(
    db: Session, *, student_id: int,
    include_abandoned: bool = False,
) -> list[StudentGoal]:
    """Bir öğrencinin tüm hedef düğümleri (tek SQL — flat list)."""
    q = db.query(StudentGoal).filter(StudentGoal.student_id == student_id)
    if not include_abandoned:
        q = q.filter(StudentGoal.status != GoalStatus.ABANDONED)
    return q.order_by(StudentGoal.created_at.asc()).all()


def build_tree(
    db: Session, *, student_id: int, include_abandoned: bool = False,
) -> list[GoalNode]:
    """Öğrencinin hedeflerini ağaç olarak döndür (kök hedefler liste).

    Tree dolduktan sonra her node için `aggregated_pct` + count'lar set edilir.
    """
    flat = list_student_goals(
        db, student_id=student_id, include_abandoned=include_abandoned,
    )
    nodes_by_id: dict[int, GoalNode] = {
        g.id: GoalNode(goal=g) for g in flat
    }
    roots: list[GoalNode] = []
    for g in flat:
        node = nodes_by_id[g.id]
        if g.parent_id and g.parent_id in nodes_by_id:
            nodes_by_id[g.parent_id].children.append(node)
        else:
            roots.append(node)

    # İlerlemeyi yukarı doğru hesapla (post-order traversal)
    for root in roots:
        _compute_aggregate(root)
    return roots


def _compute_aggregate(node: GoalNode) -> None:
    """Yaprak: progress_pct → aggregated_pct.
    Üst düğüm: çocukların aggregated_pct ağırlıklı ortalaması.
    """
    g = node.goal
    if not node.children:
        # Yaprak
        node.aggregated_pct = g.progress_pct
        node.total_count = 1
        node.achieved_count = 1 if g.status == GoalStatus.ACHIEVED else 0
        return

    # Alt düğümleri rekürsif hesapla
    total_w = 0
    weighted_sum = 0
    has_any_pct = False
    achieved = 0
    total = 0
    for ch in node.children:
        _compute_aggregate(ch)
        total += ch.total_count
        achieved += ch.achieved_count
        if ch.aggregated_pct is not None:
            has_any_pct = True
            # Eşit ağırlık (her alt eşit önemli)
            weighted_sum += ch.aggregated_pct
            total_w += 1

    # Bu düğümün kendisi de tree count'unda yer alır
    total += 1
    if g.status == GoalStatus.ACHIEVED:
        achieved += 1
    node.total_count = total
    node.achieved_count = achieved

    if has_any_pct and total_w > 0:
        node.aggregated_pct = round(weighted_sum / total_w)
    else:
        # Sayısal hedef yoksa ama children içinde achieved/total varsa
        # sayım üzerinden yüzde ver
        if total > 0:
            node.aggregated_pct = round(100 * achieved / total)


def tree_to_dict(nodes: list[GoalNode]) -> list[dict[str, Any]]:
    """Tree'yi JSON-serializable dict listesine çevir — UI/test için."""
    out = []
    for n in nodes:
        out.append({
            "id": n.goal.id,
            "kind": n.goal.kind.value,
            "status": n.goal.status.value,
            "title": n.goal.title,
            "target_value": n.goal.target_value,
            "current_value": n.goal.current_value,
            "unit": n.goal.unit,
            "target_date": n.goal.target_date.isoformat() if n.goal.target_date else None,
            "aggregated_pct": n.aggregated_pct,
            "achieved_count": n.achieved_count,
            "total_count": n.total_count,
            "is_auto_generated": n.goal.is_auto_generated,
            "children": tree_to_dict(n.children),
        })
    return out


# ============================ CRUD ============================


def create_goal(
    db: Session, *, student: User, kind: GoalKind, title: str,
    parent_id: int | None = None,
    description: str | None = None,
    target_value: float | None = None,
    current_value: float | None = None,
    unit: str | None = None,
    target_date: date | None = None,
    is_auto_generated: bool = False,
    created_by_user_id: int | None = None,
    autocommit: bool = True,
) -> StudentGoal:
    """Yeni hedef oluştur.

    Validation: parent_id verilmişse aynı student_id'ye ait olmalı (cross-student
    hedef ağacı yok).
    """
    if student.role != UserRole.STUDENT:
        raise ValueError(
            f"create_goal: yalnız öğrencilere hedef eklenebilir, role={student.role}"
        )
    if parent_id is not None:
        parent = db.get(StudentGoal, parent_id)
        if parent is None:
            raise ValueError(f"create_goal: parent goal #{parent_id} yok")
        if parent.student_id != student.id:
            raise PermissionError(
                "create_goal: parent goal başka öğrenciye ait"
            )

    g = StudentGoal(
        student_id=student.id,
        parent_id=parent_id,
        kind=kind,
        status=GoalStatus.ACTIVE,
        title=title.strip(),
        description=(description or "").strip() or None,
        target_value=target_value,
        current_value=current_value,
        unit=unit,
        target_date=target_date,
        is_auto_generated=is_auto_generated,
        created_by_user_id=created_by_user_id,
    )
    db.add(g)
    db.flush()
    if autocommit:
        db.commit()
    logger.info(
        "create_goal: id=%s student=%s kind=%s parent=%s",
        g.id, student.id, kind.value, parent_id,
    )
    return g


def update_goal(
    db: Session, *, goal: StudentGoal,
    title: str | None = None,
    description: str | None = None,
    target_value: float | None = None,
    current_value: float | None = None,
    unit: str | None = None,
    target_date: date | None = None,
    autocommit: bool = True,
) -> StudentGoal:
    """Hedef alanlarını güncelle. None geçilen alanlar değişmez (current_value
    hariç — onu sıfırlamak için 0.0 verilmeli).
    """
    if title is not None:
        goal.title = title.strip()
    if description is not None:
        goal.description = description.strip() or None
    if target_value is not None:
        goal.target_value = target_value
    if current_value is not None:
        goal.current_value = current_value
    if unit is not None:
        goal.unit = unit
    if target_date is not None:
        goal.target_date = target_date

    # Otomatik achievement detection — current >= target ise ACHIEVED
    if (
        goal.status == GoalStatus.ACTIVE
        and goal.target_value is not None and goal.target_value > 0
        and goal.current_value is not None
        and goal.current_value >= goal.target_value
    ):
        mark_achieved(db, goal=goal, autocommit=False)

    db.flush()
    if autocommit:
        db.commit()
    return goal


def mark_achieved(
    db: Session, *, goal: StudentGoal,
    autocommit: bool = True,
) -> StudentGoal:
    """Hedefi ACHIEVED işaretle + achieved_at set."""
    if goal.status == GoalStatus.ACHIEVED:
        return goal
    goal.status = GoalStatus.ACHIEVED
    goal.achieved_at = datetime.now(timezone.utc)
    db.flush()
    if autocommit:
        db.commit()
    logger.info("mark_achieved: goal_id=%s student=%s", goal.id, goal.student_id)
    return goal


def mark_abandoned(
    db: Session, *, goal: StudentGoal,
    autocommit: bool = True,
) -> StudentGoal:
    """Hedefi ABANDONED işaretle (öğrenci/öğretmen vazgeçti)."""
    if goal.status == GoalStatus.ABANDONED:
        return goal
    goal.status = GoalStatus.ABANDONED
    goal.abandoned_at = datetime.now(timezone.utc)
    db.flush()
    if autocommit:
        db.commit()
    return goal


def delete_goal(
    db: Session, *, goal: StudentGoal, autocommit: bool = True,
) -> None:
    """Hedefi tamamen sil (children CASCADE silinir).

    Genelde abandoned status tercih edilir; gerçek silme ancak yanlış
    oluşturulmuş hedef için.
    """
    db.delete(goal)
    if autocommit:
        db.commit()


# ============================ Aggregations ============================


def student_goal_summary(db: Session, *, student_id: int) -> dict:
    """Bir öğrencinin hedef özeti — UI dashboard kartı için.

    {
        'total': N, 'active': N, 'achieved': N, 'abandoned': N,
        'overall_pct': 0..100 | None,    # tüm aktif hedeflerin agg ortalaması
        'next_target_date': date | None, # en yakın target_date
    }
    """
    goals = list_student_goals(db, student_id=student_id, include_abandoned=True)
    total = len(goals)
    active = sum(1 for g in goals if g.status == GoalStatus.ACTIVE)
    achieved = sum(1 for g in goals if g.status == GoalStatus.ACHIEVED)
    abandoned = sum(1 for g in goals if g.status == GoalStatus.ABANDONED)

    roots = build_tree(db, student_id=student_id)
    overall_pct = None
    if roots:
        pcts = [r.aggregated_pct for r in roots if r.aggregated_pct is not None]
        if pcts:
            overall_pct = round(sum(pcts) / len(pcts))

    # En yakın target_date — aktif hedefler arasında
    upcoming = [
        g.target_date for g in goals
        if g.status == GoalStatus.ACTIVE and g.target_date is not None
    ]
    next_target_date = min(upcoming) if upcoming else None

    return {
        "total": total,
        "active": active,
        "achieved": achieved,
        "abandoned": abandoned,
        "overall_pct": overall_pct,
        "next_target_date": next_target_date.isoformat() if next_target_date else None,
    }


def institution_goal_summary(
    db: Session, *, institution_id: int,
) -> dict:
    """Kurum geneli hedef özeti — institution_admin paneli için.

    {
        'students_with_goals': N, 'students_without_goals': N,
        'total_goals': N, 'achieved_goals': N, 'active_goals': N,
        'avg_overall_pct': 0..100 | None,
    }
    """
    students = (
        db.query(User)
        .filter(
            User.institution_id == institution_id,
            User.role == UserRole.STUDENT,
            User.is_active.is_(True),
        )
        .all()
    )
    student_ids = [s.id for s in students]
    if not student_ids:
        return {
            "students_with_goals": 0, "students_without_goals": 0,
            "total_goals": 0, "achieved_goals": 0, "active_goals": 0,
            "avg_overall_pct": None,
        }

    all_goals = (
        db.query(StudentGoal)
        .filter(StudentGoal.student_id.in_(student_ids))
        .all()
    )
    students_with_goals = len(set(g.student_id for g in all_goals))
    achieved = sum(1 for g in all_goals if g.status == GoalStatus.ACHIEVED)
    active = sum(1 for g in all_goals if g.status == GoalStatus.ACTIVE)

    # Ortalama overall_pct — öğrenci başına hesap
    pcts = []
    for sid in student_ids:
        s = student_goal_summary(db, student_id=sid)
        if s["overall_pct"] is not None:
            pcts.append(s["overall_pct"])
    avg = round(sum(pcts) / len(pcts)) if pcts else None

    return {
        "students_with_goals": students_with_goals,
        "students_without_goals": len(student_ids) - students_with_goals,
        "total_goals": len(all_goals),
        "achieved_goals": achieved,
        "active_goals": active,
        "avg_overall_pct": avg,
    }

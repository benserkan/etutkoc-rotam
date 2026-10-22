"""Haftalık görev havuzu — rehber editörü şemaları (2026-10-12, Adım 2)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class PoolItemOut(BaseModel):
    id: int
    subject_id: int | None
    subject_name: str
    topic_id: int | None = None
    topic_name: str | None = None
    book_id: int | None = None
    book_name: str | None = None
    section_id: int | None = None
    section_label: str | None = None
    label: str | None = None
    quantity: int
    unit: str
    completed: int
    remaining: int
    day_hint: str | None = None
    source: str                       # rehber | ogrenci | deneme | devir | sablon
    teacher_homework: bool = False
    approval: str                     # yok | bekliyor | onaylandi | reddedildi
    carry_count: int = 0
    cup_attempts: int = 0
    counts: bool = True               # yüzdeye/tempoya giriyor mu (K38)
    created_by_name: str | None = None
    book_completed: int | None = None  # kitaplı kalem: bölümde çözülen (kitap sayacı) — ilerleme takibi
    book_total: int | None = None      # kitaplı kalem: bölümün test sayısı
    created_at: str | None = None
    # Deneme kalemi (D1b): quantity = deneme adedi; question_count = deneme başına soru.
    exam_kind: str | None = None
    exam_section: str | None = None
    question_count: int | None = None
    page_from: int | None = None
    page_to: int | None = None


class PoolSummaryOut(BaseModel):
    total_units: int
    done_units: int
    pct: int
    items_total: int
    items_done: int
    pending_student_items: int
    days_left: int
    per_day_needed: float
    expected_next_on: str | None = None


class PoolPeriodOut(BaseModel):
    id: int
    opened_on: str
    expected_next_on: str | None = None
    closed_on: str | None = None
    status: str
    status_label: str
    days_open: int
    note: str | None = None
    summary: PoolSummaryOut
    items: list[PoolItemOut] = []


class PoolPeriodBrief(BaseModel):
    id: int
    opened_on: str
    closed_on: str | None = None
    status: str
    status_label: str
    total_units: int
    done_units: int
    pct: int
    parent_summary_sent_at: str | None = None  # K53


class PoolSubjectOut(BaseModel):
    id: int
    name: str
    is_ayt: bool = False
    item_count: int = 0                # bu havuzdaki kalem sayısı (K24 kontrol şeridi için)
    group: str = "okul"                # okul (müfredat dersi) | sinav (TYT/AYT) — 2026-10-13
    book_count: int = 0                # öğrencinin bu dersteki kitabı (deneme hariç) — çipte "2 kitap"
    deneme_count: int = 0              # deneme kitabı


class PoolClassGroupOut(BaseModel):
    id: int
    name: str
    positions: dict[str, dict] = {}    # subject_id → {topic_id, topic_name, updated_on}
    lesson_days: dict[str, list[int]] = {}  # "0".."6" → subject_id listesi


class PoolVolumeHint(BaseModel):
    avg_done_last3: int | None = None  # son 3 kapanmış dönemde ortalama tamamlanan birim
    current_total: int = 0


class PoolStudentOut(BaseModel):
    id: int
    full_name: str
    program_mode: str
    grade_level: int | None = None
    is_graduate: bool = False
    track: str | None = None
    track_label: str | None = None
    needs_track: bool = False
    class_group: str | None = None


class PoolFlagEvidence(BaseModel):
    label: str
    value: str


class PoolFlagOut(BaseModel):
    """Havuz erken uyarı sinyali (pool_flags, K40–K51) — level red|amber|green, layer P/K/T/D/E/A/Z/G."""
    code: str
    level: str
    layer: str
    title: str
    detail: str
    evidence: list[PoolFlagEvidence] = []
    coach_only: bool = False


class PoolFlagsOut(BaseModel):
    headline: str = ""
    level: str = "green"
    primary: list[PoolFlagOut] = []      # K48: en çok 1 ana kart
    secondary: list[PoolFlagOut] = []    # katlanan ek sinyaller + bilgi
    good: list[PoolFlagOut] = []
    paper_student: bool = False          # K40


class PoolBundleResponse(BaseModel):
    student: PoolStudentOut
    period: PoolPeriodOut | None = None
    periods: list[PoolPeriodBrief] = []
    subjects: list[PoolSubjectOut] = []
    ayt_locked: bool = False           # K25: alan boş → AYT dersleri kapalı
    locked_ayt_names: list[str] = []
    curriculum_label: str | None = None  # "Maarif müfredatı · 11. sınıf" (okul grubu başlığı)
    # Maarif 11+: eski TYT/AYT yerine "TYT (Maarif)" — bu okul dersleri, konular ≤ max_grade (9-10. sınıf)
    tyt_maarif_subject_ids: list[int] = []
    tyt_maarif_max_grade: int = 10
    missing_subjects: list[str] = []   # K24: bu havuzda kalemi olmayan dersler
    class_group: PoolClassGroupOut | None = None
    volume: PoolVolumeHint = PoolVolumeHint()
    flags: PoolFlagsOut = PoolFlagsOut()  # Adım 4 erken uyarı
    carry_candidates: list[PoolCarryCandidate] = []   # Adım 6: dönem açarken devir adayları
    carry_source_period_id: int | None = None
    on_break: PoolBreakOut | None = None               # K61
    periods_total: int = 0                             # K60: toplam dönem (geçmiş sayfalı)
    units: list[str] = []
    today: str


class PoolTopicSource(BaseModel):
    book_id: int
    book_name: str
    section_id: int
    section_label: str
    total: int
    remaining: int
    completed: int = 0
    recommended: bool = False


class PoolTopicOut(BaseModel):
    topic_id: int
    name: str
    unit_name: str | None = None
    status: str                       # kapali|devam|planlandi|baslanmadi|kaynak_yok
    remaining: int = 0
    tests_solved: int = 0
    accuracy_pct: int | None = None
    last_assigned_on: str | None = None   # K27 "SON": en son havuza/göreve girdiği gün
    is_last: bool = False
    is_class_position: bool = False       # K9: şubenin şu an işlediği konu
    grade_level: int | None = None
    sources: list[PoolTopicSource] = []


class PoolTopicsResponse(BaseModel):
    subject_id: int
    subject_name: str
    topics: list[PoolTopicOut] = []


# ---- gövdeler

class ProgramModeBody(BaseModel):
    mode: str = Field(pattern="^(gun_gun|havuz)$")


class ModeSwitchTask(BaseModel):
    task_id: int
    date: str
    title: str
    planned: int
    completed: int
    is_draft: bool
    is_cup: bool


class ModeSwitchPreviewResponse(BaseModel):
    """Program modu geçişinin etkisi (2026-10-15) — hiçbir şey yazmaz."""
    from_mode: str
    to_mode: str
    effective_on: str
    allowed: bool
    blocker: str | None = None
    blocker_message: str | None = None
    delete_tasks: list[ModeSwitchTask] = []
    keep_partial: list[ModeSwitchTask] = []
    release_tests: int = 0
    dead_reserve_tests: int = 0
    pool_leftover_items: int = 0
    pool_leftover_units: int = 0
    notes: list[str] = []


class ModeSwitchBody(BaseModel):
    to_mode: str = Field(pattern="^(gun_gun|havuz)$")
    effective_on: str | None = None          # boş → bugün
    open_first_period: bool = True           # yalnız havuza geçişte: ilk dönemi aynı gün aç
    expected_next_on: str | None = None
    note: str | None = Field(default=None, max_length=1000)


class ModeChangeOut(BaseModel):
    id: int
    from_mode: str
    to_mode: str
    from_label: str
    to_label: str
    effective_on: str
    trigger: str
    trigger_label: str
    changed_by_name: str | None = None
    note: str | None = None
    summary: dict = {}
    created_at: str | None = None


class ModeHistoryResponse(BaseModel):
    current_mode: str
    items: list[ModeChangeOut] = []


class PoolCarryCandidate(BaseModel):
    """Adım 6 devir ekranı: son kapanmış dönemin kalanı olan kalemi (K22/K58)."""
    item_id: int
    subject_name: str
    title: str
    unit: str
    remaining: int
    quantity: int
    carry_count: int
    third_carry: bool          # K58: bu devirle 3. kez → kaçınılan sinyali; miktar yeniden yazılır
    teacher_homework: bool = False


class PoolBreakOut(BaseModel):
    """K61: ara (tatil) durumu — açık dönem yok, son dönem 'ara' ile kapandı."""
    period_id: int
    since: str
    note: str | None = None


class PeriodOpenBody(BaseModel):
    opened_on: str
    expected_next_on: str | None = None
    note: str | None = Field(default=None, max_length=1000)
    carry: list["CarryIn"] = []   # Adım 6: son kapanmış dönemden kalem kalem devir


class PeriodCloseBody(BaseModel):
    closed_on: str
    status: str = Field(default="kapandi", pattern="^(kapandi|ara|gorusmesiz)$")
    note: str | None = Field(default=None, max_length=500)  # seanssız kapanışın gerekçesi → dönem notu


class PoolItemBody(BaseModel):
    subject_id: int
    topic_id: int | None = None
    book_id: int | None = None
    section_id: int | None = None
    label: str | None = Field(default=None, max_length=255)
    quantity: int | None = Field(default=None, ge=1, le=500)
    unit: str = Field(pattern="^(test|soru|sayfa|deneme|etkinlik)$")
    day_hint: str | None = None
    teacher_homework: bool = False
    source: str = Field(default="rehber", pattern="^(rehber|deneme|sablon)$")
    exam_result_id: int | None = None
    page_from: int | None = Field(default=None, ge=1, le=5000)   # sayfa aralığı (unit=sayfa)
    page_to: int | None = Field(default=None, ge=1, le=5000)


class PoolQuantityBody(BaseModel):
    quantity: int = Field(ge=1, le=500)


class PoolApproveBody(BaseModel):
    approved: bool = True


class ClassPositionBody(BaseModel):
    subject_id: int
    topic_id: int | None = None


class LessonDaysBody(BaseModel):
    lessons: dict[str, list[int]]      # "0".."6" → subject_id listesi


class ParseBody(BaseModel):
    text: str = Field(min_length=1, max_length=300)
    subject_id: int | None = None


class ParseChip(BaseModel):
    kind: str                         # subject | topic | book | section | quantity | unit | text
    id: int | None = None
    label: str
    confident: bool = True


class ParseOption(BaseModel):
    """Belirsiz ayrıştırmada "Bunu mu demek istedin?" seçeneği (konu ya da yalnız ders)."""
    subject_id: int
    subject_name: str
    topic_id: int | None = None
    topic_name: str | None = None
    grade_level: int | None = None
    unit_name: str | None = None
    book_id: int | None = None
    section_id: int | None = None
    label: str | None = None


class ParseBase(BaseModel):
    quantity: int | None = None
    unit: str = "test"


class ParseResponse(BaseModel):
    chips: list[ParseChip] = []
    draft: PoolItemBody | None = None  # doğruysa tek dokunuşla eklenebilir
    warning: str | None = None
    options: list[ParseOption] = []    # belirsizlikte seçilecek konu/ders (taslak yokken)
    base: ParseBase | None = None      # seçenek seçilince kullanılacak miktar/birim


# ---- seans ekranı (K18–K22)

class SessionExamTopic(BaseModel):
    topic_id: int
    name: str
    wrong: int


class SessionExamStrip(BaseModel):
    exam_id: int
    title: str
    exam_date: str
    net: float
    delta: float | None = None
    prev_title: str | None = None
    in_period: bool = False
    wrong_topics: list[SessionExamTopic] = []
    studied_but_wrong: list[SessionExamTopic] = []


class SessionPrevious(BaseModel):
    id: int
    session_date: str
    agenda: str
    coach_note: str | None = None
    next_change: str | None = None
    mood: int | None = None


class SessionAgendaOut(BaseModel):
    id: str
    text: str
    source: str | None = None


class SessionItemOut(PoolItemOut):
    session_marked: int = 0
    done_units: int = 0
    avoided: bool = False
    avoided_reason: str | None = None
    # Seansta konu kapatma (2026-10-14): kalemin konusu (kendi konusu ya da kitap bölümünün eşli konusu)
    closure_topic_id: int | None = None
    topic_closed: bool = False


class PoolSessionResponse(BaseModel):
    student: PoolStudentOut
    period: PoolPeriodOut | None = None
    headline: str
    items: list[SessionItemOut] = []
    avoided: list[SessionItemOut] = []
    pending_student_items: list[SessionItemOut] = []
    exam: SessionExamStrip | None = None
    previous_session: SessionPrevious | None = None
    agenda_queue: list[SessionAgendaOut] = []
    flags: PoolFlagsOut = PoolFlagsOut()  # Adım 4: seans ekranında sinyaller (K44/K47/K48)
    today: str


class SessionMarkBody(BaseModel):
    count: int = Field(ge=0, le=500)
    note: str | None = Field(default=None, max_length=300)


class CarryIn(BaseModel):
    item_id: int
    quantity: int | None = Field(default=None, ge=1, le=500)


class SessionFinishBody(BaseModel):
    closed_on: str
    expected_next_on: str | None = None
    carry: list[CarryIn] = []
    record_session: bool = True
    agenda: str | None = Field(default=None, max_length=5000)
    coach_note: str | None = Field(default=None, max_length=8000)
    next_change: str | None = Field(default=None, max_length=2000)
    mood: int | None = Field(default=None, ge=1, le=5)
    new_period_note: str | None = Field(default=None, max_length=1000)
    # 2026-10-15: "Bu seansla gün gün programa geç" — yeni dönem açılmaz, devir yapılmaz.
    switch_to_gun_gun: bool = False


# ---- öğrenci yüzeyi (Adım 3; K34–K41)

class StudentPoolItemOut(BaseModel):
    id: int
    subject_id: int | None
    subject_name: str
    title: str                        # konu / kitap — bölüm / serbest metin
    book_name: str | None = None
    quantity: int
    unit: str
    done: int                         # öğrenci kaydı + rehber işareti
    remaining: int
    day_hint: str | None = None
    source: str
    teacher_homework: bool = False
    approval: str
    counts: bool = True
    in_cup_today: bool = False
    cup_task_id: int | None = None
    suggested: bool = False           # K37 kap önerisi (gün etiketi / bugün dershanede işlenen ders)


class StudentCupTask(BaseModel):
    task_id: int
    item_id: int | None
    subject_name: str | None = None   # kaptaki görevin dersi (renk + etiket)
    title: str
    status: str
    planned: int
    completed: int
    can_return: bool                  # ilerleme yoksa havuza geri alınabilir


class StudentPoolProjectionSubject(BaseModel):
    subject_id: int | None = None
    name: str
    units: int


class StudentPoolProjectionDay(BaseModel):
    date: str
    units: int
    lessons: list[str] = []                               # o gün dershanede işlenen dersler
    subjects: list[StudentPoolProjectionSubject] = []     # o güne önerilen birimler (ders ders)


class StudentPoolSummary(BaseModel):
    pct: int
    total_units: int
    done_units: int
    items_total: int
    items_done: int
    days_left: int
    per_day_needed: float
    expected_next_on: str | None = None
    pace: str                         # onde | yolunda | geride | belirsiz
    pace_note: str                    # K41 yargılamayan tek cümle


class StudentPoolSubject(BaseModel):
    id: int
    name: str
    group: str = "okul"        # okul | sinav (kalem ekleme penceresinde gruplama)
    is_ayt: bool = False


class StudentPoolHint(BaseModel):
    """K41/K46/K48: öğrenciye yönlendirme cümlesi — kırmızı yok, yargı yok."""
    code: str
    title: str
    note: str


class StudentPoolResponse(BaseModel):
    mode: str
    period_id: int | None = None
    opened_on: str | None = None
    summary: StudentPoolSummary | None = None
    items: list[StudentPoolItemOut] = []
    cup: list[StudentCupTask] = []
    projection: list[StudentPoolProjectionDay] = []
    lesson_today: list[str] = []
    subjects: list[StudentPoolSubject] = []
    hints: list[StudentPoolHint] = []
    previous: list["PoolPeriodBrief"] = []   # K60: önceki dönemler (öğrenci görür)
    on_break: PoolBreakOut | None = None     # K61
    units: list[str] = []
    today: str
    lesson_days_set: bool = False   # şube ders programı girilmiş mi (dağılım ona göre)


class StudentCupBody(BaseModel):
    item_id: int
    count: int | None = Field(default=None, ge=1, le=500)


class StudentCupResizeBody(BaseModel):
    count: int = Field(ge=1, le=500)


class StudentPoolItemBody(BaseModel):
    subject_id: int
    topic_id: int | None = None
    label: str | None = Field(default=None, max_length=255)
    quantity: int | None = Field(default=None, ge=1, le=500)
    unit: str = Field(pattern="^(test|soru|sayfa|deneme|etkinlik)$")
    teacher_homework: bool = False   # K11: ders/özel ders öğretmeninin ödevi


class StudentCloseDayBody(BaseModel):
    date: str | None = None


# ---------------------------------------------------------------- K53 veli seans özeti

class PoolParentSummarySubject(BaseModel):
    subject: str
    total: int
    done: int
    items: int
    items_done: int
    pct: int


class PoolParentSummaryItem(BaseModel):
    subject: str
    name: str
    quantity: int
    unit: str
    done: int
    is_done: bool
    teacher_homework: bool = False


class PoolParentSummaryCarried(BaseModel):
    subject: str
    name: str
    quantity: int
    unit: str


class PoolParentSummaryExam(BaseModel):
    title: str
    date: str
    net: float
    delta: float | None = None
    prev_title: str | None = None


class PoolParentRecipient(BaseModel):
    parent_id: int
    name: str
    email: str | None = None
    will_send: bool
    reason: str | None = None


class PoolParentSummaryResponse(BaseModel):
    period_id: int
    student_id: int
    student_name: str
    opened_on: str
    closed_on: str
    opened_label: str | None = None
    closed_label: str | None = None
    days: int
    pct: int
    done_units: int
    total_units: int
    items_done: int
    items_total: int
    subjects: list[PoolParentSummarySubject] = []
    items: list[PoolParentSummaryItem] = []
    carried: list[PoolParentSummaryCarried] = []
    exam: PoolParentSummaryExam | None = None
    narrative: list[str] = []
    include_items: bool = True
    include_exam: bool = True
    recipients: list[PoolParentRecipient] = []
    is_sent_snapshot: bool = False
    sent_at: str | None = None


class PoolParentSummarySendBody(BaseModel):
    narrative: list[str] | None = None
    include_items: bool = True
    include_exam: bool = True


class PoolParentSummarySendResult(BaseModel):
    queued: int
    suppressed: int
    sent: bool
    sent_at: str | None = None


# ---------------------------------------------------------------- K48/K50 günlük görüşme listesi

class PoolDailyRow(BaseModel):
    student_id: int
    student_name: str
    class_group: str | None = None
    session_today: bool
    appointment_time: str | None = None
    appointment_id: int | None = None
    period_id: int | None = None
    days_open: int | None = None
    expected_next_on: str | None = None
    pct: int | None = None
    level: str
    headline: str
    primary: PoolFlagOut | None = None
    primary_snoozed: bool = False
    extra: list[PoolFlagOut] = []
    good: list[PoolFlagOut] = []
    paper_student: bool = False


class PoolDailyCounts(BaseModel):
    students: int
    sessions_today: int
    red: int
    amber: int
    snoozed: int


class PoolDailyResponse(BaseModel):
    today: str
    rows: list[PoolDailyRow] = []
    counts: PoolDailyCounts


# ---------------------------------------------------------------- K52 veli salt-okuma

class ParentPoolItem(BaseModel):
    id: int
    subject_name: str
    title: str
    quantity: int
    unit: str
    done: int
    remaining: int
    teacher_homework: bool = False
    in_cup_today: bool = False


class ParentPoolCup(BaseModel):
    title: str
    status: str


class ParentPoolResponse(BaseModel):
    mode: str
    period_id: int | None = None
    opened_on: str | None = None
    expected_next_on: str | None = None
    days_open: int | None = None
    summary: StudentPoolSummary | None = None
    items: list[ParentPoolItem] = []
    cup: list[ParentPoolCup] = []
    previous: list[PoolPeriodBrief] = []
    on_break: PoolBreakOut | None = None
    today: str


# ---------------------------------------------------------------- K60 dönem geçmişi (sayfalı)

class PoolHistorySubject(BaseModel):
    subject: str
    total: int
    done: int
    pct: int


class PoolHistoryRow(BaseModel):
    id: int
    opened_on: str
    closed_on: str | None = None
    expected_next_on: str | None = None
    status: str
    status_label: str
    note: str | None = None
    total_units: int
    done_units: int
    pct: int
    items_total: int
    items_done: int
    session_marked_units: int
    carried_in: int
    carried_out: int
    has_session: bool
    parent_summary_sent_at: str | None = None
    subjects: list[PoolHistorySubject] = []


class PoolHistoryResponse(BaseModel):
    total: int
    offset: int
    limit: int
    rows: list[PoolHistoryRow] = []


# ---------------------------------------------------------------- dönem penceresi (geçmiş dönem içi, 2026-10-13)

class PoolPeriodDetailItem(BaseModel):
    id: int
    subject_id: int | None = None
    subject_name: str
    title: str
    topic_name: str | None = None
    book_name: str | None = None
    section_label: str | None = None
    label: str | None = None
    quantity: int
    unit: str
    completed: int                    # öğrenci kaydı
    session_marked: int               # rehber seansta işaretledi (K18)
    done: int
    remaining: int
    source: str
    teacher_homework: bool = False
    approval: str
    counts: bool = True
    carry_count: int = 0
    cup_attempts: int = 0             # yalnız rehber yüzeyinde dolu
    cup_returns: int = 0              # yalnız rehber yüzeyinde dolu (K44)
    carried_out: bool = False         # sonraki döneme devredildi
    exam_linked: bool = False         # denemeden eklendi (K29)
    day_hint: str | None = None
    removed: bool = False
    removed_at: str | None = None
    created_by_name: str | None = None


class PoolPeriodDayTask(BaseModel):
    task_id: int
    item_id: int | None = None
    title: str
    status: str                       # pending | partial | completed
    type: str
    planned: int | None = None        # kalemsiz etkinlikte None
    done: int
    correct: int | None = None
    wrong: int | None = None
    blank: int | None = None
    period: str | None = None         # sabah / öğle / akşam (varsa)
    itemless: bool = False


class PoolPeriodDay(BaseModel):
    date: str
    weekday: int                      # 0 = Pazartesi
    tasks: list[PoolPeriodDayTask] = []
    done_units: int = 0


class PoolPeriodDetailResponse(BaseModel):
    period: PoolHistoryRow
    items: list[PoolPeriodDetailItem] = []
    removed_items: list[PoolPeriodDetailItem] = []   # yalnız rehber (iz)
    days: list[PoolPeriodDay] = []
    audience: str                     # teacher | student | parent
    today: str


# ---------------------------------------------------------------- dönem silme (2026-10-13)

class PoolPeriodDeleteImpact(BaseModel):
    period_id: int
    deletable: bool
    blocked_reason: str | None = None
    items: int
    removed_items: int
    tasks_kept: int
    tasks_deleted: int
    done_units: int
    session_marked_units: int
    carried_out: int
    parent_summary_sent: bool


# ---------------------------------------------------------------- "Nereden? → Öğrencinin kitapları" (2026-10-13)

class PoolBookSectionOut(BaseModel):
    section_id: int
    label: str
    test_count: int
    completed: int
    remaining: int          # test − çözülen − (gün-gün rezerv)
    in_pool: int            # açık dönemde havuzda bekleyen
    available: int          # remaining − in_pool
    topic_name: str | None = None
    last_on: str | None = None
    is_last: bool = False   # bu kitapta en son verilen bölüm (SON)


class PoolBookOut(BaseModel):
    book_id: int
    name: str
    publisher: str | None = None
    type: str
    type_label: str
    is_deneme: bool
    total_tests: int
    completed: int
    sections: list[PoolBookSectionOut] = []


class PoolBooksResponse(BaseModel):
    subject_id: int
    subject_name: str
    books: list[PoolBookOut] = []

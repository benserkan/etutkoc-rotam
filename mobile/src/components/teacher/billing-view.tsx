import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { Pressable, Text, TextInput, View } from "react-native";

import { FormSheet } from "@/components/ui/form-sheet";
import type { BillingMonthResponse, BillingStudentRow, PaymentCreateBody } from "@/lib/teacher";
import { cn } from "@/lib/utils";

const TR_MONTHS = [
  "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
  "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
];
function monthLabel(ym: string): string {
  const [y, m] = ym.split("-").map(Number);
  if (!y || !m) return ym;
  return `${TR_MONTHS[m - 1]} ${y}`;
}
function shiftMonth(ym: string, delta: number): string {
  const [y, m] = ym.split("-").map(Number);
  const d = new Date(y, m - 1 + delta, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}
function tl(n: number | null | undefined): string {
  if (n == null) return "—";
  return `${n.toLocaleString("tr-TR")} ₺`;
}
function todayISO(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

const STATUS: Record<string, { bg: string; text: string; label: string }> = {
  no_rate: { bg: "bg-slate-100", text: "text-slate-600", label: "Ücret yok" },
  paid: { bg: "bg-emerald-50", text: "text-emerald-700", label: "Ödendi" },
  partial: { bg: "bg-amber-50", text: "text-amber-700", label: "Kısmi" },
  pending: { bg: "bg-rose-50", text: "text-rose-700", label: "Bekliyor" },
};

function NumField({
  label,
  value,
  onChangeText,
  maxLen = 7,
}: {
  label: string;
  value: string;
  onChangeText: (v: string) => void;
  maxLen?: number;
}) {
  return (
    <View className="flex-1 gap-1">
      <Text className="text-xs font-medium text-slate-600">{label}</Text>
      <TextInput
        value={value}
        onChangeText={(v) => onChangeText(v.replace(/[^0-9]/g, "").slice(0, maxLen))}
        keyboardType="number-pad"
        placeholder="0"
        placeholderTextColor="#cbd5e1"
        className="rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-lg font-semibold text-slate-900"
      />
    </View>
  );
}

function RateForm({ row, busy, onSubmit }: { row: BillingStudentRow; busy: boolean; onSubmit: (fee: number) => void }) {
  const [fee, setFee] = React.useState(row.session_fee != null ? String(row.session_fee) : "");
  const n = Number(fee) || 0;
  return (
    <View className="gap-4 pb-2">
      <Text className="text-sm text-slate-600">
        {row.student_name} için <Text className="font-semibold">seans başına</Text> ücreti belirle.
      </Text>
      <NumField label="Seans ücreti (₺)" value={fee} onChangeText={setFee} />
      <Pressable
        onPress={() => onSubmit(n)}
        disabled={busy || n <= 0}
        className={cn("items-center rounded-xl py-3.5", busy || n <= 0 ? "bg-brand-700/40" : "bg-brand-700 active:bg-brand-800")}
      >
        <Text className="text-base font-semibold text-white">{busy ? "Kaydediliyor…" : "Ücreti kaydet"}</Text>
      </Pressable>
    </View>
  );
}

const METHODS = [
  { v: "cash", label: "Nakit" },
  { v: "transfer", label: "Havale/EFT" },
  { v: "other", label: "Diğer" },
];

function PaymentForm({
  row,
  month,
  busy,
  onSubmit,
}: {
  row: BillingStudentRow;
  month: string;
  busy: boolean;
  onSubmit: (body: PaymentCreateBody) => void;
}) {
  const [amount, setAmount] = React.useState(row.balance != null && row.balance > 0 ? String(row.balance) : "");
  const [method, setMethod] = React.useState<"cash" | "transfer" | "other">("cash");
  const n = Number(amount) || 0;
  return (
    <View className="gap-4 pb-2">
      <Text className="text-sm text-slate-600">
        {row.student_name} · {monthLabel(month)} · kalan {tl(row.balance)}
      </Text>
      <NumField label="Ödeme tutarı (₺)" value={amount} onChangeText={setAmount} />
      <View className="gap-1.5">
        <Text className="text-xs font-medium text-slate-600">Yöntem</Text>
        <View className="flex-row gap-2">
          {METHODS.map((m) => {
            const active = m.v === method;
            return (
              <Pressable
                key={m.v}
                onPress={() => setMethod(m.v as "cash" | "transfer" | "other")}
                className={cn(
                  "rounded-full border px-3 py-1.5",
                  active ? "border-brand-600 bg-brand-50" : "border-slate-300 bg-white",
                )}
              >
                <Text className={cn("text-sm font-medium", active ? "text-brand-700" : "text-slate-600")}>{m.label}</Text>
              </Pressable>
            );
          })}
        </View>
      </View>
      <Pressable
        onPress={() => onSubmit({ amount: n, paid_at: todayISO(), method, period_month: month })}
        disabled={busy || n <= 0}
        className={cn("items-center rounded-xl py-3.5", busy || n <= 0 ? "bg-emerald-600/50" : "bg-emerald-600 active:bg-emerald-700")}
      >
        <Text className="text-base font-semibold text-white">{busy ? "Kaydediliyor…" : "Ödemeyi kaydet"}</Text>
      </Pressable>
    </View>
  );
}

export function BillingView({
  data,
  busy,
  onPrev,
  onNext,
  onSetRate,
  onPay,
}: {
  data: BillingMonthResponse;
  busy: boolean;
  onPrev: () => void;
  onNext: () => void;
  onSetRate: (studentId: number, fee: number) => void;
  onPay: (studentId: number, body: PaymentCreateBody) => void;
}) {
  const [rateRow, setRateRow] = React.useState<BillingStudentRow | null>(null);
  const [payRow, setPayRow] = React.useState<BillingStudentRow | null>(null);
  const t = data.totals;
  const isCurrentOrFuture = data.month >= shiftMonth(todayISO().slice(0, 7), 0);

  return (
    <View className="flex-1 gap-4 px-4 py-4">
      {/* Ay seçici */}
      <View className="flex-row items-center justify-between rounded-2xl border border-slate-200 bg-white px-2 py-2">
        <Pressable onPress={onPrev} hitSlop={8} className="size-10 items-center justify-center rounded-full active:bg-slate-100">
          <Ionicons name="chevron-back" size={22} color="#334155" />
        </Pressable>
        <Text className="text-base font-bold text-slate-900">{monthLabel(data.month)}</Text>
        <Pressable
          onPress={onNext}
          disabled={isCurrentOrFuture}
          hitSlop={8}
          className="size-10 items-center justify-center rounded-full active:bg-slate-100"
        >
          <Ionicons name="chevron-forward" size={22} color={isCurrentOrFuture ? "#cbd5e1" : "#334155"} />
        </Pressable>
      </View>

      {/* Toplamlar */}
      <View className="flex-row gap-3">
        <View className="flex-1 rounded-2xl border border-slate-200 bg-white p-3">
          <Text className="text-[11px] font-medium text-slate-400">Tahakkuk</Text>
          <Text className="mt-1 text-lg font-extrabold text-slate-900">{tl(t.accrued)}</Text>
        </View>
        <View className="flex-1 rounded-2xl border border-slate-200 bg-white p-3">
          <Text className="text-[11px] font-medium text-slate-400">Tahsil</Text>
          <Text className="mt-1 text-lg font-extrabold text-emerald-600">{tl(t.paid)}</Text>
        </View>
        <View className="flex-1 rounded-2xl border border-slate-200 bg-white p-3">
          <Text className="text-[11px] font-medium text-slate-400">Kalan</Text>
          <Text className={cn("mt-1 text-lg font-extrabold", t.balance > 0 ? "text-rose-600" : "text-slate-900")}>
            {tl(t.balance)}
          </Text>
        </View>
      </View>

      {/* Öğrenci satırları */}
      {data.rows.length === 0 ? (
        <View className="mt-6 items-center gap-2 px-6">
          <Ionicons name="wallet-outline" size={40} color="#94a3b8" />
          <Text className="text-center text-sm text-slate-500">Bu ay için kayıt yok.</Text>
        </View>
      ) : (
        <View className="gap-2.5">
          {data.rows.map((r) => {
            const st = STATUS[r.status] ?? STATUS.pending;
            return (
              <View key={r.student_id} className="rounded-2xl border border-slate-200 bg-white p-4">
                <View className="flex-row items-center justify-between gap-2">
                  <Text className="flex-1 text-[15px] font-semibold text-slate-900" numberOfLines={1}>
                    {r.student_name}
                  </Text>
                  <View className={cn("rounded-full px-2 py-0.5", st.bg)}>
                    <Text className={cn("text-[11px] font-semibold", st.text)}>{st.label}</Text>
                  </View>
                </View>
                <Text className="mt-1 text-xs text-slate-500">
                  {r.session_fee != null ? `${tl(r.session_fee)}/seans · ` : ""}
                  {r.done_sessions} seans · tahakkuk {tl(r.accrued)} · ödenen {tl(r.paid)}
                  {r.balance != null && r.balance > 0 ? ` · kalan ${tl(r.balance)}` : ""}
                </Text>
                <View className="mt-3 flex-row gap-2">
                  <Pressable
                    onPress={() => setRateRow(r)}
                    className="flex-1 items-center rounded-xl border border-slate-300 py-2.5 active:bg-slate-50"
                  >
                    <Text className="text-sm font-semibold text-slate-700">
                      {r.session_fee != null ? "Ücreti düzenle" : "Ücret belirle"}
                    </Text>
                  </Pressable>
                  {r.session_fee != null ? (
                    <Pressable
                      onPress={() => setPayRow(r)}
                      className="flex-1 items-center rounded-xl bg-emerald-600 py-2.5 active:bg-emerald-700"
                    >
                      <Text className="text-sm font-semibold text-white">
                        {r.balance != null && r.balance > 0 ? "Ödeme gir" : "Ödeme ekle"}
                      </Text>
                    </Pressable>
                  ) : null}
                </View>
              </View>
            );
          })}
        </View>
      )}

      <FormSheet visible={rateRow != null} title="Seans ücreti" onClose={() => setRateRow(null)}>
        {rateRow ? (
          <RateForm
            row={rateRow}
            busy={busy}
            onSubmit={(fee) => {
              onSetRate(rateRow.student_id, fee);
              setRateRow(null);
            }}
          />
        ) : null}
      </FormSheet>

      <FormSheet visible={payRow != null} title="Ödeme kaydet" onClose={() => setPayRow(null)}>
        {payRow ? (
          <PaymentForm
            row={payRow}
            month={data.month}
            busy={busy}
            onSubmit={(body) => {
              onPay(payRow.student_id, body);
              setPayRow(null);
            }}
          />
        ) : null}
      </FormSheet>
    </View>
  );
}

import * as React from "react";
import * as Notifications from "expo-notifications";
import { router } from "expo-router";

import { useAuth } from "./auth";

/**
 * Push bildirimine tıklayınca doğru ekrana götürür (deep-link).
 *
 * Bildirim `data` alanı backend'de set edilir:
 *   - veli: { type: "parent_notification", kind, student_id }
 *   - destek: { type: "support", request_id }
 *
 * Soğuk açılışta (uygulama kapalıyken tık) bildirim auth hazır olmadan gelebilir
 * → href "pending"e yazılır, authed olunca yönlendirilir (router hazır olur).
 */
type NotifData = Record<string, unknown> | null | undefined;

export function hrefForNotificationData(data: NotifData): string | null {
  if (!data || typeof data !== "object") return null;
  const type = data.type as string | undefined;

  if (type === "support" && data.request_id != null) {
    return `/support-thread?id=${data.request_id}`;
  }

  if (type === "parent_notification") {
    const sid = data.student_id;
    if (sid == null) return "/(app)/parent/notifications";
    const kind = data.kind as string | undefined;
    switch (kind) {
      case "weekly_report":
        return `/parent-child-report?id=${sid}`; // geçen hafta performansı
      case "new_program":
        return `/parent-child-week?id=${sid}`; // bu haftanın programı
      case "teacher_note":
      case "drop_alert":
      case "exam_approaching":
      case "empty_day":
      case "daily_summary":
      default:
        return `/parent-child?id=${sid}`; // çocuk detayı
    }
  }

  return null;
}

export function NotificationObserver() {
  const { status } = useAuth();
  const statusRef = React.useRef(status);
  statusRef.current = status;
  const pending = React.useRef<string | null>(null);
  const coldHandled = React.useRef(false);

  const handle = React.useCallback((data: NotifData) => {
    const href = hrefForNotificationData(data);
    if (!href) return;
    if (statusRef.current === "authed") {
      router.push(href as never);
    } else {
      pending.current = href;
    }
  }, []);

  // Sıcak tık (uygulama açıkken/arka planda).
  React.useEffect(() => {
    const sub = Notifications.addNotificationResponseReceivedListener((resp) => {
      handle(resp.notification.request.content.data as NotifData);
    });
    return () => sub.remove();
  }, [handle]);

  // Soğuk açılış (uygulama kapalıyken tık) — pending'e yaz, authed'de yönlendir.
  React.useEffect(() => {
    if (coldHandled.current) return;
    coldHandled.current = true;
    Notifications.getLastNotificationResponseAsync()
      .then((resp) => {
        if (resp) {
          const href = hrefForNotificationData(resp.notification.request.content.data as NotifData);
          if (href) pending.current = href;
        }
      })
      .catch(() => {});
  }, []);

  // Authed olunca bekleyen yönlendirmeyi uygula (router artık hazır).
  React.useEffect(() => {
    if (status === "authed" && pending.current) {
      const href = pending.current;
      pending.current = null;
      // Navigasyon yığını otursun diye bir tık ertele.
      const t = setTimeout(() => router.push(href as never), 150);
      return () => clearTimeout(t);
    }
  }, [status]);

  return null;
}

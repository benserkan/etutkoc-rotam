import * as React from "react";
import { ScrollView, Text, View } from "react-native";

/**
 * Render hatalarını yakalayıp EKRANDA gösterir (release build'de sessiz çökme
 * yerine). Teşhis için kritik — APK'da JS hatası olursa kullanıcı mesajı görür.
 */
interface State {
  error: Error | null;
  info: string | null;
}

export class ErrorBoundary extends React.Component<{ children: React.ReactNode }, State> {
  state: State = { error: null, info: null };

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { error };
  }

  componentDidCatch(error: Error, info: { componentStack?: string | null }) {
    this.setState({ error, info: info?.componentStack ?? null });
    // eslint-disable-next-line no-console
    console.error("ErrorBoundary caught:", error, info?.componentStack);
  }

  render() {
    const { error, info } = this.state;
    if (!error) return this.props.children;
    return (
      <View style={{ flex: 1, backgroundColor: "#fff", paddingTop: 64 }}>
        <ScrollView contentContainerStyle={{ padding: 20 }}>
          <Text style={{ fontSize: 18, fontWeight: "800", color: "#be123c", marginBottom: 8 }}>
            Uygulama hatası
          </Text>
          <Text style={{ fontSize: 14, color: "#0f172a", marginBottom: 12 }}>
            {error.name}: {error.message}
          </Text>
          {error.stack ? (
            <Text selectable style={{ fontSize: 11, color: "#475569", fontFamily: "monospace" }}>
              {error.stack}
            </Text>
          ) : null}
          {info ? (
            <Text selectable style={{ fontSize: 11, color: "#94a3b8", marginTop: 12, fontFamily: "monospace" }}>
              {info}
            </Text>
          ) : null}
        </ScrollView>
      </View>
    );
  }
}

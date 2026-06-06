import * as React from "react";
import {
  KeyboardAvoidingView,
  Modal,
  Pressable,
  ScrollView,
  Text,
  View,
} from "react-native";

/** Alttan açılan form modalı (klavyeden kaçınır + tutamak + başlık). */
export function FormSheet({
  visible,
  title,
  onClose,
  children,
}: {
  visible: boolean;
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  return (
    <Modal visible={visible} transparent statusBarTranslucent animationType="slide" onRequestClose={onClose}>
      <View className="flex-1">
        <Pressable className="absolute inset-0 bg-black/40" onPress={onClose} />
        <KeyboardAvoidingView
          className="flex-1 justify-end"
          // Android'de de "padding" şart — alttan açılan sheet klavyenin üstüne
          // çıksın (önceden undefined idi → klavye formu örtüyordu).
          behavior="padding"
        >
          <View className="max-h-[90%] rounded-t-3xl bg-white px-5 pb-8 pt-3">
            <View className="mb-2 items-center">
              <View className="h-1.5 w-10 rounded-full bg-slate-300" />
            </View>
            <View className="mb-2 flex-row items-center justify-between">
              <Text className="text-lg font-bold text-slate-900">{title}</Text>
              <Pressable onPress={onClose} hitSlop={10} className="rounded-full p-1 active:bg-slate-100">
                <Text className="text-base font-semibold text-slate-400">Kapat</Text>
              </Pressable>
            </View>
            <ScrollView keyboardShouldPersistTaps="handled" keyboardDismissMode="interactive">
              {children}
            </ScrollView>
          </View>
        </KeyboardAvoidingView>
      </View>
    </Modal>
  );
}

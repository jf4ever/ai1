# Сборка APK

Добавлен Android-проект `app/` и скрипт автоматической сборки.

## Быстрый запуск

```bash
./scripts/build_apk_local.sh
```

Скрипт запускает `gradle :app:assembleDebug` и копирует артефакт в:

- `dist/overlaytester-debug.apk`

## Ручная команда

```bash
JAVA_HOME=/root/.local/share/mise/installs/java/17.0.2 \
PATH=/root/.local/share/mise/installs/java/17.0.2/bin:$PATH \
gradle :app:assembleDebug
```

Ожидаемый APK после успешной сборки:

- `app/build/outputs/apk/debug/app-debug.apk`

## Почему в этом окружении APK не собирается

Текущее окружение блокирует выход в внешние репозитории (Google/Maven/Plugin Portal), из-за чего Gradle не может скачать Android Gradle Plugin `com.android.application` и зависимости Android SDK. Поэтому сборка прерывается до генерации APK.

# Сборка APK

В репозиторий добавлен Android-проект (`app/`) с `MainActivity` и кнопками Start/Stop.

## Команда сборки

```bash
JAVA_HOME=/root/.local/share/mise/installs/java/17.0.2 \
PATH=/root/.local/share/mise/installs/java/17.0.2/bin:$PATH \
gradle :app:assembleDebug
```

Ожидаемый артефакт после успешной сборки:

`app/build/outputs/apk/debug/app-debug.apk`

## Ограничение текущего окружения

В этом окружении недоступно получение Android Gradle Plugin/SDK из внешних репозиториев, поэтому сборка останавливается на этапе резолва плагина `com.android.application`.

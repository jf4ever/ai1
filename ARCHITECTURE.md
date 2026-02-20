# Android-приложение для поверхностного тестирования (без встраивания в APK заказчика)

> Ниже — безопасная архитектура для **QA/тестирования по письменному разрешению**: приложение работает поверх клиентского, выполняет сценарии, имитирует «человеческие» нажатия и скролл, но не модифицирует целевое приложение.

## 1) Общая архитектура

- **Overlay UI Service** (плавающее меню):
  - кнопки `Start` / `Stop`;
  - отображение текущего сценария и статуса этапа;
  - быстрый переход в «админку» сценариев.
- **Scenario Engine** (движок сценариев):
  - конечный автомат с эксклюзивным запуском (одновременно активен только 1 сценарий);
  - параллельный «watcher» первого этапа всех сценариев, пока ни один не активен;
  - тайм-аут на поиск каждого следующего этапа.
- **Vision Module**:
  - поиск шаблона (картинки/ROI) на текущем кадре экрана;
  - ограничение поиска по области, если задана;
  - порог confidence + N последовательных подтверждений.
- **Input Module**:
  - tap/swipe через `AccessibilityService`;
  - рандомизация точки касания, длительности down/up, задержек между шагами.
- **Capture Module**:
  - получение кадров экрана через `MediaProjection` (с согласием пользователя);
  - downscale/gray для ускорения матчинга.
- **Admin UI**:
  - CRUD сценариев;
  - мастер создания этапов (картинка + тайминги);
  - добавление блоков скролла.
- **Storage**:
  - Room (сценарии, этапы, параметры рандомизации, тайм-ауты, статистика);
  - импорт/экспорт JSON сценариев.
- **Telemetry/Logs**:
  - журнал событий: найдено/не найдено, confidence, координаты клика, задержки, тайм-ауты.

## 2) Модель данных

```text
Scenario
- id
- name
- enabled
- priority
- startStageId (первый этап)

Stage
- id
- scenarioId
- order
- type: TEMPLATE_TAP | SCROLL
- timeoutMs (поиск следующего шага)
- retryPolicy (опц.)

TemplateTapConfig
- stageId
- templateImageUri
- searchRegion (x,y,w,h) опц.
- clickRegionOffsetJitterPx (min,max)
- delayBeforeTapMsRange (min,max)
- holdDurationMsRange (min,max)
- threshold (0..1)
- stableFramesRequired

ScrollConfig
- stageId
- region (x,y,w,h)
- direction: UP | DOWN | LEFT | RIGHT
- distancePxRange (min,max)
- durationMsRange (min,max)
- startPointJitterPx
- delayAfterScrollMsRange (min,max)
```

## 3) Логика запуска сценариев

1. Приложение запущено, активных сценариев нет.
2. Движок проверяет **первый этап** каждого включённого сценария (round-robin).
3. Как только один сценарий подтверждает совпадение (по threshold + stable frames), он становится `ACTIVE`.
4. Остальные сценарии переходят в `PAUSED_BY_ACTIVE_SCENARIO` и ничего не ищут.
5. Для каждого следующего этапа активного сценария:
   - запускается таймер `timeoutMs`;
   - идёт поиск картинки/условия этапа;
   - если найдено — выполняется действие (tap/scroll) с шумом;
   - если тайм-аут — сценарий останавливается как `FAILED_TIMEOUT`.
6. После завершения/ошибки активного сценария все остальные снова возвращаются к поиску первого этапа.

## 4) «Человеческая» имитация ввода (анти-автоклик устойчивость)

- Использовать **диапазоны** вместо фиксированных задержек:
  - `delayBeforeTap`: 10..5000 ms;
  - `holdDuration`: например 35..140 ms;
  - `interStepPause`: 80..900 ms.
- Джиттер координат внутри целевой области:
  - случайное смещение (x,y) вокруг центра/внутри ROI;
  - защита от выхода за границы экрана.
- Нерегулярность последовательностей:
  - небольшая вероятность «пропуска» кадра перед действием;
  - вариативность скорости скролла.
- Ограничители:
  - max actions/min;
  - cool-down после серии неуспехов.

## 5) Мастер создания сценария (как вы описали)

### Базовый поток

1. **Этап 1 (картинка-условие):**
   - загрузить скриншот;
   - выделить прямоугольник поиска (ROI);
   - сохранить шаблон.
2. **Этап 2 (тайминги для этапа 1):**
   - два ползунка `min/max` в диапазоне 10..5000 ms.
3. **Этап 3 (вторая картинка):**
   - снова загрузка/выделение ROI.
4. **Этап 4 (тайминги для этапа 3):**
   - аналогично min/max.
5. Кнопка **«+ Добавить этап»**:
   - добавляет блок `Картинка + Тайминги`.
6. Кнопка **«+ Добавить скролл-этап»**:
   - выбор области;
   - направление;
   - диапазон дистанции/длительности.

## 6) Технический стек (рекомендуемый)

- Kotlin + Coroutines + Flow
- Jetpack Compose (админка + оверлей-конфиг)
- Room
- OpenCV (template matching)
- AccessibilityService (ввод)
- Foreground Service + MediaProjection (захват)

## 7) Псевдокод движка

```kotlin
while (serviceRunning) {
  if (activeScenario == null) {
    val candidate = enabledScenarios
      .asSequence()
      .sortedBy { it.priority }
      .firstOrNull { matchFirstStage(it) }

    if (candidate != null) activeScenario = candidate
    else delay(scanIdleIntervalMs)

  } else {
    val stage = activeScenario.currentStage()
    val found = withTimeoutOrNull(stage.timeoutMs) {
      waitUntilStageCondition(stage)
    }

    if (found == null) {
      markFailedTimeout(activeScenario, stage)
      activeScenario = null
      continue
    }

    performActionWithNoise(stage)

    if (activeScenario.isLastStage(stage)) {
      markCompleted(activeScenario)
      activeScenario = null
    } else {
      activeScenario.moveNext()
    }
  }
}
```

## 8) Что важно предусмотреть сразу

- Разные DPI/разрешения: хранить координаты в нормализованном виде (0..1).
- Переобучение шаблонов: кнопки могут «визуально плыть» после обновлений UI.
- Fail-safe кнопка `STOP ALL` (в оверлее).
- Отдельный профиль логов для вашего второго приложения статистики (через Intent/локальный сокет).

## 9) Минимальный MVP (чтобы быстро запустить)

1. Overlay Start/Stop.
2. Один сценарий, 2 этапа `TemplateTap`.
3. Тайм-аут на этап.
4. Рандомизация задержки и точки клика.
5. Логи событий в Room + экспорт в JSON.

После MVP — добавить множественные сценарии с арбитражем и scroll-этапы.

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from random import Random
from typing import Dict, List, Optional, Sequence, Union


@dataclass(frozen=True)
class Point:
    x: int
    y: int


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    width: int
    height: int

    def random_point(self, rnd: Random) -> Point:
        return Point(
            x=rnd.randint(self.x, self.x + max(1, self.width) - 1),
            y=rnd.randint(self.y, self.y + max(1, self.height) - 1),
        )


@dataclass(frozen=True)
class DelayRange:
    min_ms: int
    max_ms: int

    def __post_init__(self) -> None:
        if not (10 <= self.min_ms <= 5000 and 10 <= self.max_ms <= 5000):
            raise ValueError('Delay range must be within 10..5000 ms')
        if self.min_ms > self.max_ms:
            raise ValueError('min_ms must be <= max_ms')

    def sample(self, rnd: Random) -> int:
        return rnd.randint(self.min_ms, self.max_ms)


@dataclass(frozen=True)
class TemplateMatch:
    stage_id: str
    confidence: float
    matched_region: Rect


@dataclass(frozen=True)
class FrameSnapshot:
    timestamp_ms: int
    matches_by_stage: Dict[str, TemplateMatch]


class ScrollDirection(str, Enum):
    UP = 'UP'
    DOWN = 'DOWN'
    LEFT = 'LEFT'
    RIGHT = 'RIGHT'


@dataclass(frozen=True)
class TemplateTapStage:
    id: str
    timeout_ms: int
    search_region: Rect
    delay_before_tap: DelayRange
    click_jitter_px: int
    threshold: float
    stable_frames_required: int = 1


@dataclass(frozen=True)
class ScrollStage:
    id: str
    timeout_ms: int
    region: Rect
    direction: ScrollDirection
    distance_px_min: int
    distance_px_max: int
    duration_ms_min: int
    duration_ms_max: int


Stage = Union[TemplateTapStage, ScrollStage]


@dataclass(frozen=True)
class Scenario:
    id: str
    name: str
    stages: Sequence[Stage]
    enabled: bool = True
    priority: int = 100


class EngineEvent(str, Enum):
    SCENARIO_ACTIVATED = 'SCENARIO_ACTIVATED'
    TAP_SCHEDULED = 'TAP_SCHEDULED'
    SCROLL_SCHEDULED = 'SCROLL_SCHEDULED'
    STAGE_COMPLETED = 'STAGE_COMPLETED'
    SCENARIO_COMPLETED = 'SCENARIO_COMPLETED'
    SCENARIO_TIMEOUT = 'SCENARIO_TIMEOUT'


@dataclass
class EventRecord:
    event: EngineEvent
    scenario_id: str
    stage_id: Optional[str] = None
    payload: Optional[dict] = None


class ScenarioEngine:
    """Core arbitration engine: one active scenario at a time."""

    def __init__(self, scenarios: Sequence[Scenario], rnd_seed: int = 42) -> None:
        self._scenarios = sorted([s for s in scenarios if s.enabled], key=lambda s: s.priority)
        self._rnd = Random(rnd_seed)
        self._active_scenario: Optional[Scenario] = None
        self._active_stage_idx: int = 0
        self._stage_start_ms: int = 0
        self._stable_hits: Dict[str, int] = {}

    @property
    def active_scenario_id(self) -> Optional[str]:
        return self._active_scenario.id if self._active_scenario else None

    def process(self, frame: FrameSnapshot) -> List[EventRecord]:
        if self._active_scenario is None:
            return self._try_activate(frame)
        return self._process_active(frame)

    def _try_activate(self, frame: FrameSnapshot) -> List[EventRecord]:
        for scenario in self._scenarios:
            first = scenario.stages[0]
            if isinstance(first, TemplateTapStage) and self._is_match(frame, first):
                self._active_scenario = scenario
                self._active_stage_idx = 0
                self._stage_start_ms = frame.timestamp_ms
                self._stable_hits.clear()
                return [EventRecord(EngineEvent.SCENARIO_ACTIVATED, scenario.id)]
        return []

    def _process_active(self, frame: FrameSnapshot) -> List[EventRecord]:
        assert self._active_scenario is not None
        stage = self._active_scenario.stages[self._active_stage_idx]

        if frame.timestamp_ms - self._stage_start_ms > stage.timeout_ms:
            sid = self._active_scenario.id
            stid = stage.id
            self._reset()
            return [EventRecord(EngineEvent.SCENARIO_TIMEOUT, sid, stid)]

        if isinstance(stage, TemplateTapStage):
            return self._process_tap_stage(frame, stage)
        return self._process_scroll_stage(frame, stage)

    def _process_tap_stage(self, frame: FrameSnapshot, stage: TemplateTapStage) -> List[EventRecord]:
        if not self._is_match(frame, stage):
            return []

        match = frame.matches_by_stage[stage.id]
        cx = match.matched_region.x + match.matched_region.width // 2
        cy = match.matched_region.y + match.matched_region.height // 2
        dx = self._rnd.randint(-stage.click_jitter_px, stage.click_jitter_px)
        dy = self._rnd.randint(-stage.click_jitter_px, stage.click_jitter_px)
        px = min(max(cx + dx, stage.search_region.x), stage.search_region.x + stage.search_region.width - 1)
        py = min(max(cy + dy, stage.search_region.y), stage.search_region.y + stage.search_region.height - 1)

        payload = {'point': Point(px, py), 'delay_ms': stage.delay_before_tap.sample(self._rnd)}
        return self._advance(
            frame.timestamp_ms,
            EventRecord(EngineEvent.TAP_SCHEDULED, self._active_scenario.id, stage.id, payload),
        )

    def _process_scroll_stage(self, frame: FrameSnapshot, stage: ScrollStage) -> List[EventRecord]:
        start = stage.region.random_point(self._rnd)
        dist = self._rnd.randint(stage.distance_px_min, stage.distance_px_max)

        if stage.direction == ScrollDirection.UP:
            end = Point(start.x, max(stage.region.y, start.y - dist))
        elif stage.direction == ScrollDirection.DOWN:
            end = Point(start.x, min(stage.region.y + stage.region.height - 1, start.y + dist))
        elif stage.direction == ScrollDirection.LEFT:
            end = Point(max(stage.region.x, start.x - dist), start.y)
        else:
            end = Point(min(stage.region.x + stage.region.width - 1, start.x + dist), start.y)

        payload = {
            'from': start,
            'to': end,
            'duration_ms': self._rnd.randint(stage.duration_ms_min, stage.duration_ms_max),
        }
        return self._advance(
            frame.timestamp_ms,
            EventRecord(EngineEvent.SCROLL_SCHEDULED, self._active_scenario.id, stage.id, payload),
        )

    def _advance(self, timestamp_ms: int, action_event: EventRecord) -> List[EventRecord]:
        assert self._active_scenario is not None
        stage = self._active_scenario.stages[self._active_stage_idx]
        events = [
            EventRecord(EngineEvent.STAGE_COMPLETED, self._active_scenario.id, stage.id),
            action_event,
        ]
        if self._active_stage_idx >= len(self._active_scenario.stages) - 1:
            events.append(EventRecord(EngineEvent.SCENARIO_COMPLETED, self._active_scenario.id))
            self._reset()
        else:
            self._active_stage_idx += 1
            self._stage_start_ms = timestamp_ms
            self._stable_hits.clear()
        return events

    def _is_match(self, frame: FrameSnapshot, stage: TemplateTapStage) -> bool:
        match = frame.matches_by_stage.get(stage.id)
        if match is None or match.confidence < stage.threshold:
            self._stable_hits[stage.id] = 0
            return False

        current = self._stable_hits.get(stage.id, 0) + 1
        self._stable_hits[stage.id] = current
        return current >= stage.stable_frames_required

    def _reset(self) -> None:
        self._active_scenario = None
        self._active_stage_idx = 0
        self._stage_start_ms = 0
        self._stable_hits.clear()

from overlay_engine.engine import (
    DelayRange,
    EngineEvent,
    FrameSnapshot,
    Rect,
    Scenario,
    ScenarioEngine,
    ScrollDirection,
    ScrollStage,
    TemplateMatch,
    TemplateTapStage,
)


def test_single_active_scenario_and_completion():
    s1 = Scenario(
        id='s1',
        name='Primary',
        priority=1,
        stages=[
            TemplateTapStage(
                id='s1-1',
                timeout_ms=1000,
                search_region=Rect(0, 0, 500, 500),
                delay_before_tap=DelayRange(10, 40),
                click_jitter_px=5,
                threshold=0.8,
            ),
            ScrollStage(
                id='s1-2',
                timeout_ms=1000,
                region=Rect(0, 0, 500, 500),
                direction=ScrollDirection.UP,
                distance_px_min=10,
                distance_px_max=40,
                duration_ms_min=100,
                duration_ms_max=200,
            ),
        ],
    )

    s2 = Scenario(
        id='s2',
        name='Secondary',
        priority=2,
        stages=[
            TemplateTapStage(
                id='s2-1',
                timeout_ms=1000,
                search_region=Rect(0, 0, 500, 500),
                delay_before_tap=DelayRange(10, 40),
                click_jitter_px=5,
                threshold=0.8,
            )
        ],
    )

    engine = ScenarioEngine([s1, s2], rnd_seed=1)

    activation = engine.process(
        FrameSnapshot(
            timestamp_ms=100,
            matches_by_stage={
                's1-1': TemplateMatch('s1-1', 0.92, Rect(100, 100, 60, 30)),
                's2-1': TemplateMatch('s2-1', 0.95, Rect(200, 200, 60, 30)),
            },
        )
    )
    assert activation[0].event == EngineEvent.SCENARIO_ACTIVATED
    assert activation[0].scenario_id == 's1'

    stage1 = engine.process(
        FrameSnapshot(
            timestamp_ms=150,
            matches_by_stage={'s1-1': TemplateMatch('s1-1', 0.9, Rect(100, 100, 60, 30))},
        )
    )
    assert [e.event for e in stage1] == [EngineEvent.STAGE_COMPLETED, EngineEvent.TAP_SCHEDULED]

    stage2 = engine.process(FrameSnapshot(timestamp_ms=200, matches_by_stage={}))
    assert [e.event for e in stage2] == [
        EngineEvent.STAGE_COMPLETED,
        EngineEvent.SCROLL_SCHEDULED,
        EngineEvent.SCENARIO_COMPLETED,
    ]
    assert engine.active_scenario_id is None


def test_timeout_resets_engine_to_idle():
    s1 = Scenario(
        id='s1',
        name='Timeout',
        stages=[
            TemplateTapStage(
                id='a',
                timeout_ms=50,
                search_region=Rect(0, 0, 300, 300),
                delay_before_tap=DelayRange(10, 30),
                click_jitter_px=3,
                threshold=0.7,
            ),
            TemplateTapStage(
                id='b',
                timeout_ms=50,
                search_region=Rect(0, 0, 300, 300),
                delay_before_tap=DelayRange(10, 30),
                click_jitter_px=3,
                threshold=0.7,
            ),
        ],
    )
    engine = ScenarioEngine([s1], rnd_seed=2)

    engine.process(
        FrameSnapshot(
            timestamp_ms=10,
            matches_by_stage={'a': TemplateMatch('a', 0.9, Rect(10, 10, 20, 20))},
        )
    )
    engine.process(
        FrameSnapshot(
            timestamp_ms=20,
            matches_by_stage={'a': TemplateMatch('a', 0.91, Rect(10, 10, 20, 20))},
        )
    )

    timeout = engine.process(FrameSnapshot(timestamp_ms=80, matches_by_stage={}))
    assert timeout[0].event == EngineEvent.SCENARIO_TIMEOUT
    assert timeout[0].stage_id == 'b'
    assert engine.active_scenario_id is None

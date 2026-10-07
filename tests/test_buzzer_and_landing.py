"""
Tests for buzzer logic and landing state machine transitions.
"""

import threading
import time
import unittest
from unittest.mock import MagicMock, patch

from payload.constants import (
    BUZZER_PIN,
    GROUND_ALTITUDE_METERS,
    LANDED_ACCELERATION_METERS_PER_SECOND_SQUARED,
    MAX_FREE_FALL_SECONDS,
)
from payload.state import FreeFallState, LandedState


class DummyDataProcessor:
    def __init__(self):
        self.current_altitude = 100.0
        self.average_vertical_acceleration = 0.0
        self.current_timestamp_seconds = 10.0


class DummyContext:
    def __init__(self):
        self.data_processor = DummyDataProcessor()
        self.state = None
        self.logger = MagicMock()
        self.logger.is_log_buffer_full = False
        self.stop_called = False

    def start(self):
        pass

    def stop(self):
        self.stop_called = True

    def update(self):
        pass


class MockBuzzerDevice:
    def __init__(self):
        self.on_calls = 0
        self.off_calls = 0
        self.close_calls = 0

    def on(self):
        self.on_calls += 1

    def off(self):
        self.off_calls += 1

    def close(self):
        self.close_calls += 1


class TestFreeFallState(unittest.TestCase):
    def setUp(self):
        self.context = DummyContext()
        self.state = FreeFallState(self.context)
        self.context.state = self.state

    def test_no_transition_while_falling(self):
        # Altitude is high, acceleration is normal
        self.context.data_processor.current_altitude = 50.0
        self.context.data_processor.average_vertical_acceleration = 9.81
        self.context.data_processor.current_timestamp_seconds = 20.0

        self.state.update()
        self.assertIsInstance(self.context.state, FreeFallState)

    def test_transition_on_impact_spike(self):
        # Near ground and impact acceleration spike
        self.context.data_processor.current_altitude = GROUND_ALTITUDE_METERS - 1.0
        self.context.data_processor.average_vertical_acceleration = (
            LANDED_ACCELERATION_METERS_PER_SECOND_SQUARED + 5.0
        )

        self.state.update()
        self.assertIsInstance(self.context.state, LandedState)
        # Clean up spawned buzzer thread
        self.context.state.stop()

    def test_transition_on_free_fall_timeout(self):
        # Soft landing where impact spike was missed or altitude didn't zero perfectly
        self.context.data_processor.current_altitude = 25.0
        self.context.data_processor.average_vertical_acceleration = 5.0
        self.context.data_processor.current_timestamp_seconds = (
            self.state._start_timestamp_seconds + MAX_FREE_FALL_SECONDS + 1.0
        )

        self.state.update()
        self.assertIsInstance(self.context.state, LandedState)
        # Clean up spawned buzzer thread
        self.context.state.stop()


class TestLandedState(unittest.TestCase):
    def setUp(self):
        self.context = DummyContext()

    def test_buzzer_pin_configuration(self):
        self.assertEqual(BUZZER_PIN, 26)
        self.assertEqual(LandedState._BUZZER_PIN, 26)

    def test_buzzer_beacon_toggles_and_cleans_up(self):
        mock_buzzer = MockBuzzerDevice()
        # Use a very short duration for test speed
        state = LandedState(self.context, buzzer=mock_buzzer, duration_seconds=0.05)
        self.context.state = state

        # Wait for thread to finish
        state._buzzer_thread.join(timeout=2.0)
        self.assertFalse(state._buzzer_thread.is_alive())

        self.assertGreater(mock_buzzer.on_calls, 0)
        self.assertGreater(mock_buzzer.off_calls, 0)
        self.assertEqual(mock_buzzer.close_calls, 1)

    def test_buzzer_stops_immediately_on_stop_call(self):
        mock_buzzer = MockBuzzerDevice()
        # 10 minutes duration
        state = LandedState(self.context, buzzer=mock_buzzer, duration_seconds=600.0)
        self.context.state = state

        self.assertTrue(state._buzzer_thread.is_alive())

        # Calling stop should terminate the thread within ~100ms instead of 600s
        start = time.monotonic()
        state.stop()
        state._buzzer_thread.join(timeout=1.0)
        elapsed = time.monotonic() - start

        self.assertFalse(state._buzzer_thread.is_alive())
        self.assertLess(elapsed, 0.9)
        self.assertEqual(mock_buzzer.close_calls, 1)

    def test_graceful_fallback_without_gpio(self):
        # When gpiozero is unavailable or fails to initialize
        with patch.object(LandedState, "_init_buzzer", return_value=None):
            state = LandedState(self.context, duration_seconds=0.05)
            self.assertIsNone(state._buzzer_device)
            state._buzzer_thread.join(timeout=2.0)
            self.assertFalse(state._buzzer_thread.is_alive())

    def test_init_buzzer_catches_hardware_exception(self):
        # Simulate gpiozero throwing an exception during pin initialization
        with patch("sys.modules", {"gpiozero": MagicMock(Buzzer=MagicMock(side_effect=RuntimeError("Pin in use")))}):
            state = LandedState(self.context, duration_seconds=0.05)
            self.assertIsNone(state._buzzer_device)
            state.stop()

    def test_landed_state_update_calls_stop_when_buffer_full(self):
        mock_buzzer = MockBuzzerDevice()
        state = LandedState(self.context, buzzer=mock_buzzer, duration_seconds=600.0)
        self.context.logger.is_log_buffer_full = True

        state.update()
        self.assertTrue(self.context.stop_called)
        state.stop()

    def test_keyboard_interrupt_stops_landed_state(self):
        numpy_mock = MagicMock()
        numpy_mock.typing = MagicMock()
        with patch.dict(
            "sys.modules",
            {
                "msgspec": MagicMock(),
                "firm_client": MagicMock(),
                "polars": MagicMock(),
                "colorama": MagicMock(),
                "numpy": numpy_mock,
                "numpy.typing": numpy_mock.typing,
            },
        ):
            from payload.main import run_flight_loop

            mock_buzzer = MockBuzzerDevice()
            mock_state = LandedState(self.context, buzzer=mock_buzzer, duration_seconds=600.0)
            self.context.state = mock_state

            mock_display = MagicMock()
            # Simulate KeyboardInterrupt on the first update call
            with patch.object(self.context, "update", side_effect=KeyboardInterrupt):
                run_flight_loop(self.context, mock_display)

            # Ensure stop was called on mock_state
            self.assertTrue(mock_state._stop_event.is_set())
            mock_state._buzzer_thread.join(timeout=1.0)
            self.assertFalse(mock_state._buzzer_thread.is_alive())



if __name__ == "__main__":
    unittest.main()


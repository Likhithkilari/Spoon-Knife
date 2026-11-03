
"""Bridge UDP telemetry and SDN flow statistics to NetworkDetector.

This module deliberately does not implement a UDP server or an SDN controller.
Member 2's UDP server and Member 1's SDN statistics collector should call the
appropriate methods on MonitoringPipeline when they receive new data.
"""

from collections.abc import Callable, Mapping
from typing import Any, Optional

from monitoring.detector import NetworkDetector


AlertCallback = Callable[[dict[str, Any]], None]


class MonitoringPipeline:
    """Small integration layer around the team's existing NetworkDetector.

    Expected flow-statistics fields:
        switch, flow_id, byte_count, packet_count, timestamp

    Expected telemetry fields:
        host, timestamp, bytes_sent, packets_sent
    """

    def __init__(
        self,
        detector: Optional[NetworkDetector] = None,
        on_alert: Optional[AlertCallback] = None,
    ) -> None:
        self.detector = detector or NetworkDetector()
        self.on_alert = on_alert

    def handle_flow_stats(
        self, stats: Mapping[str, Any]
    ) -> list[dict[str, Any]]:
        """Pass one cumulative SDN flow-counter sample to the detector."""
        self._require_fields(
            stats,
            ("switch", "flow_id", "byte_count", "packet_count", "timestamp"),
            "SDN flow statistics",
        )
        alerts = self.detector.process_flow_stats(dict(stats))
        return self._publish(alerts)

    def handle_telemetry(
        self, telemetry: Mapping[str, Any]
    ) -> list[dict[str, Any]]:
        """Pass one host telemetry message received by the UDP server."""
        self._require_fields(
            telemetry,
            ("host", "timestamp", "bytes_sent", "packets_sent"),
            "UDP host telemetry",
        )
        alerts = self.detector.process_telemetry(dict(telemetry))
        return self._publish(alerts)

    def check_stale_flows(
        self, now: Optional[float] = None
    ) -> list[dict[str, Any]]:
        """Ask the detector to identify flows whose samples have gone stale."""
        if now is None:
            alerts = self.detector.find_stale_flows()
        else:
            alerts = self.detector.find_stale_flows(now=now)

        return self._publish(alerts)

    def _publish(self, alerts: Any) -> list[dict[str, Any]]:
        """Normalize detector output and optionally forward each alert."""
        if alerts is None:
            result: list[dict[str, Any]] = []
        elif isinstance(alerts, dict):
            result = [alerts]
        else:
            result = list(alerts)

        if self.on_alert is not None:
            for alert in result:
                self.on_alert(alert)

        return result

    @staticmethod
    def _require_fields(
        data: Mapping[str, Any],
        required: tuple[str, ...],
        description: str,
    ) -> None:
        missing = [field for field in required if field not in data]

        if missing:
            raise ValueError(
                f"{description} is missing required field(s): "
                f"{', '.join(missing)}"
            )

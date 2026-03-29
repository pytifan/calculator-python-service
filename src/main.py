"""
Oil & Gas Well Completion Calculator Service
Python gRPC service for physics-based well completion simulation.
"""

import grpc
import http.server
import threading
import time
from concurrent import futures
import logging

from well_calculator import WellCompletionCalculator, WellParameters, WellProgressStep, WellCompletionResult

# Generated from calculation.proto
import calculation_pb2
import calculation_pb2_grpc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Unit conversion constants
M3_TO_BBL = 6.28981
M3_TO_GAL = 264.172


# ============================================================================
# gRPC SERVICE IMPLEMENTATION
# ============================================================================

class CalculationServiceServicer(calculation_pb2_grpc.CalculationServiceServicer):
    """
    gRPC service implementation.
    Implements CalculationService with server-streaming Calculate RPC.
    """

    def __init__(self):
        self.well_calculator = WellCompletionCalculator()

    def _progress(self, calculation_id: str, pct: int, phase: str,
                  iteration: int = 0, metric: float = 0.0, message: str = "") -> calculation_pb2.CalculationUpdate:
        return calculation_pb2.CalculationUpdate(
            calculation_id=calculation_id,
            progress=calculation_pb2.Progress(
                percentage=pct,
                phase=phase,
                iteration=iteration,
                convergence_metric=metric,
                message=message
            )
        )

    def Calculate(self, request, context):
        """
        Server-streaming RPC: Calculate.
        Routes to WellCompletionCalculator when well_params are present.
        """
        calc_id = request.calculation_id
        logger.info(f"Received Calculate request: {calc_id}")

        if request.HasField("well_params") and request.well_params.tubing_length_m > 0:
            yield from self._calculate_well_completion(calc_id, request)
        else:
            yield calculation_pb2.CalculationUpdate(
                calculation_id=calc_id,
                error=calculation_pb2.Error(
                    error_code="INVALID_REQUEST",
                    error_message="Well parameters are required"
                )
            )

    def _calculate_well_completion(self, calc_id: str, request):
        """
        Handle well completion calculation using WellCompletionCalculator.
        Yields gRPC CalculationUpdate stream messages.
        """
        wp = request.well_params
        params = WellParameters(
            tubing_length_m=wp.tubing_length_m,
            tubing_od_mm=wp.tubing_od_mm,
            tubing_wall_mm=wp.tubing_wall_mm,
            casing_od_mm=wp.casing_od_mm,
            casing_wall_mm=wp.casing_wall_mm,
            fluid_density_kg_m3=wp.fluid_density_kg_m3 if wp.fluid_density_kg_m3 > 0 else 1020.0,
            gravity_m_s2=wp.gravity_m_s2 if wp.gravity_m_s2 > 0 else 9.81,
            initial_water_level_m=wp.initial_water_level_m,
            surface_pressure_pa=wp.surface_pressure_pa if wp.surface_pressure_pa > 0 else 1e5,
            max_wellhead_pressure_pa=wp.max_wellhead_pressure_pa if wp.max_wellhead_pressure_pa > 0 else 200e5,
            min_wellhead_pressure_pa=wp.min_wellhead_pressure_pa if wp.min_wellhead_pressure_pa > 0 else 100e5,
        )

        logger.info(f"Starting well completion calculation: {calc_id}, L={params.tubing_length_m}m")

        start_time = time.time()
        final_result = None

        try:
            for step in self.well_calculator.calculate(params):
                if isinstance(step, WellProgressStep):
                    yield calculation_pb2.CalculationUpdate(
                        calculation_id=calc_id,
                        progress=calculation_pb2.Progress(
                            percentage=step.percentage,
                            phase=step.phase,
                            message=step.message,
                            volume_pumped_m3=step.volume_pumped_m3,
                            annulus_front_m=step.annulus_front_m,
                            tubing_front_m=step.tubing_front_m,
                            wellhead_pressure_pa=step.wellhead_pressure_pa,
                            bottom_pressure_pa=step.bottom_pressure_pa,
                        )
                    )
                elif isinstance(step, WellCompletionResult):
                    final_result = step

        except Exception as e:
            logger.error(f"Well completion calculation failed for {calc_id}: {e}", exc_info=True)
            yield calculation_pb2.CalculationUpdate(
                calculation_id=calc_id,
                error=calculation_pb2.Error(
                    error_code="WELL_CALC_FAILED",
                    error_message=str(e)
                )
            )
            return

        if final_result is None:
            yield calculation_pb2.CalculationUpdate(
                calculation_id=calc_id,
                error=calculation_pb2.Error(
                    error_code="NO_RESULT",
                    error_message="Calculation produced no result"
                )
            )
            return

        elapsed_ms = int((time.time() - start_time) * 1000)

        unit_system = request.options.unit_system or "metric"
        volumes = [
            calculation_pb2.VolumeRequirement(
                fluid_type="completion_fluid_annulus",
                volume_m3=final_result.new_fluid_in_annulus_m3,
                volume_bbl=final_result.new_fluid_in_annulus_m3 * M3_TO_BBL,
                volume_gal=final_result.new_fluid_in_annulus_m3 * M3_TO_GAL,
                calculation_basis=f"Annulus: {final_result.annulus_cross_section_m2*1e4:.2f} cm² × {params.tubing_length_m:.0f} m",
            ),
            calculation_pb2.VolumeRequirement(
                fluid_type="completion_fluid_tubing",
                volume_m3=final_result.new_fluid_in_tubing_m3,
                volume_bbl=final_result.new_fluid_in_tubing_m3 * M3_TO_BBL,
                volume_gal=final_result.new_fluid_in_tubing_m3 * M3_TO_GAL,
                calculation_basis=f"Tubing: {final_result.tubing_cross_section_m2*1e4:.2f} cm² × {params.tubing_length_m:.0f} m",
            ),
        ]

        metadata = calculation_pb2.CalculationMetadata(
            algorithm_used="well_completion_displacement",
            iterations=WellCompletionCalculator.NUM_STEPS,
            final_convergence=0.0,
            elapsed_ms=elapsed_ms,
            converged=True,
            unit_system=unit_system,
        )

        logger.info(
            f"Well completion done: {calc_id}, total={final_result.total_pumped_m3:.1f}m³, "
            f"elapsed={elapsed_ms}ms"
        )

        yield calculation_pb2.CalculationUpdate(
            calculation_id=calc_id,
            result=calculation_pb2.CalculationResult(
                volumes=volumes,
                metadata=metadata,
            )
        )

    def HealthCheck(self, request, context):
        return calculation_pb2.HealthResponse(
            status="SERVING",
            version="1.0.0",
            service="calculator-python-service"
        )


# ============================================================================
# HTTP HEALTH ENDPOINT (for Docker healthcheck)
# ============================================================================

def _run_health_http_server(port: int = 8000):
    """Minimal HTTP server for Docker healthcheck on port 8000."""

    class HealthHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/health':
                body = b'{"status":"UP"}'
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, fmt, *args):
            pass  # suppress access logs

    httpd = http.server.HTTPServer(('', port), HealthHandler)
    httpd.serve_forever()


# ============================================================================
# SERVER STARTUP
# ============================================================================

def serve(grpc_port: int = 50051, health_port: int = 8000):
    """Start gRPC server and HTTP health endpoint."""

    # Start HTTP health server in background daemon thread
    health_thread = threading.Thread(
        target=_run_health_http_server,
        args=(health_port,),
        daemon=True,
        name="http-health"
    )
    health_thread.start()
    logger.info(f"HTTP health endpoint started on port {health_port}")

    # Start gRPC server
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    calculation_pb2_grpc.add_CalculationServiceServicer_to_server(
        CalculationServiceServicer(),
        server
    )

    server.add_insecure_port(f'[::]:{grpc_port}')
    server.start()

    logger.info(f"Oil & Gas Well Completion Calculator Service started on port {grpc_port}")
    print(f"gRPC server listening on port {grpc_port}")
    print(f"HTTP health endpoint on port {health_port}")

    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
        server.stop(0)


if __name__ == '__main__':
    serve()

"""
Oil & Gas Liquid Volume Calculator Service
Python gRPC service for non-linear equation solving
"""

import ast
import grpc
import http.server
import threading
import time
from concurrent import futures
import logging
from dataclasses import dataclass
from typing import List, Callable

import numpy as np
from scipy.optimize import fsolve, root

# Generated from calculation.proto
import calculation_pb2
import calculation_pb2_grpc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Unit conversion constants
M3_TO_BBL = 6.28981
M3_TO_GAL = 264.172

# Python built-ins / math names that are NOT variable names
_EXCLUDED_NAMES = frozenset(dir(__builtins__) if isinstance(__builtins__, dict) else dir(__builtins__)) | {
    'abs', 'sqrt', 'sin', 'cos', 'tan', 'exp', 'log', 'pi', 'e',
    'True', 'False', 'None'
}


def extract_variable_names(equations: List[str]) -> List[str]:
    """
    Extract unique variable names used in equations by parsing the AST.
    Names that appear in the equations (in order of first appearance) that
    are not Python built-ins are treated as variables.
    """
    seen = []
    seen_set = set()
    for eq in equations:
        try:
            tree = ast.parse(eq, mode='eval')
            for node in ast.walk(tree):
                if isinstance(node, ast.Name) and node.id not in _EXCLUDED_NAMES:
                    if node.id not in seen_set:
                        seen_set.add(node.id)
                        seen.append(node.id)
        except SyntaxError:
            pass
    return seen


# ============================================================================
# DOMAIN MODEL (Think of this like Java @Data classes, but Python dataclass)
# ============================================================================

@dataclass
class EquationSystem:
    """Represents a system of non-linear equations to solve"""
    equations: List[str]  # Python code strings like "x**2 + y**2 - 1"
    initial_guess: List[float]
    variable_names: List[str]

    def compile_equations(self) -> Callable:
        """
        Compile equation strings to callable function
        Analogy: Like Java's Function<Double[], Double[]> interface

        Returns a function: f(vars) -> [equation_values]
        """
        compiled_eqs = [compile(eq, '<string>', 'eval') for eq in self.equations]

        def system_function(variables):
            # Create variable namespace: {x: val1, y: val2, ...}
            namespace = {
                name: val
                for name, val in zip(self.variable_names, variables)
            }
            namespace.update({'__builtins__': {}})  # Security: no built-ins

            # Evaluate all equations
            return [
                eval(compiled_eq, namespace, {})
                for compiled_eq in compiled_eqs
            ]

        return system_function


@dataclass
class SolutionResult:
    """Result of solving an equation system"""
    variables: List[float]
    convergence_iterations: int
    residual: float
    success: bool
    message: str
    variable_names: List[str]


# ============================================================================
# SOLVER REPOSITORY (Strategy pattern for different solvers)
# ============================================================================

class EquationSolver:
    """
    Abstraction for equation solving strategies
    Analogy: Like a Java interface with multiple implementations
    """

    @staticmethod
    def solve_fsolve(system: EquationSystem) -> SolutionResult:
        """SciPy's fsolve - robust and fast for most cases"""
        try:
            system_func = system.compile_equations()
            solution = fsolve(
                system_func,
                system.initial_guess,
                full_output=True,
                xtol=1e-9
            )
            variables, info, ier, msg = solution
            return SolutionResult(
                variables=variables.tolist(),
                convergence_iterations=info['nfev'],
                residual=float(np.linalg.norm(info['fvec'])),
                success=(ier == 1),
                message=msg,
                variable_names=system.variable_names
            )
        except Exception as e:
            logger.error(f"fsolve failed: {e}")
            return SolutionResult([], 0, float('inf'), False, str(e), system.variable_names)

    @staticmethod
    def solve_root_hybr(system: EquationSystem) -> SolutionResult:
        """SciPy's root() with hybr method - more robust for difficult systems"""
        try:
            system_func = system.compile_equations()
            result = root(system_func, system.initial_guess, method='hybr', options={'xtol': 1e-9})
            return SolutionResult(
                variables=result.x.tolist(),
                convergence_iterations=result.nfev,
                residual=float(np.linalg.norm(result.fun)),
                success=result.success,
                message=result.message,
                variable_names=system.variable_names
            )
        except Exception as e:
            logger.error(f"root(hybr) failed: {e}")
            return SolutionResult([], 0, float('inf'), False, str(e), system.variable_names)

    @staticmethod
    def solve_lm(system: EquationSystem) -> SolutionResult:
        """SciPy's root() with Levenberg-Marquardt - good for ill-conditioned systems"""
        try:
            system_func = system.compile_equations()
            result = root(system_func, system.initial_guess, method='lm', options={'xtol': 1e-9})
            return SolutionResult(
                variables=result.x.tolist(),
                convergence_iterations=result.nfev,
                residual=float(np.linalg.norm(result.fun)),
                success=result.success,
                message=result.message,
                variable_names=system.variable_names
            )
        except Exception as e:
            logger.error(f"root(lm) failed: {e}")
            return SolutionResult([], 0, float('inf'), False, str(e), system.variable_names)


# ============================================================================
# CALCULATOR SERVICE (Business logic orchestrator)
# ============================================================================

class VolumeCalculatorService:
    """Main service for volume calculations"""

    def __init__(self):
        self.solver = EquationSolver()

    def calculate_volume(
            self,
            equations: List[str],
            initial_guess: List[float],
            variable_names: List[str],
            method: str = "auto"
    ) -> SolutionResult:
        if len(equations) != len(variable_names):
            return SolutionResult([], 0, float('inf'), False,
                                  "Number of equations must match number of variables",
                                  variable_names)

        if len(initial_guess) != len(variable_names):
            return SolutionResult([], 0, float('inf'), False,
                                  "Initial guess size must match number of variables",
                                  variable_names)

        system = EquationSystem(
            equations=equations,
            initial_guess=initial_guess,
            variable_names=variable_names
        )

        logger.info(f"Solving system with method={method}: {equations}")

        if method == "fsolve":
            return self.solver.solve_fsolve(system)
        elif method == "hybr":
            return self.solver.solve_root_hybr(system)
        elif method == "lm":
            return self.solver.solve_lm(system)
        else:  # auto - try fsolve first, fallback to hybr
            result = self.solver.solve_fsolve(system)
            if not result.success:
                logger.info("fsolve failed, trying hybr method...")
                result = self.solver.solve_root_hybr(system)
            return result


# ============================================================================
# gRPC SERVICE IMPLEMENTATION
# ============================================================================

class CalculationServiceServicer(calculation_pb2_grpc.CalculationServiceServicer):
    """
    gRPC service implementation.
    Implements CalculationService with server-streaming Calculate RPC.
    """

    def __init__(self):
        self.calculator = VolumeCalculatorService()

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
        Streams progress updates then a final result (or error).
        """
        calc_id = request.calculation_id
        logger.info(f"Received Calculate request: {calc_id}")

        yield self._progress(calc_id, 5, "INITIALIZING", message="Parsing equations...")

        equations = list(request.equations)
        initial_params = list(request.initial_parameters)
        method = request.options.solver_method or "auto"
        unit_system = request.options.unit_system or "metric"

        # Extract variable names from the equation strings
        variable_names = extract_variable_names(equations)
        n = len(variable_names)

        if n == 0 or len(equations) == 0:
            yield calculation_pb2.CalculationUpdate(
                calculation_id=calc_id,
                error=calculation_pb2.Error(
                    error_code="INVALID_INPUT",
                    error_message="No equations provided or no variables detected"
                )
            )
            return

        # Pad/truncate initial_parameters to match the number of variables
        if len(initial_params) < n:
            initial_params.extend([1.0] * (n - len(initial_params)))
        elif len(initial_params) > n:
            initial_params = initial_params[:n]

        yield self._progress(calc_id, 20, "SETTING_UP",
                             message=f"Setting up {n}-equation system with variables: {variable_names}...")

        yield self._progress(calc_id, 50, "SOLVING",
                             message=f"Running solver (method={method})...")

        start_time = time.time()
        try:
            result = self.calculator.calculate_volume(
                equations=equations,
                initial_guess=initial_params,
                variable_names=variable_names,
                method=method
            )
        except Exception as e:
            logger.error(f"Solver exception for {calc_id}: {e}", exc_info=True)
            yield calculation_pb2.CalculationUpdate(
                calculation_id=calc_id,
                error=calculation_pb2.Error(
                    error_code="SOLVER_EXCEPTION",
                    error_message=str(e)
                )
            )
            return

        elapsed_ms = int((time.time() - start_time) * 1000)

        if not result.success:
            logger.warning(f"Solver did not converge for {calc_id}: {result.message}")
            yield calculation_pb2.CalculationUpdate(
                calculation_id=calc_id,
                error=calculation_pb2.Error(
                    error_code="SOLVER_NOT_CONVERGED",
                    error_message=result.message
                )
            )
            return

        yield self._progress(calc_id, 90, "FINALIZING",
                             iteration=result.convergence_iterations,
                             metric=result.residual,
                             message="Computing volume requirements...")

        # Convert solution variables to VolumeRequirements
        # Each solution variable represents a fluid volume in m³
        well_config = request.well_config
        fluid_type = well_config.fluid_type if well_config.fluid_type else "fluid"

        volumes = []
        for i, v in enumerate(result.variables):
            volume_m3 = abs(v)
            fluid_label = f"{fluid_type}_{variable_names[i]}" if n > 1 else fluid_type
            volumes.append(calculation_pb2.VolumeRequirement(
                fluid_type=fluid_label,
                volume_m3=volume_m3,
                volume_bbl=volume_m3 * M3_TO_BBL,
                volume_gal=volume_m3 * M3_TO_GAL,
                calculation_basis=f"Equation: {equations[i]}"
            ))

        metadata = calculation_pb2.CalculationMetadata(
            algorithm_used=method,
            iterations=result.convergence_iterations,
            final_convergence=result.residual,
            elapsed_ms=elapsed_ms,
            converged=result.success,
            unit_system=unit_system
        )

        logger.info(f"Calculation complete: {calc_id}, iterations={result.convergence_iterations}, "
                    f"residual={result.residual:.2e}, elapsed={elapsed_ms}ms")

        yield calculation_pb2.CalculationUpdate(
            calculation_id=calc_id,
            result=calculation_pb2.CalculationResult(
                volumes=volumes,
                metadata=metadata
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

    logger.info(f"Oil & Gas Volume Calculator Service started on port {grpc_port}")
    print(f"gRPC server listening on port {grpc_port}")
    print(f"HTTP health endpoint on port {health_port}")

    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
        server.stop(0)


if __name__ == '__main__':
    serve()

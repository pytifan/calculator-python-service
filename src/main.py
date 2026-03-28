"""
Oil & Gas Liquid Volume Calculator Service
Python gRPC service for non-linear equation solving
"""

import grpc
from concurrent import futures
import logging
from dataclasses import dataclass
from typing import List, Callable, Tuple
import numpy as np
from scipy.optimize import fsolve, root
import sys

# Generated from liquidvolume.proto
import calculation_pb2
import calculation_pb2_grpc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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
        """
        SciPy's fsolve - robust and fast for most cases
        Uses modified Powell method
        """
        try:
            system_func = system.compile_equations()

            # Main solver call
            solution = fsolve(
                system_func,
                system.initial_guess,
                full_output=True,
                xtol=1e-9
            )

            variables, info, ier, msg = solution

            return SolutionResult(
                variables=variables.tolist(),
                convergence_iterations=info['nfev'],  # Function evals = iterations
                residual=float(np.linalg.norm(info['fvec'])),
                success=(ier == 1),
                message=msg,
                variable_names=system.variable_names
            )
        except Exception as e:
            logger.error(f"fsolve failed: {e}")
            return SolutionResult(
                variables=[],
                convergence_iterations=0,
                residual=float('inf'),
                success=False,
                message=str(e),
                variable_names=system.variable_names
            )

    @staticmethod
    def solve_root_hybr(system: EquationSystem) -> SolutionResult:
        """
        SciPy's root() with hybr method - more robust for difficult systems
        Better for singular Jacobians
        """
        try:
            system_func = system.compile_equations()

            result = root(
                system_func,
                system.initial_guess,
                method='hybr',
                options={'xtol': 1e-9}
            )

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
            return SolutionResult(
                variables=[],
                convergence_iterations=0,
                residual=float('inf'),
                success=False,
                message=str(e),
                variable_names=system.variable_names
            )

    @staticmethod
    def solve_lm(system: EquationSystem) -> SolutionResult:
        """
        SciPy's root() with Levenberg-Marquardt - good for ill-conditioned systems
        Better for least-squares problems
        """
        try:
            system_func = system.compile_equations()

            result = root(
                system_func,
                system.initial_guess,
                method='lm',
                options={'xtol': 1e-9}
            )

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
            return SolutionResult(
                variables=[],
                convergence_iterations=0,
                residual=float('inf'),
                success=False,
                message=str(e),
                variable_names=system.variable_names
            )


# ============================================================================
# CALCULATOR SERVICE (Business logic orchestrator)
# ============================================================================

class VolumeCalculatorService:
    """
    Main service for volume calculations
    Analogy: Like a @Service bean in Spring - coordinates work
    """

    def __init__(self):
        self.solver = EquationSolver()

    def calculate_volume(
            self,
            equations: List[str],
            initial_guess: List[float],
            variable_names: List[str],
            method: str = "auto"
    ) -> SolutionResult:
        """
        Calculate liquid volume by solving equation system

        Args:
            equations: List of equation strings (e.g., ["x**2 + y**2 - 1", "x - y"])
            initial_guess: Starting point for solver
            variable_names: Names of variables (x, y, etc.)
            method: "auto", "fsolve", "hybr", "lm"

        Returns:
            SolutionResult with computed variables
        """

        # Validate inputs
        if len(equations) != len(variable_names):
            return SolutionResult(
                variables=[],
                convergence_iterations=0,
                residual=float('inf'),
                success=False,
                message="Number of equations must match number of variables",
                variable_names=variable_names
            )

        if len(initial_guess) != len(variable_names):
            return SolutionResult(
                variables=[],
                convergence_iterations=0,
                residual=float('inf'),
                success=False,
                message="Initial guess size must match number of variables",
                variable_names=variable_names
            )

        # Create system
        system = EquationSystem(
            equations=equations,
            initial_guess=initial_guess,
            variable_names=variable_names
        )

        # Choose solver strategy
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

class LiquidVolumeSolverServicer(calculation_pb2_grpc.LiquidVolumeSolverServicer):
    """
    gRPC service implementation
    Handles requests from SpringBoot gateway
    """

    def __init__(self):
        self.calculator = VolumeCalculatorService()

    def SolveVolumeEquations(self, request, context):
        """
        RPC method: SolveVolumeEquations

        Receives:
        - equations: list of equation strings
        - initialGuess: starting point
        - variableNames: x, y, z, etc.
        - solverMethod: "auto", "fsolve", "hybr", "lm"

        Returns: SolutionResponse with solution
        """
        try:
            logger.info(f"Received request for well: {request.wellId}")
            logger.debug(f"Equations: {request.equations}")
            logger.debug(f"Variable names: {request.variableNames}")
            logger.debug(f"Initial guess: {request.initialGuess}")
            logger.debug(f"Solver method: {request.solverMethod}")

            # Convert protobuf lists to Python lists
            equations = list(request.equations)
            initial_guess = list(request.initialGuess)
            variable_names = list(request.variableNames)
            method = request.solverMethod or "auto"

            # Validate inputs
            if len(equations) != len(variable_names):
                error_msg = f"Mismatch: {len(equations)} equations but {len(variable_names)} variable names"
                logger.error(error_msg)
                return calculation_pb2.SolutionResponse(
                    success=False,
                    message=error_msg
                )

            if len(initial_guess) != len(variable_names):
                error_msg = f"Mismatch: initial guess has {len(initial_guess)} values but {len(variable_names)} variable names"
                logger.error(error_msg)
                return calculation_pb2.SolutionResponse(
                    success=False,
                    message=error_msg
                )

            # Solve
            result = self.calculator.calculate_volume(
                equations=equations,
                initial_guess=initial_guess,
                variable_names=variable_names,
                method=method
            )

            logger.info(f"Solution found: {result.success}, "
                        f"iterations: {result.convergence_iterations}, "
                        f"residual: {result.residual}")

            # Convert to protobuf response
            return calculation_pb2.SolutionResponse(
                wellId=request.wellId,
                success=result.success,
                variables=result.variables,
                iterations=result.convergence_iterations,
                residual=result.residual,
                message=result.message
            )

        except Exception as e:
            logger.error(f"Error in SolveVolumeEquations: {e}", exc_info=True)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error: {str(e)}")
            return calculation_pb2.SolutionResponse(
                success=False,
                message=f"Error: {str(e)}"
            )

    def HealthCheck(self, request, context):
        """Simple health check endpoint"""
        return calculation_pb2.HealthCheckResponse(status="SERVING")


# ============================================================================
# SERVER STARTUP
# ============================================================================

def serve(port: int = 50051):
    """Start gRPC server"""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

    calculation_pb2_grpc.add_LiquidVolumeSolverServicer_to_server(
        LiquidVolumeSolverServicer(),
        server
    )

    server.add_insecure_port(f'[::]:{port}')
    server.start()

    logger.info(f"Oil & Gas Volume Calculator Service started on port {port}")
    print(f"🚀 gRPC server listening on port {port}")

    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
        server.stop(0)


if __name__ == '__main__':
    serve()
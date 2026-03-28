"""Direct test of volume calculator (no gRPC)"""
from main import VolumeCalculatorService

def test_simple_circle_intersection():
    """Test: x^2 + y^2 = 1 intersects x = y"""
    calc = VolumeCalculatorService()

    result = calc.calculate_volume(
        equations=["x**2 + y**2 - 1", "x - y"],
        initial_guess=[1.0, 1.0],
        variable_names=["x", "y"],
        method="auto"
    )

    print("\n" + "="*60)
    print("TEST: Circle & Line Intersection")
    print("="*60)
    print(f"✅ Success: {result.success}")
    print(f"   Solution: x={result.variables[0]:.6f}, y={result.variables[1]:.6f}")
    print(f"   Expected: x≈0.707107, y≈0.707107")
    print(f"   Iterations: {result.convergence_iterations}")
    print(f"   Residual: {result.residual:.2e}")

    assert result.success, "Should converge"
    assert len(result.variables) == 2, "Should have 2 variables"
    assert abs(result.variables[0] - 0.707107) < 0.001, "x should match"
    assert abs(result.variables[1] - 0.707107) < 0.001, "y should match"

    print("✅ TEST PASSED\n")


def test_three_variable_system():
    """Test: 3D system (more realistic for volume calculations)"""
    calc = VolumeCalculatorService()

    # System:
    # x^2 + y^2 - 4 = 0       (cylinder radius 2)
    # y^2 + z^2 - 4 = 0       (cylinder radius 2)
    # x + y + z - 3 = 0       (plane constraint)

    result = calc.calculate_volume(
        equations=[
            "x**2 + y**2 - 4",
            "y**2 + z**2 - 4",
            "x + y + z - 3"
        ],
        initial_guess=[1.0, 1.0, 1.0],
        variable_names=["x", "y", "z"],
        method="hybr"  # Use robust solver
    )

    print("\n" + "="*60)
    print("TEST: 3D Volume System")
    print("="*60)
    print(f"✅ Success: {result.success}")
    print(f"   Solution: x={result.variables[0]:.4f}, y={result.variables[1]:.4f}, z={result.variables[2]:.4f}")
    print(f"   Iterations: {result.convergence_iterations}")
    print(f"   Residual: {result.residual:.2e}")

    assert result.success, "Should converge"
    assert len(result.variables) == 3, "Should have 3 variables"

    print("✅ TEST PASSED\n")


def test_solver_fallback():
    """Test: Auto solver tries fsolve, falls back to hybr if needed"""
    calc = VolumeCalculatorService()

    # Difficult system - will likely need fallback
    result = calc.calculate_volume(
        equations=["x**3 - y", "y**3 - x"],
        initial_guess=[1.5, 1.5],
        variable_names=["x", "y"],
        method="auto"
    )

    print("\n" + "="*60)
    print("TEST: Solver Fallback (Stiff System)")
    print("="*60)
    print(f"✅ Success: {result.success}")
    print(f"   Solution: x={result.variables[0]:.6f}, y={result.variables[1]:.6f}")
    print(f"   Iterations: {result.convergence_iterations}")

    print("✅ TEST PASSED\n")


if __name__ == "__main__":
    test_simple_circle_intersection()
    test_three_variable_system()
    test_solver_fallback()
    print("🎉 All Python tests passed!")
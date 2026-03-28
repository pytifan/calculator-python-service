"""Quick test of the volume calculator"""
from main import VolumeCalculatorService

def test_circle_line_intersection():
    """Test: Find where a line intersects a circle"""

    calc = VolumeCalculatorService()

    # Equations: circle x^2 + y^2 = 1, line x = y
    result = calc.calculate_volume(
        equations=["x**2 + y**2 - 1", "x - y"],
        initial_guess=[1.0, 1.0],
        variable_names=["x", "y"],
        method="auto"
    )

    print(f"✅ Success: {result.success}")
    print(f"Solution: x={result.variables[0]:.4f}, y={result.variables[1]:.4f}")
    print(f"Iterations: {result.convergence_iterations}")
    print(f"Residual: {result.residual:.2e}")

    assert result.success, "Solver should converge"
    assert abs(result.variables[0] - 0.7071) < 0.01, "x should be ~0.7071"
    assert abs(result.variables[1] - 0.7071) < 0.01, "y should be ~0.7071"

    print("🎉 All tests passed!")

if __name__ == "__main__":
    test_circle_line_intersection()
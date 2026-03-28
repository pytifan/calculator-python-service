"""Test gRPC communication from Python client to Python server"""
import grpc
import calculation_pb2
import calculation_pb2_grpc


def test_grpc_health_check():
    """Simple health check - does server respond?"""
    print("\n" + "="*60)
    print("TEST: gRPC Health Check")
    print("="*60)

    try:
        with grpc.insecure_channel('localhost:50051') as channel:
            stub = calculation_pb2_grpc.CalculationServiceStub(channel)
            response = stub.HealthCheck(calculation_pb2.Empty())

            print(f"  Server Status: {response.status}")
            print(f"  Service: {response.service}")
            assert response.status == "SERVING"

    except Exception as e:
        print(f"ERROR: {e}")
        print("   Is Python service running on port 50051?")
        raise

    print("TEST PASSED\n")


def test_grpc_solve_equations():
    """Test actual equation solving via gRPC streaming"""
    print("\n" + "="*60)
    print("TEST: gRPC Calculate (streaming)")
    print("="*60)

    try:
        with grpc.insecure_channel('localhost:50051') as channel:
            stub = calculation_pb2_grpc.CalculationServiceStub(channel)

            request = calculation_pb2.CalculationRequest(
                calculation_id="TEST-001",
                equations=["x**2 + y**2 - 1", "x - y"],
                initial_parameters=[1.0, 1.0],
                options=calculation_pb2.CalculationOptions(
                    solver_method="auto",
                    max_iterations=1000,
                    tolerance=1e-8,
                    unit_system="metric"
                ),
                well_config=calculation_pb2.WellConfiguration(
                    well_name="Test Well",
                    fluid_type="fluid"
                )
            )

            result_received = False
            for update in stub.Calculate(request):
                if update.HasField("progress"):
                    p = update.progress
                    print(f"  Progress {p.percentage}% [{p.phase}] {p.message}")
                elif update.HasField("result"):
                    r = update.result
                    print(f"  Converged: {r.metadata.converged}")
                    print(f"  Iterations: {r.metadata.iterations}")
                    print(f"  Residual: {r.metadata.final_convergence:.2e}")
                    for v in r.volumes:
                        print(f"  Volume [{v.fluid_type}]: {v.volume_m3:.6f} m3 "
                              f"/ {v.volume_bbl:.4f} bbl / {v.volume_gal:.2f} gal")
                    assert r.metadata.converged, "Should converge"
                    assert len(r.volumes) == 2, "Should return 2 volumes"
                    result_received = True
                elif update.HasField("error"):
                    raise AssertionError(
                        f"gRPC error: {update.error.error_code} - {update.error.error_message}"
                    )

            assert result_received, "Should have received a result update"

    except grpc.RpcError as e:
        print(f"gRPC ERROR: {e.code()}")
        print(f"   Details: {e.details()}")
        raise

    print("TEST PASSED\n")


if __name__ == "__main__":
    test_grpc_health_check()
    test_grpc_solve_equations()
    print("All gRPC tests passed!")

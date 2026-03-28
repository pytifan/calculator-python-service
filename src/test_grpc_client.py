"""Test gRPC communication from Python client to Python server"""
import grpc
import liquidvolume_pb2
import liquidvolume_pb2_grpc

def test_grpc_health_check():
    """Simple health check - does server respond?"""
    print("\n" + "="*60)
    print("TEST: gRPC Health Check")
    print("="*60)

    try:
        # Connect to gRPC server
        with grpc.insecure_channel('localhost:50051') as channel:
            stub = liquidvolume_pb2_grpc.LiquidVolumeSolverStub(channel)

            # Health check
            response = stub.HealthCheck(liquidvolume_pb2.HealthCheckRequest())

            print(f"✅ Server Status: {response.status}")
            assert response.status == "SERVING"

    except Exception as e:
        print(f"❌ ERROR: {e}")
        print("   Is Python service running on port 50051?")
        raise

    print("✅ TEST PASSED\n")


def test_grpc_solve_equations():
    """Test actual equation solving via gRPC"""
    print("\n" + "="*60)
    print("TEST: gRPC Solve Equations RPC")
    print("="*60)

    try:
        with grpc.insecure_channel('localhost:50051') as channel:
            stub = liquidvolume_pb2_grpc.LiquidVolumeSolverStub(channel)

            # Create request
            request = liquidvolume_pb2.SolutionRequest(
                wellId="WELL-001",
                equations=["x**2 + y**2 - 1", "x - y"],
                variableNames=["x", "y"],
                initialGuess=[1.0, 1.0],
                solverMethod="auto"
            )

            # Call gRPC method
            response = stub.SolveVolumeEquations(request)

            print(f"✅ Well ID: {response.wellId}")
            print(f"✅ Success: {response.success}")
            print(f"   Solution: x={response.variables[0]:.6f}, y={response.variables[1]:.6f}")
            print(f"   Iterations: {response.iterations}")
            print(f"   Residual: {response.residual:.2e}")
            print(f"   Message: {response.message}")

            assert response.success, "Should solve successfully"
            assert response.wellId == "WELL-001", "Well ID should match"
            assert len(response.variables) == 2, "Should return 2 variables"

    except grpc.RpcError as e:
        print(f"❌ gRPC ERROR: {e.code()}")
        print(f"   Details: {e.details()}")
        raise

    print("✅ TEST PASSED\n")


if __name__ == "__main__":
    test_grpc_health_check()
    test_grpc_solve_equations()
    print("🎉 All gRPC tests passed!")
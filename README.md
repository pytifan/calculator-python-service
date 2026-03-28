# Python Calculator Service

Python gRPC service that solves systems of non-linear equations using NumPy and SciPy. Used by [calculations-gateway](https://github.com/pytifan/oil-and-gas) as the computation backend for Oil & Gas field calculations.

- **Transport**: gRPC on port `50051`
- **Proto**: `proto/calculation.proto` — service `LiquidVolumeSolver`
- **Solvers**: `fsolve`, `hybr` (Hybrid Powell), `lm` (Levenberg-Marquardt), `auto` (tries fsolve, falls back to hybr)

## Prerequisites

- Python 3.12+

## Setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Start the server

```bash
python src/main.py
```

Server starts on **`localhost:50051`** (plaintext gRPC).

## Verify it's running

Run the integration health check (server must be running, from the `src/` directory):

```bash
cd src
python test_grpc_client.py
```

Expected output ends with: `All gRPC tests passed!`

## Run tests

**Unit tests** — no server needed:

```bash
cd src
python test_service.py
python test_calculator.py
```

**Integration tests** — server must be running on `localhost:50051`:

```bash
cd src
python test_grpc_client.py
```

> `test_grpc_client.py` imports `liquidvolume_pb2`. If you regenerate the stubs (see below), ensure the output file name matches or update the import.

## Regenerate protobuf stubs

Run from the project root after any change to `proto/calculation.proto`:

```bash
python -m grpc_tools.protoc \
  -I./proto \
  --python_out=./src \
  --grpc_python_out=./src \
  ./proto/calculation.proto
```

This overwrites `src/calculation_pb2.py` and `src/calculation_pb2_grpc.py`.

## Solvers

| Method | When to use |
|---|---|
| `auto` | Default — tries `fsolve`, falls back to `hybr` on failure |
| `fsolve` | Fast, works for most well-conditioned systems |
| `hybr` | More robust for systems with singular Jacobians |
| `lm` | Levenberg-Marquardt — best for ill-conditioned / least-squares problems |

## Integration with calculations-gateway

The Spring Boot gateway connects to this service at `localhost:50051` by default (configured in `application.yml`):

```yaml
grpc:
  client:
    python-calculator:
      address: 'static://localhost:50051'
      negotiationType: plaintext
```

Start this service before starting the gateway, otherwise the gateway will apply circuit breaker / retry logic on every request until the service becomes available.

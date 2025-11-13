1.  python -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt

export MCP_JIRA_TOKEN="mock-jira-token"
export MODEL_ENDPOINT="http://vllm-openai:8000/v1"

uvicorn app.main:app --host 0.0.0.0 --port 8080

curl -s http://localhost:8080/health/alive
curl -s http://localhost:8080/health/ready

curl -s -X POST http://localhost:8080/execute \
 -H 'content-type: application/json' \
 -d '{"query":"hello"}'

docker build -t ai-agent:local .
docker run --rm -p 8080:8080 ai-agent:local
or
docker build -t ghcr.io/you/agents/orchestrator:1.0.0 .
docker push ghcr.io/you/agents/orchestrator:1.0.0

2.  python tools/preflight.py tools/preflight.yaml

3.  python tools/deploy.py tools/preflight.yaml

4.  Script:
    Optionally execute terraform apply
    Run helm upgrade --install
    Wait for rollout status
    Wait for /health/ready
    Run smoke POST /execute

or

Manually:

curl -s https://agents.example.com/health/ready
curl -s -X POST https://agents.example.com/execute \
 -H 'content-type: application/json' \
 -d '{"query":"ping"}'

curl -k -s http://agents.example.com/health/ready
curl -s -X POST http://agents.example.com/execute \
 -H 'content-type: application/json' \
 -d '{"query":"ping"}'

5. Should be installed:
   helm
   terraform
   oras
   kubectl

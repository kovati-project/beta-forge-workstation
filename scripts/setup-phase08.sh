#!/usr/bin/env bash
# Setup Phase 08: n8n workflows and MCP configuration
set -euo pipefail

echo "=== Phase 08: Setup Agentic Configuration ==="
echo ""

# Create n8n credentials template (optional — users create via UI)
sudo mkdir -p /data/n8n-credentials
sudo tee /data/n8n-credentials/README.md <<'EOF'
# n8n Credentials

Store credential templates here. n8n UI at :5678 to add credentials:

1. **Ollama (OpenAI Compatible)**
   - Type: OpenAI API
   - Base URL: http://10.10.10.2:11434/v1
   - API Key: EMPTY

2. **Loadout Manager**
   - Type: HTTP Header Auth
   - Base URL: http://10.10.10.2:8800
   - Header: Authorization: Bearer <optional-token>

3. **Localhost SSH** (for remote command execution)
   - Host: 10.10.10.2
   - Port: 22
   - User: kasemo
   - Auth: key-pair or password

4. **PostgreSQL** (for Dify database)
   - Host: dify-db
   - Port: 5432
   - User: dify
   - Password: difypassword
   - Database: dify
EOF

sudo mkdir -p /data/n8n-workflows
sudo tee /data/n8n-workflows/README.md <<'EOF'
# n8n Workflow Templates

Reference workflows for common AI workstation tasks:

## 1. Health Monitor
Check Loadout Manager every 5 minutes:
- Trigger: Cron (every 5 min)
- Node: HTTP Request → Loadout Manager /status
- Node: IF → GPU temp > 85°C? → Send alert
- Node: Slack/Email notification

## 2. Training Pipeline
Trigger training job and monitor:
- Trigger: Webhook (POST /training)
- Node: Activate Loadout Manager profile
- Node: Docker Run → Axolotl training
- Node: Poll for completion (check /data/checkpoints/)
- Node: Notify via webhook

## 3. Content Generation
Text → prompt enhancement → image generation:
- Trigger: Webhook (POST /generate)
- Node: LLM (Ollama) → Enhance prompt
- Node: HTTP Request → ComfyUI API queue
- Node: Poll ComfyUI /queue → get result
- Node: Real-ESRGAN upscale
- Node: Save + return

## 4. RAG Document Ingestion
Watch folder → chunk → embed → store:
- Trigger: File (watch /data/documents/inbox/)
- Node: PDFParser → extract text
- Node: Chunk node (1000 token chunks)
- Node: LLM (Ollama) → embed via nomic-embed-text
- Node: Qdrant → upsert embeddings
- Node: Move file to /data/documents/processed/

## 5. Dataset Curation
Filter quality → tag → move to training:
- Trigger: File (watch /data/datasets/raw/)
- Node: Load image
- Node: LLM vision check → quality score
- Node: IF score > 0.7 → Label Studio auto-tag
- Node: Move to /data/datasets/formatted/
- Node: Update training queue
EOF

sudo chown -R "$(id -u):$(id -g)" /data/n8n-credentials /data/n8n-workflows

echo "✓ Created /data/n8n-credentials/"
echo "✓ Created /data/n8n-workflows/ with reference templates"
echo ""
echo "Next: Visit n8n UI at http://10.10.10.2:5678 to:"
echo "  1. Create owner account"
echo "  2. Add credentials (Ollama, Loadout Manager, SSH, etc.)"
echo "  3. Build first workflow from templates above"

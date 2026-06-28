import { Panel } from '../../Panel';

export function HelpResources() {
  return (
    <div className="help-section">
      <div className="help-section-header">
        <h2 className="help-section-title">Resources</h2>
        <p className="help-section-subtitle">
          The Resources page manages all data assets: models, datasets, fine-tuning checkpoints, vector collections, and raw file storage. It has five tabs.
        </p>
      </div>

      <Panel title="Models Tab">
        <div className="help-body">
          <p>Lists all models stored in MinIO, organized by inference engine:</p>
          <ul>
            <li><strong>vLLM models</strong> — HuggingFace-format model directories for use with the vLLM inference server</li>
            <li><strong>Ollama models</strong> — GGUF quantized models downloaded via Ollama</li>
            <li><strong>Axolotl base models</strong> — Models available as a base for text LoRA training</li>
            <li><strong>Kohya base models</strong> — Diffusion checkpoints available for image LoRA training</li>
          </ul>
          <p>Each model entry shows file size, type, and last modified date. Use the download button to export a model, or the delete button (with confirmation) to free up storage.</p>
          <div className="help-tip">
            <strong>Tip:</strong> To add a new model, pull it via Ollama (CLI) or copy it into the MinIO bucket via the Storage tab or the MinIO web console (port 9001).
          </div>
        </div>
      </Panel>

      <Panel title="Datasets Tab">
        <div className="help-body">
          <p>Browse and manage training datasets stored in <span className="help-code">/data/datasets/</span>.</p>
          <h3>Uploading a dataset</h3>
          <ol className="help-steps" style={{marginTop: 6}}>
            <li className="help-step">
              <span className="help-step-number">1</span>
              <div className="help-step-body">Drag and drop a file onto the upload area, or click to browse. Supported: JSONL, CSV, Parquet.</div>
            </li>
            <li className="help-step">
              <span className="help-step-number">2</span>
              <div className="help-step-body">The file is validated on upload. Malformed files are rejected with an error message.</div>
            </li>
            <li className="help-step">
              <span className="help-step-number">3</span>
              <div className="help-step-body">Once uploaded, the dataset appears in the list and is available to select in the Training wizard.</div>
            </li>
          </ol>
          <h3 style={{marginTop: 10}}>Dataset format for text LoRA</h3>
          <p>Axolotl expects JSONL with one JSON object per line. Recommended format (instruction tuning):</p>
          <pre className="help-code" style={{display: 'block', padding: '8px 10px', marginTop: 6, lineHeight: 1.6, fontSize: 10}}>
{`{"instruction": "Summarize this:", "input": "...", "output": "..."}`}
          </pre>
        </div>
      </Panel>

      <Panel title="Checkpoints Tab">
        <div className="help-body">
          <p>Lists fine-tuning outputs exported from training runs. Each checkpoint entry shows:</p>
          <ul>
            <li><strong>Name</strong> — derived from the training run name and timestamp</li>
            <li><strong>Base model</strong> — the model this adapter was trained on</li>
            <li><strong>Created</strong> — when the checkpoint was exported</li>
            <li><strong>Size</strong> — disk usage of the adapter weights</li>
          </ul>
          <p>Use <strong>View Config</strong> to inspect the Axolotl or Kohya YAML that generated the checkpoint. Use <strong>Download</strong> to export the weights to your local machine.</p>
        </div>
      </Panel>

      <Panel title="Vectors Tab">
        <div className="help-body">
          <p>Connects to the Qdrant vector database and lists all collections. Each collection shows:</p>
          <ul>
            <li><strong>Vector count</strong> — total number of embeddings stored</li>
            <li><strong>Dimensions</strong> — the embedding size (e.g., 768, 1536, 4096)</li>
            <li><strong>Index type</strong> — HNSW or flat index</li>
            <li><strong>Disk usage</strong></li>
          </ul>
          <p>Collections are typically created by external applications (n8n, Dify, custom code) that use Qdrant for RAG (retrieval-augmented generation). You can browse and filter vectors by metadata from this tab.</p>
        </div>
      </Panel>

      <Panel title="Storage Tab">
        <div className="help-body">
          <p>A direct file browser for the MinIO S3-compatible object store. Buckets:</p>
          <ul>
            <li><span className="help-code">models</span> — all model weights</li>
            <li><span className="help-code">datasets</span> — training datasets</li>
            <li><span className="help-code">checkpoints</span> — fine-tuning outputs</li>
          </ul>
          <p>You can upload files directly, download individual files, and view disk usage quotas per bucket. For bulk operations, use the MinIO web console available at port 9001 when the MinIO service is running.</p>
        </div>
      </Panel>
    </div>
  );
}

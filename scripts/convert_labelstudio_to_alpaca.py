#!/usr/bin/env python3
"""Convert Label Studio conversational export to Alpaca JSONL for Axolotl."""
import json
import sys
from pathlib import Path


def convert(input_path: str, output_path: str):
    """Convert Label Studio JSON export to Alpaca JSONL format."""
    with open(input_path) as f:
        tasks = json.load(f)
    
    records = []
    for task in tasks:
        ann = task.get("annotations", [{}])[0]
        result = ann.get("result", [])
        
        instruction = task["data"].get("instruction", "")
        input_text = task["data"].get("input", "")
        output_text = ""
        
        # Extract text from annotation results
        for r in result:
            if r.get("type") == "textarea":
                output_text = r["value"]["text"][0]
        
        # Only include complete records
        if instruction and output_text:
            records.append({
                "instruction": instruction,
                "input": input_text,
                "output": output_text
            })
    
    # Write JSONL format (one record per line)
    with open(output_path, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    
    print(f"Converted {len(records)} records → {output_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: convert_labelstudio_to_alpaca.py <input.json> <output.jsonl>")
        sys.exit(1)
    convert(sys.argv[1], sys.argv[2])

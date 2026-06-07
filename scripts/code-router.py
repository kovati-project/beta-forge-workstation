#!/usr/bin/env python3
"""
Code model routing: Select the best model for code requests based on language/task.
Integrates with Continue.dev and OpenHands for optimal performance.
"""
import re
from enum import Enum
from typing import Optional

class CodeModel(Enum):
    """Available code models and their characteristics."""
    QWEN_32B = {
        "name": "qwen2.5-coder:32b",
        "endpoint": "http://10.10.10.2:8000/v1",
        "context": 32768,
        "speed": "medium",
        "quality": "high",
        "description": "Primary: best overall code quality, architecture decisions"
    }
    DEEPSEEK_16B = {
        "name": "deepseek-coder-v2:16b",
        "endpoint": "http://10.10.10.2:11434",
        "context": 16384,
        "speed": "fast",
        "quality": "high",
        "description": "Debugging, refactoring, issue diagnosis"
    }
    CODELLAMA_70B = {
        "name": "codellama:70b",
        "endpoint": "http://10.10.10.2:8002/v1",
        "context": 100000,
        "speed": "slow",
        "quality": "highest",
        "description": "Security review, architecture, complex refactoring, large context"
    }
    QWEN_14B = {
        "name": "qwen2.5-coder:14b",
        "endpoint": "http://10.10.10.2:11434",
        "context": 16384,
        "speed": "fast",
        "quality": "good",
        "description": "Fast turnaround, still high quality"
    }
    QWEN_7B = {
        "name": "qwen2.5-coder:7b",
        "endpoint": "http://10.10.10.2:11434",
        "context": 4096,
        "speed": "fastest",
        "quality": "good",
        "description": "Autocomplete, tab suggestions, <100ms response"
    }

class CodeRouter:
    """Route code requests to optimal models."""
    
    LANGUAGE_ROUTING = {
        # Systems languages (complex, use larger models)
        "rust":       CodeModel.QWEN_32B,
        "c":          CodeModel.QWEN_32B,
        "c++":        CodeModel.QWEN_32B,
        "cpp":        CodeModel.QWEN_32B,
        "zig":        CodeModel.QWEN_32B,
        
        # CUDA kernels (use largest, most capable model)
        "cuda":       CodeModel.CODELLAMA_70B,
        "cuda-c":     CodeModel.CODELLAMA_70B,
        
        # Web/application languages
        "python":     CodeModel.QWEN_32B,
        "typescript": CodeModel.QWEN_32B,
        "javascript": CodeModel.QWEN_32B,
        "go":         CodeModel.QWEN_32B,
        "java":       CodeModel.QWEN_32B,
        
        # Fast feedback languages
        "bash":       CodeModel.QWEN_14B,
        "shell":      CodeModel.QWEN_14B,
        "sql":        CodeModel.QWEN_14B,
        "yaml":       CodeModel.QWEN_14B,
    }
    
    TASK_ROUTING = {
        # Tasks requiring security focus → use largest model
        "security":      CodeModel.CODELLAMA_70B,
        "audit":         CodeModel.CODELLAMA_70B,
        "cve":           CodeModel.CODELLAMA_70B,
        "vulnerability": CodeModel.CODELLAMA_70B,
        "penetration":   CodeModel.CODELLAMA_70B,
        
        # Architecture/design decisions → use larger model
        "architect":     CodeModel.CODELLAMA_70B,
        "design":        CodeModel.QWEN_32B,
        "refactor":      CodeModel.QWEN_32B,
        "optimize":      CodeModel.QWEN_32B,
        "performance":   CodeModel.QWEN_32B,
        
        # Debugging → use specialized model
        "debug":         CodeModel.DEEPSEEK_16B,
        "fix":           CodeModel.DEEPSEEK_16B,
        "issue":         CodeModel.DEEPSEEK_16B,
        "error":         CodeModel.DEEPSEEK_16B,
        
        # Documentation → fast model OK
        "document":      CodeModel.QWEN_14B,
        "comment":       CodeModel.QWEN_14B,
        "explain":       CodeModel.QWEN_14B,
        
        # Autocomplete → use fastest
        "complete":      CodeModel.QWEN_7B,
        "autocomplete":  CodeModel.QWEN_7B,
        "suggest":       CodeModel.QWEN_7B,
    }
    
    KEYWORD_ROUTING = {
        # Keywords that strongly indicate model choice
        "sql injection":         CodeModel.CODELLAMA_70B,
        "buffer overflow":       CodeModel.CODELLAMA_70B,
        "memory leak":           CodeModel.QWEN_32B,
        "race condition":        CodeModel.QWEN_32B,
        "deadlock":              CodeModel.DEEPSEEK_16B,
        "kernel":                CodeModel.QWEN_32B,
        "nvlink":                CodeModel.QWEN_32B,
        "vllm":                  CodeModel.QWEN_32B,
        "inference":             CodeModel.QWEN_32B,
        "fsdp":                  CodeModel.QWEN_32B,
        "distributed":           CodeModel.QWEN_32B,
        "algorithm":             CodeModel.QWEN_32B,
        "complexity":            CodeModel.QWEN_32B,
    }

    @staticmethod
    def route(
        message: str,
        language: Optional[str] = None,
        task: Optional[str] = None,
        context_size: int = 4096,
        speed_priority: bool = False
    ) -> dict:
        """
        Route a code request to the best model.
        
        Args:
            message: The code request message
            language: Programming language (optional, auto-detected if not provided)
            task: Task type (optional, auto-detected if not provided)
            context_size: Required context size (defaults to reasonable minimum)
            speed_priority: If True, prefer speed over quality
        
        Returns:
            Dict with model info: {name, endpoint, context, model_obj, reason}
        """
        message_lower = message.lower()
        
        # Explicit language override
        if language:
            language_lower = language.lower()
            if language_lower in CodeRouter.LANGUAGE_ROUTING:
                model = CodeRouter.LANGUAGE_ROUTING[language_lower]
                return CodeRouter._model_dict(model, f"Language: {language}")
        
        # Explicit task override
        if task:
            task_lower = task.lower()
            if task_lower in CodeRouter.TASK_ROUTING:
                model = CodeRouter.TASK_ROUTING[task_lower]
                return CodeRouter._model_dict(model, f"Task: {task}")
        
        # Check keywords in message
        for keyword, model in CodeRouter.KEYWORD_ROUTING.items():
            if keyword in message_lower:
                return CodeRouter._model_dict(model, f"Keyword: {keyword}")
        
        # Check for task keywords in message
        for task_keyword, model in CodeRouter.TASK_ROUTING.items():
            if task_keyword in message_lower:
                return CodeRouter._model_dict(model, f"Task inferred: {task_keyword}")
        
        # Check for language keywords in message (code blocks, imports, etc.)
        language_patterns = {
            r"\bimport\s+\w+|from\s+\w+\s+import": CodeModel.PYTHON,
            r"^import\s+\{|^export\s+(const|function|class)": CodeModel.QWEN_32B,  # TypeScript
            r"^package\s+\w+|^func\s+\w+": CodeModel.QWEN_32B,  # Go
            r"^use\s+\w+::|^fn\s+\w+\(": CodeModel.QWEN_32B,  # Rust
            r"^fn\s+\w+\(|\blua\b": CodeModel.QWEN_14B,
            r"^#include|^int\s+main": CodeModel.QWEN_32B,  # C/C++
        }
        
        for pattern, model in language_patterns.items():
            if re.search(pattern, message, re.MULTILINE):
                return CodeRouter._model_dict(model, "Language detected from code")
        
        # Speed priority mode (use faster models)
        if speed_priority:
            return CodeRouter._model_dict(CodeModel.QWEN_14B, "Speed priority mode")
        
        # Default to primary model
        return CodeRouter._model_dict(CodeModel.QWEN_32B, "Default (primary model)")

    @staticmethod
    def _model_dict(model: CodeModel, reason: str) -> dict:
        """Convert model enum to dictionary."""
        info = model.value
        return {
            "model": info["name"],
            "endpoint": info["endpoint"],
            "context": info["context"],
            "speed": info["speed"],
            "quality": info["quality"],
            "description": info["description"],
            "reason": reason
        }

    @staticmethod
    def for_autocomplete() -> dict:
        """Get model for tab autocomplete (always fastest)."""
        return CodeRouter._model_dict(CodeModel.QWEN_7B, "Tab autocomplete")

    @staticmethod
    def for_security() -> dict:
        """Get model for security review (always best)."""
        return CodeRouter._model_dict(CodeModel.CODELLAMA_70B, "Security review")

    @staticmethod
    def for_architecture() -> dict:
        """Get model for architecture decisions (always best)."""
        return CodeRouter._model_dict(CodeModel.CODELLAMA_70B, "Architecture decision")

def main():
    """CLI for testing router."""
    import json
    
    # Test cases
    test_cases = [
        ("Write a CUDA kernel for matrix multiplication", None, None),
        ("Debug this deadlock issue", None, None),
        ("Security review of this authentication code", None, "security"),
        ("Add docstrings to this function", None, "document"),
        ("Optimize this SQL query", "sql", None),
        ("Complete this Python function", None, None),
        ("Fix this buffer overflow in C", "c", None),
    ]
    
    print("Code Model Router Test\n" + "=" * 60)
    for message, lang, task in test_cases:
        result = CodeRouter.route(message, language=lang, task=task)
        print(f"\nMessage: {message}")
        print(f"Language: {lang}, Task: {task}")
        print(f"→ Model: {result['model']}")
        print(f"  Speed: {result['speed']}, Quality: {result['quality']}")
        print(f"  Reason: {result['reason']}")

if __name__ == "__main__":
    main()

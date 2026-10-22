import os
import json
import re
import replicate
from typing import Optional, Dict, Any, List, Generator
from pydantic import BaseModel


class DynamicTool(BaseModel):
    tool_name: str
    description: str
    inputs: list
    # Kernel-native compute: the card solves `relation` for `solve_for`
    # server-side. The model references a kernel relation by name; it never
    # ships executable code.
    relation: Optional[str] = None
    solve_for: Optional[str] = None
    output_unit: Optional[str] = None
    formula_latex: Optional[str] = None
    # Deprecated: never executed. Kept only so old persisted sessions parse.
    formula_js: Optional[str] = None
    outputs: Optional[list] = None
    suggestions: Optional[list] = None


class LLMResponse(BaseModel):
    content: str
    chat_title: Optional[str] = None
    tool: Optional[DynamicTool] = None


def run_llama(prompt: str, model: str, temperature: float = 0.7) -> Generator[str, None, None]:
    """
    Helper to run Llama 3 via Replicate with Streaming.
    """
    output = replicate.stream(
        model,
        input={
            "prompt": prompt,
            "max_tokens": 2048,
            "temperature": temperature,
            "top_p": 0.9,
            "stop_sequences": "<|eot_id|>"
        }
    )
    for event in output:
        yield str(event)


def extract_balanced_json(text: str, start_idx: int) -> Optional[str]:
    """
    Extract a complete JSON object starting at start_idx by balancing braces.
    Properly handles strings and escape characters.
    """
    if start_idx >= len(text) or text[start_idx] != '{':
        return None
    
    depth = 0
    in_string = False
    i = start_idx
    
    while i < len(text):
        char = text[i]
        
        # Handle escape sequences in strings
        if in_string and char == '\\' and i + 1 < len(text):
            i += 2  # Skip escaped character
            continue
        
        # Handle string boundaries
        if char == '"':
            in_string = not in_string
        
        # Only count braces outside of strings
        if not in_string:
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    return text[start_idx:i + 1]
        
        i += 1
    
    return None


def try_parse_json(text: str) -> Optional[dict]:
    """
    Try to parse JSON with multiple repair strategies for LLM output.
    """
    if not text or not text.strip():
        return None
    
    text = text.strip()
    
    # Strategy 1: Direct parse
    try:
        return json.loads(text)
    except:
        pass
    
    # Strategy 2: Fix unescaped backslashes in LaTeX
    try:
        # Replace single backslashes not followed by valid JSON escape chars
        fixed = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', text)
        return json.loads(fixed)
    except:
        pass
    
    # Strategy 3: Use strict=False for control chars
    try:
        return json.loads(text, strict=False)
    except:
        pass
    
    # Strategy 4: Try to complete truncated JSON
    try:
        opens = text.count('{')
        closes = text.count('}')
        if opens > closes:
            text += '}' * (opens - closes)
        return json.loads(text, strict=False)
    except:
        pass
    
    return None


def parse_llm_response(response_text: str) -> tuple[str, Optional[DynamicTool], Optional[str]]:
    """
    Parse LLM response to extract content and tool.
    Handles JSON both with and without code fences.
    """
    if not response_text:
        return "", None, None
    
    content = response_text
    tool_obj = None
    title = None
    
    # STRATEGY 1: Find code-fenced JSON blocks
    # Match entire code fence including backticks
    fence_pattern = r'```(?:json)?\s*([\s\S]*?)```'
    
    for match in re.finditer(fence_pattern, response_text):
        block_content = match.group(1).strip()
        
        # Find JSON object within the code block
        json_start = block_content.find('{')
        if json_start == -1:
            continue
            
        json_str = extract_balanced_json(block_content, json_start)
        if json_str and '"tool_name"' in json_str:
            parsed = try_parse_json(json_str)
            if parsed and 'tool_name' in parsed:
                # Found valid tool - extract content before the code fence
                content = response_text[:match.start()].strip()
                
                # Clean up trailing labels
                content = re.sub(r'\*\*(?:Calculator\s*)?Tool:\*\*\s*$', '', content, flags=re.IGNORECASE).strip()
                content = re.sub(r'(?:Calculator\s*)?Tool:\s*$', '', content, flags=re.IGNORECASE).strip()
                content = re.sub(r'Here(?:\'s| is) (?:the|a) (?:calculator|tool).*?:\s*$', '', content, flags=re.IGNORECASE).strip()
                
                # Create tool object
                try:
                    tool_data = parsed.get('arguments', parsed)
                    tool_obj = DynamicTool(
                        tool_name=tool_data.get('tool_name', 'Calculator'),
                        description=tool_data.get('description', ''),
                        inputs=tool_data.get('inputs', []),
                        relation=tool_data.get('relation'),
                        solve_for=tool_data.get('solve_for'),
                        output_unit=tool_data.get('output_unit'),
                        formula_latex=tool_data.get('formula_latex'),
                        formula_js=tool_data.get('formula_js'),
                        outputs=tool_data.get('outputs'),
                        suggestions=tool_data.get('suggestions')
                    )
                    title = parsed.get('chat_title')
                    return content, tool_obj, title
                except Exception as e:
                    print(f"Tool creation error: {e}")
                    continue

    # STRATEGY 2: Look for bare JSON (no code fence)
    # Find all { positions and try to extract JSON
    for i, char in enumerate(response_text):
        if char == '{':
            # Skip if inside a code fence
            before = response_text[:i]
            fence_opens = before.count('```')
            if fence_opens % 2 == 1:  # Inside a code fence
                continue
            
            json_str = extract_balanced_json(response_text, i)
            if json_str and '"tool_name"' in json_str:
                parsed = try_parse_json(json_str)
                if parsed and 'tool_name' in parsed:
                    content = response_text[:i].strip()
                    
                    # Clean up labels
                    content = re.sub(r'\*\*(?:Calculator\s*)?Tool:\*\*\s*$', '', content, flags=re.IGNORECASE).strip()
                    content = re.sub(r'(?:Calculator\s*)?Tool:\s*$', '', content, flags=re.IGNORECASE).strip()
                    
                    try:
                        tool_data = parsed.get('arguments', parsed)
                        tool_obj = DynamicTool(
                            tool_name=tool_data.get('tool_name', 'Calculator'),
                            description=tool_data.get('description', ''),
                            inputs=tool_data.get('inputs', []),
                            relation=tool_data.get('relation'),
                            solve_for=tool_data.get('solve_for'),
                            output_unit=tool_data.get('output_unit'),
                            formula_latex=tool_data.get('formula_latex'),
                            formula_js=tool_data.get('formula_js'),
                            outputs=tool_data.get('outputs'),
                            suggestions=tool_data.get('suggestions')
                        )
                        title = parsed.get('chat_title')
                        return content, tool_obj, title
                    except Exception as e:
                        print(f"Tool creation error: {e}")
                        continue
    
    # No tool found
    return content, None, None

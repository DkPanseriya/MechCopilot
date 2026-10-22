import re
import json
from pydantic import BaseModel
from typing import Optional, List

class DynamicTool(BaseModel):
    tool_name: str
    description: str
    inputs: list
    formula_latex: Optional[str] = None

def repair_json(json_str: str) -> str:
    """
    Attempts to fix common LLM JSON errors, specifically single backslashes in LaTeX.
    """
    # Replace all backslashes with double backslashes, 
    # except if they are already followed by a double quote (escaping the quote).
    return re.sub(r'\\(?!")', r'\\\\', json_str)

def parse_tool_response(response_text: str):
    # Try code block first
    json_match = re.search(r"```json\s*(\{.*?\})\s*```", response_text, re.DOTALL)
    if not json_match:
        # Try raw JSON
        json_match = re.search(r"(\{.*\})", response_text, re.DOTALL)
    
    if json_match:
        try:
            raw_json = json_match.group(1)
            print(f"Found raw JSON: {raw_json}")
            
            try:
                # Try strict first
                tool_json = json.loads(raw_json)
            except json.JSONDecodeError as jde:
                print(f"Strict decoding failed: {jde}")
                # Try non-strict (allows control characters like form feed)
                try:
                    tool_json = json.loads(raw_json, strict=False)
                    print("Non-strict decoding succeeded!")
                except:
                    # If still fails, try repair
                    print("Repairing...")
                    raw_json = repair_json(raw_json)
                    print(f"Repaired JSON: {raw_json}")
                    tool_json = json.loads(raw_json, strict=False)
            
            args = None
            if isinstance(tool_json, dict):
                if "arguments" in tool_json:
                    args = tool_json["arguments"]
                elif "inputs" in tool_json and "tool_name" in tool_json:
                    args = tool_json
                
            if args:
                print(f"Candidate args: {args}")
                tool_data = DynamicTool(**args) 
                clean_text = response_text.replace(json_match.group(0), "").strip()
                return clean_text, tool_data
        except Exception as e:
            print(f"Error during parsing: {e}")
            return response_text, None

    return response_text, None

# Test with single backslash LaTeX (Invalid JSON)
# USE RAW STRING r"..." to simulate what we get from the network
test_text = r"""
Here is the JSON object for a calculator tool:
{
  "tool_name": "Axial Stress Calculator",
  "arguments": {
    "tool_name": "Axial Stress Calculator",
    "description": "Calculates stress.",
    "formula_latex": "\sigma = \frac{F}{A}",
    "inputs": [
      {"name": "force", "label": "Force (N)", "type": "number", "unit": "N"}
    ]
  }
}
"""

clean, tool = parse_tool_response(test_text)
print(f"\nCLEAN TEXT:\n{clean}")
print(f"\nTOOL DATA:\n{tool}")

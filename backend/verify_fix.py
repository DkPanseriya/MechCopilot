
import sys
import os

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from llm_utils import parse_llm_response

user_failure_case = r"""
Dynamic Loadcases for a Car Upright Design

When designing a car upright...

Example Loadcases

Loadcase 1: Straight-line acceleration (longitudinal, acceleration)
Loadcase 2: Cornering (lateral, cornering)
Loadcase 3: Braking (longitudinal, braking)
Loadcase 4: Bump (vertical, impact)

JSON Tool

{
  "tool_name": "Dynamic Loadcase Calculator",
  "arguments": {
    "tool_name": "Dynamic Loadcase Calculator",
    "description": "Calculate dynamic loadcases for a car upright design",
    "formula_latex": "F_acc = m \\* a",
    "inputs": [
      {"name": "m", "label": "Mass", "unit": "kg", "unit_type": "mass", "type": "number"},
      {"name": "a", "label": "Acceleration", "unit": "m/s^2", "unit_type": "acceleration", "type": "number"}
    ]
  }
}
"""

print("Testing parse_llm_response with User Failure Case (No code blocks, text + JSON)...")
content, tool, title = parse_llm_response(user_failure_case)

print(f"Content length: {len(content)}")
print(f"Content ends with: {content[-50:]}") # Check if JSON text is removed
print(f"Tool found: {tool is not None}")
if tool:
    print(f"Tool Name: {tool.tool_name}")
    print(f"Inputs: {len(tool.inputs)}")

if tool and tool.tool_name == "Dynamic Loadcase Calculator" and "JSON Tool" not in content:
    print("SUCCESS: Tool extracted and content cleaned.")
else:
    print("FAILURE: Validation failed.")
    if "JSON Tool" in content:
        print("Reason: 'JSON Tool' label remains in content.")
